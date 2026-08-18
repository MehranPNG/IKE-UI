import os
import sys
import time
import datetime
import sqlite3
import subprocess
import shutil
import re
import json
import threading
import signal
import fcntl
import secrets
import string
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, stream_with_context
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", "/etc/strongswan-panel/panel.db")
SECRETS_PATH = os.environ.get("SECRETS_PATH", "/etc/ipsec.secrets")
SECRET_KEY_PATH = os.environ.get("SECRET_KEY_PATH", "/etc/strongswan-panel/secret.key")
SERVER_DOMAIN = os.environ.get("SERVER_DOMAIN", "faghir.seytann.com")
PANEL_PORT = int(os.environ.get("PANEL_PORT", 8000))

def generate_random_pwd(length=8):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def get_persistent_secret_key():
    candidates = [
        SECRET_KEY_PATH,
        os.path.join(BASE_DIR, ".secret.key")
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    key = f.read()
                    if len(key) >= 16:
                        return key
            except Exception:
                pass

    new_key = os.urandom(32)
    for path in candidates:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "wb") as f:
                f.write(new_key)
            os.chmod(path, 0o600)
            return new_key
        except Exception:
            continue
    return new_key

APP_VERSION = "1.2.1"

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

app.secret_key = get_persistent_secret_key()
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Graceful shutdown flag
shutdown_event = threading.Event()

def signal_handler(signum, frame):
    shutdown_event.set()

try:
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
except Exception:
    pass

@app.context_processor
def inject_globals():
    return dict(
        app_version=APP_VERSION,
        current_admin=session.get("admin_user", ""),
        vpn_enabled=(get_system_config("vpn_enabled", "1") == "1")
    )

prev_cpu_times = None
prev_net_bytes = None
prev_net_time = None

def get_cpu_raw():
    try:
        with open('/proc/stat') as f:
            line = f.readline()
            vals = [float(x) for x in line.split()[1:8]]
            idle = vals[3] + vals[4]
            total = sum(vals)
            return idle, total
    except Exception:
        return 0, 0

def get_net_raw():
    rx, tx = 0, 0
    try:
        with open('/proc/net/dev') as f:
            for line in f:
                if ':' in line:
                    iface, data = line.split(':', 1)
                    if iface.strip() != 'lo':
                        fields = data.split()
                        rx += int(fields[0])
                        tx += int(fields[8])
    except Exception:
        pass
    return rx, tx

def format_speed(bps):
    if bps < 1024:
        return f"{bps:.0f} B/s"
    elif bps < 1024 * 1024:
        return f"{bps / 1024:.1f} KB/s"
    else:
        return f"{bps / (1024 * 1024):.2f} MB/s"

def get_system_metrics():
    global prev_cpu_times, prev_net_bytes, prev_net_time
    now = time.time()
    
    try:
        total, used, free = shutil.disk_usage('/')
        disk_pct = round((used / total) * 100, 1)
        disk_used_gb = round(used / (1024**3), 1)
        disk_total_gb = round(total / (1024**3), 1)
    except Exception:
        disk_pct, disk_used_gb, disk_total_gb = 0, 0, 0

    try:
        mem = {}
        with open('/proc/meminfo') as f:
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    mem[parts[0].strip()] = int(parts[1].split()[0])
        mem_total = mem.get('MemTotal', 1)
        mem_avail = mem.get('MemAvailable', mem.get('MemFree', 0))
        mem_used = mem_total - mem_avail
        ram_pct = round((mem_used / mem_total) * 100, 1)
        ram_used_gb = round(mem_used / 1024 / 1024, 2)
        ram_total_gb = round(mem_total / 1024 / 1024, 2)
    except Exception:
        ram_pct, ram_used_gb, ram_total_gb = 0, 0, 0

    curr_idle, curr_total = get_cpu_raw()
    cpu_pct = 0.0
    if prev_cpu_times:
        p_idle, p_total = prev_cpu_times
        d_idle = curr_idle - p_idle
        d_total = curr_total - p_total
        if d_total > 0:
            cpu_pct = round(max(0.0, min(100.0, (1.0 - (d_idle / d_total)) * 100)), 1)
    prev_cpu_times = (curr_idle, curr_total)

    curr_rx, curr_tx = get_net_raw()
    rx_spd, tx_spd = "0 B/s", "0 B/s"
    if prev_net_bytes and prev_net_time:
        dt = now - prev_net_time
        if dt > 0:
            p_rx, p_tx = prev_net_bytes
            rx_spd = format_speed(max(0, curr_rx - p_rx) / dt)
            tx_spd = format_speed(max(0, curr_tx - p_tx) / dt)
    prev_net_bytes = (curr_rx, curr_tx)
    prev_net_time = now

    cpu_cores = os.cpu_count() or 1

    return {
        "cpu_percent": cpu_pct,
        "cpu_cores": cpu_cores,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "ram_percent": ram_pct,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "disk_percent": disk_pct,
        "net_rx": rx_spd,
        "net_tx": tx_spd
    }

get_system_metrics()

def get_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def get_db_usernames():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users")
        usernames = {row["username"] for row in cursor.fetchall()}
        conn.close()
        return usernames
    except Exception:
        return set()

def get_system_config(key, default="1"):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row and row["value"] is not None:
            return row["value"]
        return default
    except Exception:
        return default

def set_system_config(key, value):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_config (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Error setting config {key}: {e}", file=sys.stderr)

def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT
        )
        """)
        
        try:
            cursor.execute("ALTER TABLE admin ADD COLUMN created_at TEXT")
        except Exception:
            pass

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            max_traffic_gb REAL DEFAULT 0,
            used_traffic_bytes INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            expire_date TEXT,
            is_active INTEGER DEFAULT 1,
            note TEXT DEFAULT '',
            last_online_at TEXT,
            max_devices INTEGER DEFAULT 10
        )
        """)
        
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN last_online_at TEXT")
        except Exception:
            pass

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN max_devices INTEGER DEFAULT 10")
        except Exception:
            pass

        cursor.execute("UPDATE users SET max_devices = 10 WHERE max_devices IS NULL OR max_devices <= 0 OR max_devices > 10")
        
        cursor.execute("SELECT * FROM admin WHERE username = 'admin'")
        if not cursor.fetchone():
            default_hash = generate_password_hash("admin123")
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO admin (username, password_hash, created_at) VALUES ('admin', ?, ?)", (default_hash, now))
            
        cursor.execute("SELECT COUNT(*) as cnt FROM users")
        if cursor.fetchone()["cnt"] == 0:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            default_user_pass = generate_random_pwd(8)
            cursor.execute("""
                INSERT INTO users (username, password, max_traffic_gb, used_traffic_bytes, created_at, expire_date, is_active, note, last_online_at, max_devices)
                VALUES ('user1', ?, 0, 0, ?, NULL, 1, 'Default VPN User', NULL, 10)
            """, (default_user_pass, now))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Error in init_db: {e}", file=sys.stderr)

sync_lock = threading.Lock()

def disconnect_all_sas():
    """Disconnect all active StrongSwan SAs when VPN is killed."""
    try:
        subprocess.run(["ipsec", "down", "ikev2-vpn"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        online = fetch_online_users_raw()
        for u, data in online.items():
            for sa_id in data.get("sa_ids", []):
                if sa_id:
                    subprocess.run(["ipsec", "down", f"ikev2-vpn[{sa_id}]"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["ipsec", "down", str(sa_id)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[!] Error disconnecting all SAs: {e}", file=sys.stderr)

def disconnect_user_sas(username, online_dict=None):
    """Safely disconnect all active StrongSwan SAs for a specific username."""
    if not username:
        return
    try:
        if online_dict is None:
            online_dict = fetch_online_users_raw()
        user_info = online_dict.get(username)
        if user_info:
            for sa_id in user_info.get("sa_ids", []):
                if sa_id:
                    subprocess.run(["ipsec", "down", f"ikev2-vpn[{sa_id}]"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["ipsec", "down", str(sa_id)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[!] Error disconnecting SAs for {username}: {e}", file=sys.stderr)

def disconnect_excess_sas(username, max_devices, online_dict=None):
    """Disconnect oldest excess SAs if a user has more connections than max_devices."""
    if not username:
        return
    try:
        max_dev = max(1, min(10, int(max_devices or 10)))
        if online_dict is None:
            online_dict = fetch_online_users_raw()
        user_info = online_dict.get(username)
        if user_info:
            sa_ids = user_info.get("sa_ids", [])
            if len(sa_ids) > max_dev:
                try:
                    sorted_sas = sorted(sa_ids, key=lambda x: int(x) if str(x).isdigit() else str(x))
                except Exception:
                    sorted_sas = list(sa_ids)
                excess_count = len(sorted_sas) - max_dev
                excess_sas = sorted_sas[:excess_count]
                for sa_id in excess_sas:
                    if sa_id:
                        subprocess.run(["ipsec", "down", f"ikev2-vpn[{sa_id}]"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.run(["ipsec", "down", str(sa_id)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[!] Error disconnecting excess SAs for {username}: {e}", file=sys.stderr)

def sync_ipsec_secrets():
    with sync_lock:
        try:
            vpn_enabled = (get_system_config("vpn_enabled", "1") == "1")
            if not vpn_enabled:
                os.makedirs(os.path.dirname(os.path.abspath(SECRETS_PATH)), exist_ok=True)
                temp_secrets = f"{SECRETS_PATH}.tmp"
                with open(temp_secrets, "w") as f:
                    f.write(": RSA privkey.pem\n")
                os.chmod(temp_secrets, 0o600)
                os.replace(temp_secrets, SECRETS_PATH)
                subprocess.run(["ipsec", "rereadsecrets"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT username, password, max_traffic_gb, used_traffic_bytes, expire_date, is_active FROM users")
            users = cursor.fetchall()
            conn.close()
            
            now = datetime.datetime.now()
            active_lines = [": RSA privkey.pem"]
            
            for u in users:
                is_active = u["is_active"] if u["is_active"] is not None else 1
                if u["expire_date"]:
                    try:
                        exp_dt = datetime.datetime.strptime(u["expire_date"], "%Y-%m-%d %H:%M:%S")
                        if now > exp_dt:
                            is_active = 0
                    except Exception:
                        pass
                if u["max_traffic_gb"] and u["max_traffic_gb"] > 0:
                    max_bytes = u["max_traffic_gb"] * 1024 * 1024 * 1024
                    if (u["used_traffic_bytes"] or 0) >= max_bytes:
                        is_active = 0
                        
                if is_active == 1:
                    pwd = str(u["password"]).replace('\\', '\\\\').replace('"', '\\"')
                    uname = str(u["username"]).replace('\\', '\\\\').replace('"', '\\"')
                    active_lines.append(f'{uname} : EAP "{pwd}"')
                    
            os.makedirs(os.path.dirname(os.path.abspath(SECRETS_PATH)), exist_ok=True)
            temp_secrets = f"{SECRETS_PATH}.tmp"
            with open(temp_secrets, "w") as f:
                f.write("\n".join(active_lines) + "\n")
            os.chmod(temp_secrets, 0o600)
            os.replace(temp_secrets, SECRETS_PATH)
            
            subprocess.run(["ipsec", "rereadsecrets"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[!] Error syncing ipsec.secrets: {e}", file=sys.stderr)

cached_online_users = {}
cached_online_time = 0
online_cache_lock = threading.Lock()

def fetch_online_users_raw():
    online = {}
    try:
        db_users = get_db_usernames()
        if not db_users:
            return online
            
        db_users_set = set(db_users)
        db_users_lower = {u.lower(): u for u in db_users}
        
        res = subprocess.run(["ipsec", "statusall"], capture_output=True, text=True, check=False)
        output = res.stdout or ""
        
        lines = output.splitlines()
        sa_blocks = {}
        current_sa_id = None
        
        for line in lines:
            # Match IKE SA line: e.g. `ikev2-vpn[1]: ESTABLISHED` or `[1]: ESTABLISHED`
            ike_match = re.search(r'(?:^|\s)[\w.-]*\[(\d+)\]:\s*(.*)$', line)
            if ike_match:
                sa_id = ike_match.group(1)
                current_sa_id = sa_id
                if current_sa_id not in sa_blocks:
                    sa_blocks[current_sa_id] = []
                sa_blocks[current_sa_id].append(line)
                continue
                
            # Match Child SA line: e.g. `ikev2-vpn{1}: INSTALLED`
            child_match = re.search(r'(?:^|\s)[\w.-]*\{(\d+)\}:\s*(.*)$', line)
            if child_match:
                if current_sa_id is not None:
                    sa_blocks[current_sa_id].append(line)
                continue
                
            # Continuation line under current SA block
            if current_sa_id is not None and (line.startswith(' ') or line.startswith('\t')):
                sa_blocks[current_sa_id].append(line)
            else:
                if line.strip() and not line.startswith(' '):
                    current_sa_id = None

        # Parse each SA block
        for sa_id, block_lines in sa_blocks.items():
            block_text = "\n".join(block_lines)
            
            # Check if SA is ESTABLISHED
            if not re.search(r'ESTABLISHED', block_text, re.IGNORECASE):
                continue
                
            candidates = []
            
            # 1. EAP identity patterns (Remote EAP identity, EAP identity, EAP identity '%any' -> ...)
            eap_matches = re.findall(r'(?:Remote\s+)?EAP\s+identity(?:\s*\'%any\'\s*->)?\s*[:\s]\s*[\'\"]?([^\'\s\n\r,\]]+)', block_text, re.IGNORECASE)
            for m in eap_matches:
                candidates.append(m.strip("'\" \t"))
                
            # 2. Remote identity patterns
            rem_matches = re.findall(r'Remote\s+identity\s*[:\s]\s*[\'\"]?([^\'\s\n\r,\]]+)', block_text, re.IGNORECASE)
            for m in rem_matches:
                candidates.append(m.strip("'\" \t"))
                
            # 3. ESTABLISHED line remote ID
            for bline in block_lines:
                if 'ESTABLISHED' in bline:
                    est_rem = re.search(r'\.\.\.[^\[\n\r]*\[([^\]]+)\]', bline)
                    if est_rem:
                        raw_id = est_rem.group(1).strip()
                        if ':' in raw_id and not raw_id.startswith('::'):
                            parts = raw_id.split(':')
                            candidates.append(parts[0].strip("'\" \t"))
                        candidates.append(raw_id.strip("'\" \t"))
                        
            # Match candidate against database users
            matched_user = None
            for cand in candidates:
                cand_clean = cand
                if '\\' in cand_clean:
                    cand_clean = cand_clean.split('\\')[-1]
                if '/' in cand_clean:
                    cand_clean = cand_clean.split('/')[-1]
                if '@' in cand_clean and cand_clean not in db_users_set:
                    cand_clean = cand_clean.split('@')[0]
                    
                if cand in db_users_set:
                    matched_user = cand
                    break
                elif cand_clean in db_users_set:
                    matched_user = cand_clean
                    break
                elif cand.lower() in db_users_lower:
                    matched_user = db_users_lower[cand.lower()]
                    break
                elif cand_clean.lower() in db_users_lower:
                    matched_user = db_users_lower[cand_clean.lower()]
                    break
                    
            if not matched_user:
                continue
                
            # Extract traffic bytes for this SA
            bytes_in = 0
            bytes_out = 0
            for bline in block_lines:
                bm = re.search(r'(\d+)\s+bytes_i.*?(\d+)\s+bytes_o', bline)
                if bm:
                    bytes_in += int(bm.group(1))
                    bytes_out += int(bm.group(2))
                    
            # Extract VIP
            vip = None
            for bline in block_lines:
                vip_m = re.search(r'===\s*(10\.\d+\.\d+\.\d+|(?:\d{1,3}\.){3}\d{1,3})', bline)
                if vip_m:
                    vip = vip_m.group(1)
                    break
                vip_fallback = re.search(r'(?!0\.0\.0\.0)(\b10\.\d+\.\d+\.\d+\b)', bline)
                if vip_fallback:
                    vip = vip_fallback.group(1)
                    break
                    
            # Group per user
            if matched_user not in online:
                online[matched_user] = {
                    "username": matched_user,
                    "sa_ids": [sa_id],
                    "vips": [vip] if vip else [],
                    "bytes_in": bytes_in,
                    "bytes_out": bytes_out,
                    "bytes_total": bytes_in + bytes_out,
                    "device_count": 1,
                    "sas": {
                        sa_id: {
                            "sa_id": sa_id,
                            "bytes_in": bytes_in,
                            "bytes_out": bytes_out,
                            "bytes_total": bytes_in + bytes_out,
                            "vip": vip
                        }
                    }
                }
            else:
                if sa_id not in online[matched_user]["sa_ids"]:
                    online[matched_user]["sa_ids"].append(sa_id)
                if vip and vip not in online[matched_user]["vips"]:
                    online[matched_user]["vips"].append(vip)
                online[matched_user]["bytes_in"] += bytes_in
                online[matched_user]["bytes_out"] += bytes_out
                online[matched_user]["bytes_total"] += (bytes_in + bytes_out)
                online[matched_user]["sas"][sa_id] = {
                    "sa_id": sa_id,
                    "bytes_in": bytes_in,
                    "bytes_out": bytes_out,
                    "bytes_total": bytes_in + bytes_out,
                    "vip": vip
                }
                online[matched_user]["device_count"] = len(online[matched_user]["sa_ids"])
                
    except Exception as e:
        print(f"[!] Error parsing ipsec statusall: {e}", file=sys.stderr)
        
    return online

def get_online_users(ttl=1.5):
    global cached_online_users, cached_online_time
    now = time.time()
    with online_cache_lock:
        if (now - cached_online_time) < ttl and cached_online_users:
            return cached_online_users
            
    fresh_online = fetch_online_users_raw()
    with online_cache_lock:
        cached_online_users = fresh_online
        cached_online_time = now
    return fresh_online

last_seen_sa_bytes = {}

def accounting_daemon():
    global last_seen_sa_bytes
    while not shutdown_event.is_set():
        try:
            vpn_enabled = (get_system_config("vpn_enabled", "1") == "1")
            online = fetch_online_users_raw()
            if not vpn_enabled and online:
                disconnect_all_sas()
                online = {}

            now = datetime.datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            
            conn = get_db()
            cursor = conn.cursor()
            
            active_sa_ids = set()
            user_deltas = {}
            
            for username, data in online.items():
                for sa_id, sa_data in data.get("sas", {}).items():
                    active_sa_ids.add(sa_id)
                    curr_bytes = sa_data["bytes_total"]
                    prev_bytes = last_seen_sa_bytes.get(sa_id, 0)
                    
                    delta = 0
                    if curr_bytes >= prev_bytes:
                        delta = curr_bytes - prev_bytes
                    else:
                        delta = curr_bytes
                        
                    last_seen_sa_bytes[sa_id] = curr_bytes
                    if delta > 0:
                        user_deltas[username] = user_deltas.get(username, 0) + delta
                        
                cursor.execute("UPDATE users SET last_online_at = ? WHERE username = ?", (now_str, username))
                
            for username, delta in user_deltas.items():
                cursor.execute("""
                    UPDATE users 
                    SET used_traffic_bytes = COALESCE(used_traffic_bytes, 0) + ?
                    WHERE username = ?
                """, (delta, username))
                
            for sa_id in list(last_seen_sa_bytes.keys()):
                if sa_id not in active_sa_ids:
                    del last_seen_sa_bytes[sa_id]
                    
            conn.commit()
            
            cursor.execute("SELECT id, username, max_traffic_gb, used_traffic_bytes, expire_date, is_active, max_devices FROM users")
            users = cursor.fetchall()
            
            should_resync = False
            for u in users:
                is_active = u["is_active"] if u["is_active"] is not None else 1
                needs_disable = False
                
                if u["expire_date"]:
                    try:
                        exp_dt = datetime.datetime.strptime(u["expire_date"], "%Y-%m-%d %H:%M:%S")
                        if now > exp_dt:
                            needs_disable = True
                    except Exception:
                        pass
                
                if u["max_traffic_gb"] and u["max_traffic_gb"] > 0:
                    max_bytes = u["max_traffic_gb"] * 1024 * 1024 * 1024
                    if (u["used_traffic_bytes"] or 0) >= max_bytes:
                        needs_disable = True
                        
                if needs_disable and is_active == 1:
                    cursor.execute("UPDATE users SET is_active = 0 WHERE id = ?", (u["id"],))
                    should_resync = True
                    disconnect_user_sas(u["username"], online)
                elif is_active == 1 and u["username"] in online:
                    # Enforce per-user simultaneous device limit (1-10)
                    user_max_dev = u["max_devices"] if u["max_devices"] is not None and u["max_devices"] > 0 else 10
                    try:
                        user_max_dev = max(1, min(10, int(user_max_dev)))
                    except (ValueError, TypeError):
                        user_max_dev = 10
                    disconnect_excess_sas(u["username"], user_max_dev, online)
                            
            conn.commit()
            conn.close()
            
            if should_resync:
                sync_ipsec_secrets()
                
        except Exception as e:
            print(f"[!] Daemon exception: {e}", file=sys.stderr)
            
        if shutdown_event.wait(2):
            break

daemon_lock_handle = None

def start_accounting_daemon():
    global daemon_lock_handle
    lock_file = "/tmp/ike_accounting_daemon.lock"
    try:
        daemon_lock_handle = open(lock_file, "w")
        fcntl.flock(daemon_lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, BlockingIOError, PermissionError):
        # Another process holds the lock; do not start duplicate daemon
        return
    
    t = threading.Thread(target=accounting_daemon, daemon=True)
    t.start()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_user = session.get("admin_user")
        if not session.get("logged_in") or not admin_user:
            is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
            if is_ajax:
                return jsonify({"success": False, "error": "Unauthorized or session expired", "redirect": url_for("login")}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def format_bytes_val(bytes_val):
    if bytes_val is None:
        return "0 B"
    try:
        b = float(bytes_val)
    except Exception:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024.0 or unit == 'TB':
            return f"{b:.2f} {unit}"
        b /= 1024.0
    return f"{b:.2f} GB"

def format_last_online_str(last_seen_str):
    if not last_seen_str:
        return None
    try:
        dt = datetime.datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.datetime.now()
        diff = (now - dt).total_seconds()
        if diff < 60:
            return "Just now"
        elif diff < 3600:
            mins = int(diff // 60)
            return f"{mins}m ago"
        elif diff < 86400:
            hours = int(diff // 3600)
            return f"{hours}h ago"
        else:
            days = int(diff // 86400)
            return f"{days}d ago"
    except Exception:
        return last_seen_str[:16]

def calc_remaining_days(expire_date_str):
    if not expire_date_str:
        return ""
    try:
        exp_dt = datetime.datetime.strptime(expire_date_str, "%Y-%m-%d %H:%M:%S")
        diff = exp_dt - datetime.datetime.now()
        if diff.total_seconds() <= 0:
            return 0
        return max(0, diff.days + (1 if diff.seconds > 0 else 0))
    except Exception:
        return ""

@app.template_filter('format_bytes')
def format_bytes(bytes_val):
    return format_bytes_val(bytes_val)

@app.template_filter('traffic_percent')
def traffic_percent(used_bytes, max_gb):
    try:
        if not max_gb or float(max_gb) <= 0:
            return 0
        if not used_bytes or float(used_bytes) <= 0:
            return 0
        max_bytes = float(max_gb) * 1024 * 1024 * 1024
        pct = (float(used_bytes) / max_bytes) * 100
        return min(round(pct, 1), 100)
    except Exception:
        return 0

@app.template_filter('time_remaining')
def time_remaining(expire_date_str):
    if not expire_date_str:
        return "Unlimited"
    try:
        exp_dt = datetime.datetime.strptime(expire_date_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.datetime.now()
        if now >= exp_dt:
            return "Expired"
        diff = exp_dt - now
        days = diff.days
        hours = diff.seconds // 3600
        if days > 0:
            return f"{days}d {hours}h left"
        return f"{hours}h left"
    except Exception:
        return "Unlimited"

@app.template_filter('format_last_seen')
def format_last_seen(last_seen_str):
    return format_last_online_str(last_seen_str)

@app.template_filter('get_remaining_days')
def get_remaining_days_filter(expire_date_str):
    return calc_remaining_days(expire_date_str)

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in") and session.get("admin_user"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM admin WHERE username = ?", (username,))
            admin = cursor.fetchone()
            conn.close()
            
            if admin and check_password_hash(admin["password_hash"], password):
                session.permanent = True
                session["logged_in"] = True
                session["admin_id"] = admin["id"]
                session["admin_user"] = admin["username"]
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid username or password!", "danger")
        except Exception as e:
            flash(f"Login error: {e}", "danger")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

def format_user_payload(u, online):
    uname = u.get("username") if isinstance(u, dict) else u["username"]
    is_on = uname in online
    online_info = online.get(uname, {})
    dev_cnt = online_info.get("device_count", 1) if is_on else 0
    last_seen_raw = u.get("last_online_at") if isinstance(u, dict) else u["last_online_at"]
    last_seen_formatted = format_last_online_str(last_seen_raw)
    used_bytes = (u.get("used_traffic_bytes") if isinstance(u, dict) else u["used_traffic_bytes"]) or 0
    max_gb = (u.get("max_traffic_gb") if isinstance(u, dict) else u["max_traffic_gb"]) or 0
    exp_date = (u.get("expire_date") if isinstance(u, dict) else u["expire_date"]) or ""
    is_act = u.get("is_active") if isinstance(u, dict) else u["is_active"]
    is_act = 1 if is_act is None else int(is_act)
    note = (u.get("note") if isinstance(u, dict) else u["note"]) or ""
    u_id = u.get("id") if isinstance(u, dict) else u["id"]
    u_pwd = u.get("password") if isinstance(u, dict) else u["password"]
    raw_max_dev = u.get("max_devices") if isinstance(u, dict) else u["max_devices"]
    try:
        max_dev = int(raw_max_dev) if raw_max_dev is not None else 10
        max_dev = max(1, min(10, max_dev))
    except (ValueError, TypeError):
        max_dev = 10
    
    return {
        "id": u_id,
        "username": uname,
        "password": u_pwd,
        "is_online": is_on,
        "device_count": dev_cnt,
        "last_online_at": last_seen_raw or "",
        "last_seen_formatted": last_seen_formatted or "",
        "used_traffic_bytes": used_bytes,
        "used_traffic_formatted": format_bytes_val(used_bytes),
        "max_traffic_gb": max_gb,
        "traffic_percent": traffic_percent(used_bytes, max_gb),
        "expire_date": exp_date,
        "remaining_days": calc_remaining_days(exp_date),
        "time_remaining": time_remaining(exp_date),
        "is_active": is_act,
        "max_devices": max_dev,
        "note": note
    }

@app.route("/")
@login_required
def dashboard():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY id DESC")
        users = cursor.fetchall()
        conn.close()
    except Exception as e:
        users = []
        print(f"[!] Error fetching users: {e}", file=sys.stderr)
    
    online = get_online_users()
    
    total_users = len(users)
    active_users = sum(1 for u in users if (u["is_active"] or 0) == 1)
    online_count = sum(1 for u in users if u["username"] in online)
    total_traffic_bytes = sum((u["used_traffic_bytes"] or 0) for u in users)
    sys_metrics = get_system_metrics()
    users_formatted = [format_user_payload(u, online) for u in users]
    
    return render_template("dashboard.html", 
                           users=users, 
                           users_json=json.dumps(users_formatted),
                           online=online,
                           total_users=total_users,
                           active_users=active_users,
                           online_count=online_count,
                           total_traffic_bytes=total_traffic_bytes,
                           sys=sys_metrics,
                           server_domain=SERVER_DOMAIN)

@app.route("/api/stream")
@login_required
def sse_stream():
    def event_generator():
        while not shutdown_event.is_set():
            try:
                online = get_online_users()
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users ORDER BY id DESC")
                users = [dict(u) for u in cursor.fetchall()]
                conn.close()

                total_users = len(users)
                active_users = sum(1 for u in users if (u.get("is_active") or 0) == 1)
                online_count = sum(1 for u in users if u["username"] in online)
                total_traffic_bytes = sum((u.get("used_traffic_bytes") or 0) for u in users)
                sys_metrics = get_system_metrics()

                user_list = [format_user_payload(u, online) for u in users]

                payload = {
                    "stats": {
                        "total_users": total_users,
                        "active_users": active_users,
                        "online_count": online_count,
                        "total_traffic": format_bytes_val(total_traffic_bytes)
                    },
                    "sys": sys_metrics,
                    "vpn_enabled": (get_system_config("vpn_enabled", "1") == "1"),
                    "users": user_list
                }

                yield f"data: {json.dumps(payload)}\n\n"
            except GeneratorExit:
                break
            except Exception as e:
                print(f"[!] Error in SSE generator: {e}", file=sys.stderr)
                
            if shutdown_event.wait(2):
                break

    response = Response(stream_with_context(event_generator()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response

@app.route("/user/add", methods=["POST"])
@login_required
def add_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    
    raw_traffic = request.form.get("max_traffic_gb", "").strip()
    max_traffic_gb = float(raw_traffic) if raw_traffic else 0.0
    
    raw_days = request.form.get("duration_days", "").strip()
    duration_days = int(raw_days) if raw_days else 0

    raw_devices = request.form.get("max_devices", "10").strip()
    try:
        max_devices = int(raw_devices) if raw_devices else 10
        max_devices = max(1, min(10, max_devices))
    except ValueError:
        max_devices = 10
    
    note = request.form.get("note", "").strip()
    
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
    
    if not username or not password:
        if is_ajax:
            return jsonify({"success": False, "error": "Username and password are required!"}), 400
        flash("Username and password are required!", "danger")
        return redirect(url_for("dashboard"))

    # Case-insensitive uniqueness check
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        existing_user = cursor.fetchone()
        if existing_user:
            conn.close()
            if is_ajax:
                return jsonify({"success": False, "error": f"User '{username}' already exists!"}), 400
            flash(f"User '{username}' already exists!", "danger")
            return redirect(url_for("dashboard"))
    except Exception as e:
        pass
        
    expire_date = None
    if duration_days > 0:
        expire_date = (datetime.datetime.now() + datetime.timedelta(days=duration_days)).strftime("%Y-%m-%d %H:%M:%S")
        
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, max_traffic_gb, used_traffic_bytes, created_at, expire_date, is_active, note, last_online_at, max_devices)
            VALUES (?, ?, ?, 0, ?, ?, 1, ?, NULL, ?)
        """, (username, password, max_traffic_gb, created_at, expire_date, note, max_devices))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        sync_ipsec_secrets()
        
        traffic_display = f"{max_traffic_gb} GB" if max_traffic_gb > 0 else "Unlimited"
        expire_display = f"{duration_days} Days" if duration_days > 0 else "Lifetime (Unlimited)"
        
        if is_ajax:
            return jsonify({
                "success": True,
                "user_id": user_id,
                "username": username,
                "password": password,
                "server": SERVER_DOMAIN,
                "max_traffic": traffic_display,
                "max_traffic_gb": max_traffic_gb,
                "expire": expire_display,
                "expire_date": expire_date or "",
                "remaining_days": duration_days if duration_days > 0 else "",
                "max_devices": max_devices,
                "note": note
            })
            
        flash(f"User '{username}' added successfully!", "success")
    except sqlite3.IntegrityError:
        if is_ajax:
            return jsonify({"success": False, "error": f"User '{username}' already exists!"}), 400
        flash(f"User '{username}' already exists!", "danger")
    except Exception as e:
        if is_ajax:
            return jsonify({"success": False, "error": f"Error adding user: {e}"}), 500
        flash(f"Error adding user: {e}", "danger")
        
    return redirect(url_for("dashboard"))

@app.route("/user/edit/<int:user_id>", methods=["POST"])
@login_required
def edit_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
    
    if not user:
        conn.close()
        if is_ajax:
            return jsonify({"success": False, "error": "User not found!"}), 404
        flash("User not found!", "danger")
        return redirect(url_for("dashboard"))
        
    change_pwd = request.form.get("change_password") == "yes"
    raw_pwd = request.form.get("password", "").strip()
    
    if change_pwd and raw_pwd:
        new_password = raw_pwd
        pwd_was_changed = True
    else:
        new_password = user["password"]
        pwd_was_changed = False
        
    raw_traffic = request.form.get("max_traffic_gb", "").strip()
    if raw_traffic == "":
        max_traffic_gb = 0.0
        traffic_display = "Unlimited"
    else:
        try:
            val = float(raw_traffic)
            max_traffic_gb = 0.0001 if val == 0 else val
            traffic_display = f"{val} GB" if val > 0 else "0 GB (Disabled)"
        except ValueError:
            max_traffic_gb = user["max_traffic_gb"]
            traffic_display = f"{user['max_traffic_gb']} GB" if user['max_traffic_gb'] > 0 else "Unlimited"
            
    raw_days = request.form.get("duration_days", "").strip()
    if raw_days == "":
        new_expire = None
        expire_display = "Lifetime (Unlimited)"
        time_rem = "Unlimited"
        rem_days = ""
    else:
        try:
            days_val = int(raw_days)
            if days_val == 0:
                new_expire = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
                expire_display = "Expired"
                time_rem = "Expired"
                rem_days = 0
            else:
                new_expire = (datetime.datetime.now() + datetime.timedelta(days=days_val)).strftime("%Y-%m-%d %H:%M:%S")
                expire_display = f"{days_val} Days"
                time_rem = f"{days_val}d left"
                rem_days = days_val
        except ValueError:
            new_expire = user["expire_date"]
            expire_display = calc_remaining_days(user["expire_date"])
            time_rem = time_remaining(user["expire_date"])
            rem_days = calc_remaining_days(user["expire_date"])

    raw_devices = request.form.get("max_devices", "").strip()
    if raw_devices == "":
        existing_dev = user["max_devices"] if ("max_devices" in user.keys() and user["max_devices"] is not None) else 10
        try:
            max_devices = max(1, min(10, int(existing_dev)))
        except (ValueError, TypeError):
            max_devices = 10
    else:
        try:
            val_dev = int(raw_devices)
            max_devices = max(1, min(10, val_dev))
        except ValueError:
            existing_dev = user["max_devices"] if ("max_devices" in user.keys() and user["max_devices"] is not None) else 10
            max_devices = max(1, min(10, int(existing_dev or 10)))
            
    note = request.form.get("note", "").strip()
    
    query = """
        UPDATE users 
        SET password = ?, max_traffic_gb = ?, expire_date = ?, note = ?, max_devices = ?
        WHERE id = ?
    """
    params = [new_password, max_traffic_gb, new_expire, note, max_devices, user_id]
    
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    
    sync_ipsec_secrets()
    if pwd_was_changed:
        disconnect_user_sas(user["username"])
    else:
        disconnect_excess_sas(user["username"], max_devices)
    
    if is_ajax:
        return jsonify({
            "success": True,
            "user_id": user_id,
            "password_changed": pwd_was_changed,
            "username": user["username"],
            "password": new_password,
            "server": SERVER_DOMAIN,
            "max_traffic": traffic_display,
            "max_traffic_gb": max_traffic_gb,
            "expire": expire_display,
            "time_remaining": time_rem,
            "expire_date": new_expire or "",
            "remaining_days": rem_days,
            "max_devices": max_devices,
            "note": note
        })
        
    flash(f"User '{user['username']}' updated successfully!", "success")
    return redirect(url_for("dashboard"))

@app.route("/user/toggle/<int:user_id>", methods=["GET", "POST"])
@login_required
def toggle_user(user_id):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, is_active FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if user:
        new_state = 0 if (user["is_active"] or 0) == 1 else 1
        cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_state, user_id))
        conn.commit()
        conn.close()
        sync_ipsec_secrets()
        
        if new_state == 0:
            disconnect_user_sas(user["username"])
                    
        status_str = "Enabled" if new_state == 1 else "Disabled"
        if is_ajax:
            return jsonify({
                "success": True,
                "user_id": user_id,
                "is_active": new_state,
                "username": user["username"],
                "message": f"User '{user['username']}' is now {status_str}."
            })
        flash(f"User '{user['username']}' is now {status_str}.", "info")
    else:
        conn.close()
        if is_ajax:
            return jsonify({"success": False, "error": "User not found!"}), 404
        flash("User not found!", "danger")
    return redirect(url_for("dashboard"))

@app.route("/user/delete/<int:user_id>")
@login_required
def delete_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if user:
        username = user["username"]
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        sync_ipsec_secrets()
        disconnect_user_sas(username)
                
        flash(f"User '{username}' deleted successfully!", "warning")
    else:
        conn.close()
    return redirect(url_for("dashboard"))

# ================= Admin Management Routes =================

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
    if request.method == "POST":
        curr_pass = request.form.get("current_password", "").strip()
        new_pass = request.form.get("new_password", "").strip()
        confirm_pass = request.form.get("confirm_password", "").strip()
        
        if not curr_pass or not new_pass:
            if is_ajax:
                return jsonify({"success": False, "error": "All password fields are required!"}), 400
            flash("All password fields are required!", "danger")
            return redirect(url_for("settings"))
            
        if new_pass != confirm_pass:
            if is_ajax:
                return jsonify({"success": False, "error": "New passwords do not match!"}), 400
            flash("New passwords do not match!", "danger")
            return redirect(url_for("settings"))

        if len(new_pass) < 4:
            if is_ajax:
                return jsonify({"success": False, "error": "Password must be at least 4 characters long!"}), 400
            flash("Password must be at least 4 characters long!", "danger")
            return redirect(url_for("settings"))
            
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin WHERE username = ?", (session["admin_user"],))
        admin = cursor.fetchone()
        
        if admin and check_password_hash(admin["password_hash"], curr_pass):
            new_hash = generate_password_hash(new_pass)
            cursor.execute("UPDATE admin SET password_hash = ? WHERE id = ?", (new_hash, admin["id"]))
            conn.commit()
            conn.close()
            if is_ajax:
                return jsonify({"success": True, "message": "Admin password updated successfully!"})
            flash("Admin password updated successfully!", "success")
        else:
            conn.close()
            if is_ajax:
                return jsonify({"success": False, "error": "Current password is incorrect!"}), 400
            flash("Current password is incorrect!", "danger")
        return redirect(url_for("settings"))
        
    vpn_status = (get_system_config("vpn_enabled", "1") == "1")
    return render_template("settings.html", vpn_enabled=vpn_status)

@app.route("/settings/toggle-vpn", methods=["POST"])
@login_required
def toggle_vpn_service():
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
    current_status = (get_system_config("vpn_enabled", "1") == "1")
    new_status = not current_status
    set_system_config("vpn_enabled", "1" if new_status else "0")
    sync_ipsec_secrets()
    if not new_status:
        disconnect_all_sas()
        
    status_text = "enabled" if new_status else "disabled (Maintenance Mode)"
    msg = f"VPN Service is now {status_text}."
    if is_ajax:
        return jsonify({
            "success": True,
            "vpn_enabled": new_status,
            "message": msg
        })
    flash(msg, "success" if new_status else "warning")
    return redirect(url_for("settings"))

@app.route("/admin/add", methods=["POST"])
@login_required
def add_admin():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    confirm = request.form.get("confirm_password", "").strip()
    
    if not username or not password:
        flash("Username and password are required!", "danger")
        return redirect(url_for("settings"))
        
    if password != confirm:
        flash("Passwords do not match!", "danger")
        return redirect(url_for("settings"))
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO admin (username, password_hash, created_at) VALUES (?, ?, ?)", 
                       (username, generate_password_hash(password), now))
        conn.commit()
        conn.close()
        flash(f"Administrator '{username}' created successfully!", "success")
    except sqlite3.IntegrityError:
        flash(f"Administrator with username '{username}' already exists!", "danger")
    except Exception as e:
        flash(f"Error creating admin: {e}", "danger")
        
    return redirect(url_for("settings"))

@app.route("/admin/edit-password/<int:admin_id>", methods=["POST"])
@login_required
def edit_admin_password(admin_id):
    new_password = request.form.get("new_password", "").strip()
    confirm = request.form.get("confirm_password", "").strip()
    
    if not new_password or new_password != confirm:
        flash("Passwords are empty or do not match!", "danger")
        return redirect(url_for("settings"))
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admin WHERE id = ?", (admin_id,))
    target_admin = cursor.fetchone()
    
    if not target_admin:
        conn.close()
        flash("Administrator not found!", "danger")
        return redirect(url_for("settings"))
        
    cursor.execute("UPDATE admin SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), admin_id))
    conn.commit()
    conn.close()
    
    flash(f"Password updated for administrator '{target_admin['username']}'!", "success")
    return redirect(url_for("settings"))

@app.route("/admin/delete/<int:admin_id>", methods=["POST"])
@login_required
def delete_admin(admin_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM admin")
    total_admins = cursor.fetchone()["cnt"]
    
    if total_admins <= 1:
        conn.close()
        flash("Cannot delete the only remaining administrator!", "danger")
        return redirect(url_for("settings"))
        
    cursor.execute("SELECT * FROM admin WHERE id = ?", (admin_id,))
    target_admin = cursor.fetchone()
    
    if not target_admin:
        conn.close()
        flash("Administrator not found!", "danger")
        return redirect(url_for("settings"))
        
    is_self = (target_admin["username"] == session.get("admin_user"))
    
    cursor.execute("DELETE FROM admin WHERE id = ?", (admin_id,))
    conn.commit()
    conn.close()
    
    if is_self:
        session.clear()
        flash("Your administrator account has been deleted.", "info")
        return redirect(url_for("login"))
        
    flash(f"Administrator '{target_admin['username']}' deleted successfully.", "warning")
    return redirect(url_for("settings"))

# Initialize DB and run daemon
init_db()
sync_ipsec_secrets()
start_accounting_daemon()

if __name__ == "__main__":
    print(f"[*] Starting IKE-UI Panel on 0.0.0.0:{PANEL_PORT}...")
    app.run(host="0.0.0.0", port=PANEL_PORT, debug=False)

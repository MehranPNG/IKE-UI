#!/usr/bin/env python3
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
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, stream_with_context
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", "/etc/strongswan-panel/panel.db")
SECRETS_PATH = os.environ.get("SECRETS_PATH", "/etc/ipsec.secrets")
SECRET_KEY_PATH = os.environ.get("SECRET_KEY_PATH", "/etc/strongswan-panel/secret.key")
SERVER_DOMAIN = os.environ.get("SERVER_DOMAIN", "faghir.seytann.com")
PANEL_PORT = int(os.environ.get("PANEL_PORT", 8000))

def get_persistent_secret_key():
    os.makedirs(os.path.dirname(SECRET_KEY_PATH), exist_ok=True)
    if os.path.exists(SECRET_KEY_PATH):
        try:
            with open(SECRET_KEY_PATH, "rb") as f:
                key = f.read()
                if len(key) >= 16:
                    return key
        except Exception:
            pass
    new_key = os.urandom(32)
    try:
        with open(SECRET_KEY_PATH, "wb") as f:
            f.write(new_key)
        os.chmod(SECRET_KEY_PATH, 0o600)
    except Exception as e:
        print(f"[!] Warning: Could not save secret.key: {e}", file=sys.stderr)
    return new_key

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

app.secret_key = get_persistent_secret_key()
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

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

    return {
        "cpu_percent": cpu_pct,
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
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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

def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """)
        
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
            last_online_at TEXT
        )
        """)
        
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN last_online_at TEXT")
        except Exception:
            pass
        
        cursor.execute("SELECT * FROM admin WHERE username = 'admin'")
        if not cursor.fetchone():
            default_hash = generate_password_hash("admin123")
            cursor.execute("INSERT INTO admin (username, password_hash) VALUES ('admin', ?)", (default_hash,))
            
        cursor.execute("SELECT * FROM users WHERE username = 'mehran'")
        if not cursor.fetchone():
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO users (username, password, max_traffic_gb, used_traffic_bytes, created_at, expire_date, is_active, note, last_online_at)
                VALUES ('mehran', '12345678', 0, 0, ?, NULL, 1, 'Default Admin VPN User', NULL)
            """, (now,))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] Error in init_db: {e}", file=sys.stderr)

def sync_ipsec_secrets():
    try:
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
                active_lines.append(f'{u["username"]} : EAP "{u["password"]}"')
                
        with open(SECRETS_PATH, "w") as f:
            f.write("\n".join(active_lines) + "\n")
        os.chmod(SECRETS_PATH, 0o600)
        
        subprocess.run(["ipsec", "rereadsecrets"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[!] Error syncing ipsec.secrets: {e}", file=sys.stderr)

def get_online_users():
    online = {}
    db_users = get_db_usernames()
    
    try:
        res = subprocess.run(["ipsec", "statusall"], capture_output=True, text=True, check=False)
        output = res.stdout or ""
        
        current_user = None
        current_sa_id = None
        
        for line in output.splitlines():
            est_match = re.search(r'\[(\d+)\]:\s+ESTABLISHED\s+([^,]+),\s+.*?\.\.\..*?\[([^\]]+)\]\s*$', line)
            if est_match:
                current_sa_id = est_match.group(1)
                raw_user = est_match.group(3).strip()
                
                if raw_user in db_users:
                    current_user = raw_user
                    if current_user not in online:
                        online[current_user] = {
                            "username": current_user,
                            "sa_ids": [current_sa_id],
                            "vips": [],
                            "bytes_in": 0,
                            "bytes_out": 0,
                            "bytes_total": 0
                        }
                    else:
                        if current_sa_id not in online[current_user]["sa_ids"]:
                            online[current_user]["sa_ids"].append(current_sa_id)
                else:
                    current_user = None
                continue
                
            if current_user and current_user in online:
                bytes_match = re.search(r'(\d+)\s+bytes_i.*?(\d+)\s+bytes_o', line)
                if bytes_match:
                    b_in = int(bytes_match.group(1))
                    b_out = int(bytes_match.group(2))
                    online[current_user]["bytes_in"] += b_in
                    online[current_user]["bytes_out"] += b_out
                    online[current_user]["bytes_total"] += (b_in + b_out)
                    
                vip_match = re.search(r'(\b10\.\d+\.\d+\.\d+\b)', line)
                if not vip_match:
                    vip_match = re.search(r'(?!0\.0\.0\.0)(\d+\.\d+\.\d+\.\d+)/\d+', line)
                if vip_match:
                    vip_ip = vip_match.group(1)
                    if vip_ip not in online[current_user]["vips"]:
                        online[current_user]["vips"].append(vip_ip)
                        
        for u, data in online.items():
            data["device_count"] = max(len(data["vips"]), 1)
    except Exception as e:
        print(f"[!] Error parsing ipsec statusall: {e}", file=sys.stderr)
    return online

last_seen_bytes = {}

def accounting_daemon():
    global last_seen_bytes
    while True:
        try:
            online = get_online_users()
            now = datetime.datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            
            conn = get_db()
            cursor = conn.cursor()
            
            for username, data in online.items():
                current_total = data["bytes_total"]
                prev_total = last_seen_bytes.get(username, 0)
                
                delta = 0
                if current_total >= prev_total:
                    delta = current_total - prev_total
                else:
                    delta = current_total
                    
                last_seen_bytes[username] = current_total
                
                cursor.execute("""
                    UPDATE users 
                    SET used_traffic_bytes = COALESCE(used_traffic_bytes, 0) + ?,
                        last_online_at = ?
                    WHERE username = ?
                """, (delta, now_str, username))
            
            for u in list(last_seen_bytes.keys()):
                if u not in online:
                    del last_seen_bytes[u]
                    
            conn.commit()
            
            cursor.execute("SELECT id, username, max_traffic_gb, used_traffic_bytes, expire_date, is_active FROM users")
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
                    if u["username"] in online:
                        for sa_id in online[u["username"]].get("sa_ids", []):
                            subprocess.run(["ipsec", "down", f"ikev2-vpn[{sa_id}]"], check=False)
                            
            conn.commit()
            conn.close()
            
            if should_resync:
                sync_ipsec_secrets()
                
        except Exception as e:
            print(f"[!] Daemon exception: {e}", file=sys.stderr)
            
        time.sleep(5)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
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
    if session.get("logged_in"):
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
                session["admin_user"] = username
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
    
    return render_template("dashboard.html", 
                           users=users, 
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
        while True:
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

                user_list = []
                for u in users:
                    is_on = u["username"] in online
                    online_info = online.get(u["username"], {})
                    dev_cnt = online_info.get("device_count", 1) if is_on else 0
                    last_seen_formatted = format_last_online_str(u.get("last_online_at"))
                    
                    user_list.append({
                        "id": u["id"],
                        "username": u["username"],
                        "is_online": is_on,
                        "device_count": dev_cnt,
                        "last_online_at": u.get("last_online_at"),
                        "last_seen_formatted": last_seen_formatted,
                        "used_traffic_bytes": u.get("used_traffic_bytes") or 0,
                        "used_traffic_formatted": format_bytes_val(u.get("used_traffic_bytes") or 0),
                        "max_traffic_gb": u.get("max_traffic_gb") or 0,
                        "traffic_percent": traffic_percent(u.get("used_traffic_bytes") or 0, u.get("max_traffic_gb")),
                        "expire_date": u.get("expire_date") or "",
                        "remaining_days": calc_remaining_days(u.get("expire_date")),
                        "time_remaining": time_remaining(u.get("expire_date")),
                        "is_active": u.get("is_active") if u.get("is_active") is not None else 1,
                        "note": u.get("note") or ""
                    })

                payload = {
                    "stats": {
                        "total_users": total_users,
                        "active_users": active_users,
                        "online_count": online_count,
                        "total_traffic": format_bytes_val(total_traffic_bytes)
                    },
                    "sys": sys_metrics,
                    "users": user_list
                }

                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as e:
                print(f"[!] Error in SSE generator: {e}", file=sys.stderr)
                
            time.sleep(2)

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
    
    note = request.form.get("note", "").strip()
    
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
    
    if not username or not password:
        if is_ajax:
            return jsonify({"success": False, "error": "Username and password are required!"}), 400
        flash("Username and password are required!", "danger")
        return redirect(url_for("dashboard"))
        
    expire_date = None
    if duration_days > 0:
        expire_date = (datetime.datetime.now() + datetime.timedelta(days=duration_days)).strftime("%Y-%m-%d %H:%M:%S")
        
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, max_traffic_gb, used_traffic_bytes, created_at, expire_date, is_active, note, last_online_at)
            VALUES (?, ?, ?, 0, ?, ?, 1, ?, NULL)
        """, (username, password, max_traffic_gb, created_at, expire_date, note))
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
            
    note = request.form.get("note", "").strip()
    
    query = """
        UPDATE users 
        SET password = ?, max_traffic_gb = ?, expire_date = ?, note = ?
        WHERE id = ?
    """
    params = [new_password, max_traffic_gb, new_expire, note, user_id]
    
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    
    sync_ipsec_secrets()
    
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
            "note": note
        })
        
    flash(f"User '{user['username']}' updated successfully!", "success")
    return redirect(url_for("dashboard"))

@app.route("/user/toggle/<int:user_id>")
@login_required
def toggle_user(user_id):
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
            online = get_online_users()
            if user["username"] in online:
                for sa_id in online[user["username"]].get("sa_ids", []):
                    subprocess.run(["ipsec", "down", f"ikev2-vpn[{sa_id}]"], check=False)
                    
        status_str = "Enabled" if new_state == 1 else "Disabled"
        flash(f"User '{user['username']}' is now {status_str}.", "info")
    else:
        conn.close()
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
        
        online = get_online_users()
        if username in online:
            for sa_id in online[username].get("sa_ids", []):
                subprocess.run(["ipsec", "down", f"ikev2-vpn[{sa_id}]"], check=False)
                
        flash(f"User '{username}' deleted successfully!", "warning")
    else:
        conn.close()
    return redirect(url_for("dashboard"))

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        curr_pass = request.form.get("current_password", "").strip()
        new_pass = request.form.get("new_password", "").strip()
        confirm_pass = request.form.get("confirm_password", "").strip()
        
        if new_pass != confirm_pass:
            flash("New passwords do not match!", "danger")
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
            flash("Admin password updated successfully!", "success")
        else:
            conn.close()
            flash("Current password is incorrect!", "danger")
            
    return render_template("settings.html")

init_db()
sync_ipsec_secrets()

daemon_thread = threading.Thread(target=accounting_daemon, daemon=True)
daemon_thread.start()

if __name__ == "__main__":
    print(f"[*] Starting IKE-UI Panel on 0.0.0.0:{PANEL_PORT}...")
    app.run(host="0.0.0.0", port=PANEL_PORT, debug=False)

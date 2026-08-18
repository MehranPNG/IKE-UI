#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/MehranPNG/IKE-UI.git"
APP_VERSION="1.4.1"
INSTALL_DIR="/opt/ike-ui"
PANEL_DIR="${INSTALL_DIR}/panel"
DB_DIR="/etc/strongswan-panel"
DB_PATH="${DB_DIR}/panel.db"
SECRETS_PATH="/etc/ipsec.secrets"
SECRET_KEY_PATH="${DB_DIR}/secret.key"
BIN_PATH="/usr/local/bin/ike-ui"
ALT_BIN_PATH="/usr/bin/ike-ui"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

show_banner() {
    clear 2>/dev/null || true
    local cur_ver="$APP_VERSION"
    if [ -f "${INSTALL_DIR}/install.sh" ]; then
        local disk_ver
        disk_ver=$(grep -oP '^APP_VERSION=["\x27]?\K[^"\x27\s]+' "${INSTALL_DIR}/install.sh" 2>/dev/null || true)
        if [ -n "$disk_ver" ]; then
            cur_ver="$disk_ver"
            APP_VERSION="1.4.1"
        fi
    fi
    echo -e "${PURPLE}${BOLD}"
    cat << BANNER
  ██╗██╗  ██╗███████╗      ██╗   ██╗██╗
  ██║██║ ██╔╝██╔════╝      ██║   ██║██║
  ██║█████╔╝ █████╗  █████╗██║   ██║██║
  ██║██╔═██╗ ██╔══╝  ╚════╝██║   ██║██║
  ██║██║  ██╗███████╗      ╚██████╔╝██║
  ╚═╝╚═╝  ╚═╝╚══════╝       ╚═════╝ ╚═╝
         IKE-UI Manager v${cur_ver}
BANNER
    echo -e "${CYAN}====================================================${NC}"
    
    local panel_domain=""
    if [ -f /etc/systemd/system/ike-ui.service ]; then
        panel_domain=$(grep -oP 'Environment="SERVER_DOMAIN=\K[^"]+' /etc/systemd/system/ike-ui.service 2>/dev/null || true)
    fi
    if [ -z "$panel_domain" ] && [ -f /etc/nginx/sites-available/ike-ui ]; then
        panel_domain=$(grep -oP 'server_name\s+\K[^;]+' /etc/nginx/sites-available/ike-ui 2>/dev/null | head -n1 | tr -d ' ' || true)
    fi

    if [ -n "$panel_domain" ]; then
        local status_badge="${GREEN}● Online${NC}"
        if ! systemctl is-active --quiet ike-ui 2>/dev/null && ! systemctl is-active --quiet ikev2-panel 2>/dev/null; then
            status_badge="${RED}○ Stopped${NC}"
        fi
        echo -e " ${BOLD}Panel URL:${NC} ${CYAN}https://${panel_domain}${NC} [${status_badge}]"
        echo -e "${CYAN}====================================================${NC}"
    fi
    echo -e "${NC}"
}

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo -e "${RED}[X] Error: This script must be run as root (or with sudo).${NC}" >&2
        exit 1
    fi
}

check_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        echo -e "${RED}[X] Unsupported Linux distribution. Debian/Ubuntu is required.${NC}" >&2
        exit 1
    fi

    if [[ "$OS" != "ubuntu" && "$OS" != "debian" && "$OS" != "raspbian" && "$OS" != "kali" && "$OS" != "pop" && "$OS" != "linuxmint" ]]; then
        echo -e "${YELLOW}[!] Warning: Your OS ($OS) is not Debian/Ubuntu based.${NC}"
        echo -e "${YELLOW}    IKE-UI relies on apt-get for strongSwan and system services.${NC}"
        read -rp "Do you want to continue anyway? [y/N]: " confirm
        if [[ ! "$confirm" =~ ^[yY]([eE][sS])?$ ]]; then
            echo -e "${RED}Installation cancelled.${NC}"
            exit 1
        fi
    fi
}

detect_network() {
    NET_IFACE=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $5; exit}')
    if [ -z "$NET_IFACE" ]; then
        NET_IFACE=$(ip route show default 2>/dev/null | awk '{print $5; exit}')
    fi
    if [ -z "$NET_IFACE" ]; then
        NET_IFACE="eth0"
    fi

    SERVER_IP=$(curl -s4 --max-time 5 https://api.ipify.org || curl -s4 --max-time 5 https://ifconfig.me || echo "Unknown")
}

setup_cli_shortcut() {
    mkdir -p "$(dirname "$BIN_PATH")"
    cat > "$BIN_PATH" << 'CLI_EOF'
#!/usr/bin/env bash
exec /opt/ike-ui/install.sh "$@"
CLI_EOF
    chmod +x "$BIN_PATH"
    ln -sf "$BIN_PATH" "$ALT_BIN_PATH" 2>/dev/null || true
}

bootstrap_environment() {
    SCRIPT_SOURCE="${BASH_SOURCE[0]}"
    if [ -f "$SCRIPT_SOURCE" ]; then
        CURRENT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
    else
        CURRENT_DIR=""
    fi

    if [ "$CURRENT_DIR" != "$INSTALL_DIR" ]; then
        check_root
        show_banner
        check_os

        echo -e "${CYAN}[*] Installing base dependencies (git, curl, ca-certificates)...${NC}"
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -y
        apt-get install -y curl git ca-certificates tar iptables sudo

        echo -e "${CYAN}[*] Setting up IKE-UI in ${INSTALL_DIR}...${NC}"
        mkdir -p "$(dirname "$INSTALL_DIR")"

        if [ -d "$INSTALL_DIR/.git" ]; then
            cd "$INSTALL_DIR"
            git remote set-url origin "$REPO_URL" 2>/dev/null || true
            git fetch --all --tags --prune
            git reset --hard origin/main
        else
            if [ -d "$INSTALL_DIR" ]; then
                rm -rf "${INSTALL_DIR:?}"/*
            fi
            git clone -b main "$REPO_URL" "$INSTALL_DIR"
        fi

        chmod +x "${INSTALL_DIR}/install.sh"
        setup_cli_shortcut

        echo -e "${GREEN}[+] Initialization complete.${NC}"
        echo ""
        exec "${INSTALL_DIR}/install.sh" "$@"
    fi
}

apply_firewall() {
    detect_network
    iptables -t nat -C POSTROUTING -s 10.10.10.0/24 -o "$NET_IFACE" -j MASQUERADE 2>/dev/null || \
        iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o "$NET_IFACE" -j MASQUERADE

    iptables -C FORWARD -s 10.10.10.0/24 -j ACCEPT 2>/dev/null || \
        iptables -A FORWARD -s 10.10.10.0/24 -j ACCEPT

    iptables -C FORWARD -d 10.10.10.0/24 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || \
        iptables -A FORWARD -d 10.10.10.0/24 -m state --state RELATED,ESTABLISHED -j ACCEPT

    iptables -t mangle -C FORWARD -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1360 2>/dev/null || \
        iptables -t mangle -A FORWARD -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1360

    if command -v ufw >/dev/null 2>&1; then
        ufw allow 500/udp >/dev/null 2>&1 || true
        ufw allow 4500/udp >/dev/null 2>&1 || true
        ufw allow 80/tcp >/dev/null 2>&1 || true
        ufw allow 443/tcp >/dev/null 2>&1 || true
    fi
}

install_all() {
    show_banner
    detect_network

    echo -e "${YELLOW}[*] Primary Network Interface:${NC} ${BOLD}${NET_IFACE}${NC}"
    echo -e "${YELLOW}[*] Public IP Address:${NC} ${BOLD}${SERVER_IP}${NC}"
    echo ""

    if [ -n "$1" ]; then
        DOMAIN="$1"
    else
        read -rp "Enter Domain Name (e.g. vpn.example.com): " DOMAIN
    fi

    if [ -z "$DOMAIN" ]; then
        echo -e "${RED}[X] Error: Domain name cannot be empty.${NC}"
        exit 1
    fi

    echo ""
    read -rp "Enter Admin Username [default: admin]: " ADMIN_USER
    ADMIN_USER=${ADMIN_USER:-admin}

    read -rp "Enter Admin Password [default: admin123]: " ADMIN_PASS
    ADMIN_PASS=${ADMIN_PASS:-admin123}

    echo ""
    echo -e "${CYAN}[1/7] Installing dependencies...${NC}"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y \
        strongswan \
        strongswan-pki \
        libcharon-extra-plugins \
        libcharon-extauth-plugins \
        libstrongswan-extra-plugins \
        libstrongswan-standard-plugins \
        certbot \
        nginx \
        python3 \
        python3-pip \
        python3-venv \
        sqlite3 \
        curl \
        git \
        iptables

    setup_cli_shortcut

    echo -e "${CYAN}[2/7] Checking Let's Encrypt SSL for ${DOMAIN}...${NC}"
    systemctl stop nginx 2>/dev/null || true

    if [ -d "/etc/letsencrypt/live/${DOMAIN}" ] && [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
        echo -e "${GREEN}[+] Existing certificate found for ${DOMAIN}.${NC}"
    else
        certbot certonly --standalone \
            --agree-tos \
            --no-eff-email \
            -m "admin@${DOMAIN}" \
            -d "${DOMAIN}" \
            --key-type rsa \
            --rsa-key-size 2048 \
            --non-interactive
    fi

    echo -e "${CYAN}[3/7] Setting up certificates and auto-renewal hook...${NC}"
    mkdir -p /etc/ipsec.d/certs /etc/ipsec.d/cacerts /etc/ipsec.d/private
    cp "/etc/letsencrypt/live/${DOMAIN}/cert.pem" /etc/ipsec.d/certs/cert.pem
    cp "/etc/letsencrypt/live/${DOMAIN}/chain.pem" /etc/ipsec.d/cacerts/chain.pem
    cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" /etc/ipsec.d/private/privkey.pem

    chmod 600 /etc/ipsec.d/private/privkey.pem
    chmod 644 /etc/ipsec.d/certs/cert.pem /etc/ipsec.d/cacerts/chain.pem

    mkdir -p /etc/letsencrypt/renewal-hooks/deploy
    cat > /etc/letsencrypt/renewal-hooks/deploy/strongswan.sh << 'RENEW_EOF'
#!/usr/bin/env bash
for domain_dir in /etc/letsencrypt/live/*; do
    if [ -d "$domain_dir" ] && [ -f "$domain_dir/cert.pem" ]; then
        cp "$domain_dir/cert.pem" /etc/ipsec.d/certs/cert.pem
        cp "$domain_dir/chain.pem" /etc/ipsec.d/cacerts/chain.pem
        cp "$domain_dir/privkey.pem" /etc/ipsec.d/private/privkey.pem
        chmod 600 /etc/ipsec.d/private/privkey.pem
        chmod 644 /etc/ipsec.d/certs/cert.pem /etc/ipsec.d/cacerts/chain.pem
        ipsec reload 2>/dev/null || true
        ipsec rereadsecrets 2>/dev/null || true
        systemctl reload nginx 2>/dev/null || true
        break
    fi
done
RENEW_EOF
    chmod +x /etc/letsencrypt/renewal-hooks/deploy/strongswan.sh

    echo -e "${CYAN}[4/7] Generating StrongSwan configs...${NC}"
    cat > /etc/ipsec.conf << CONF_EOF
config setup
    charondebug="ike 1, knl 1, cfg 0"
    uniqueids=never

conn %default
    keyexchange=ikev2
    ike=aes256gcm16-prfsha384-ecp384,aes256gcm16-prfsha256-ecp256,aes256-sha256-modp2048,aes256-sha1-modp2048,aes256-sha1-modp1024,aes128-sha1-modp1024,3des-sha1-modp1024!
    esp=aes256gcm16-ecp384,aes256gcm16,aes256-sha256,aes256-sha1,aes128-sha256,aes128-sha1,3des-sha1!
    dpdaction=clear
    dpddelay=30s
    dpdtimeout=120s

conn ikev2-vpn
    auto=add
    left=%any
    leftid=@${DOMAIN}
    leftcert=cert.pem
    leftsendcert=always
    leftsubnet=0.0.0.0/0
    right=%any
    rightid=%any
    rightauth=eap-mschapv2
    rightsourceip=10.10.10.0/24
    rightdns=1.1.1.1,8.8.8.8
    rightsendcert=never
    eap_identity=%identity
CONF_EOF

    mkdir -p "${DB_DIR}"
    if [ ! -f "${SECRETS_PATH}" ]; then
        cat > "${SECRETS_PATH}" << 'SEC_EOF'
: RSA privkey.pem
SEC_EOF
        chmod 600 "${SECRETS_PATH}"
    fi

    echo -e "${CYAN}[5/7] Configuring network, forwarding and firewall rules...${NC}"
    cat > /etc/sysctl.d/99-ikev2-vpn.conf << 'SYSCTL_EOF'
net.ipv4.ip_forward = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
SYSCTL_EOF
    sysctl -p /etc/sysctl.d/99-ikev2-vpn.conf >/dev/null 2>&1 || true

    apply_firewall

    cat > /etc/systemd/system/ike-rules.service << 'RULES_EOF'
[Unit]
Description=IKE-UI Firewall & NAT Rules
After=network.target

[Service]
Type=oneshot
ExecStart=/opt/ike-ui/install.sh --apply-firewall
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
RULES_EOF

    systemctl daemon-reload
    systemctl enable ike-rules.service

    echo -e "${CYAN}[6/7] Setting up Python virtual environment & dependencies...${NC}"
    python3 -m venv "${INSTALL_DIR}/venv"
    "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip >/dev/null
    "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/panel/requirements.txt" >/dev/null

    SERVER_DOMAIN="${DOMAIN}" DB_PATH="${DB_PATH}" SECRETS_PATH="${SECRETS_PATH}" SECRET_KEY_PATH="${SECRET_KEY_PATH}" \
    VPN_USER_INFO=$("${INSTALL_DIR}/venv/bin/python" -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}/panel')
import app
from werkzeug.security import generate_password_hash
app.init_db()
conn = app.get_db()
cursor = conn.cursor()
cursor.execute('SELECT id FROM admin LIMIT 1')
row = cursor.fetchone()
if row:
    cursor.execute('UPDATE admin SET username = ?, password_hash = ? WHERE id = ?', ('${ADMIN_USER}', generate_password_hash('${ADMIN_PASS}'), row['id']))
else:
    cursor.execute('INSERT INTO admin (username, password_hash) VALUES (?, ?)', ('${ADMIN_USER}', generate_password_hash('${ADMIN_PASS}')))
conn.commit()

cursor.execute('SELECT username, password FROM users ORDER BY id ASC LIMIT 1')
u = cursor.fetchone()
conn.close()
app.sync_ipsec_secrets()
if u:
    print(f'{u[\"username\"]}:{u[\"password\"]}')
else:
    print('user1:Generated')
" 2>/dev/null || echo "user1:Generated")

    DEFAULT_VPN_USER=$(echo "$VPN_USER_INFO" | cut -d: -f1)
    DEFAULT_VPN_PASS=$(echo "$VPN_USER_INFO" | cut -d: -f2)

    cat > /etc/systemd/system/ike-ui.service << SERVICE_EOF
[Unit]
Description=IKE-UI Management Panel
After=network.target strongswan-starter.service strongswan.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}/panel
Environment="SERVER_DOMAIN=${DOMAIN}"
Environment="DB_PATH=${DB_PATH}"
Environment="SECRETS_PATH=${SECRETS_PATH}"
Environment="SECRET_KEY_PATH=${SECRET_KEY_PATH}"
ExecStart=${INSTALL_DIR}/venv/bin/gunicorn --workers 2 --threads 8 --worker-class gthread --worker-connections 1000 --timeout 30 --graceful-timeout 2 -b 127.0.0.1:8000 app:app
Restart=always
RestartSec=3
TimeoutStopSec=5s

[Install]
WantedBy=multi-user.target
SERVICE_EOF

    ln -sf /etc/systemd/system/ike-ui.service /etc/systemd/system/ikev2-panel.service 2>/dev/null || true

    echo -e "${CYAN}[7/7] Configuring Nginx reverse proxy...${NC}"
    cat > /etc/nginx/sites-available/ike-ui << NGINX_EOF
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
NGINX_EOF

    rm -f /etc/nginx/sites-enabled/default
    ln -sf /etc/nginx/sites-available/ike-ui /etc/nginx/sites-enabled/ike-ui

    systemctl daemon-reload
    systemctl enable strongswan-starter.service 2>/dev/null || systemctl enable strongswan.service 2>/dev/null || true
    systemctl enable ike-ui.service
    systemctl enable nginx.service

    systemctl restart strongswan-starter.service 2>/dev/null || systemctl restart strongswan.service 2>/dev/null || ipsec restart 2>/dev/null || true
    systemctl restart ike-ui.service
    systemctl restart nginx.service

    show_banner
    echo -e "${GREEN}${BOLD}====================================================================${NC}"
    echo -e "${GREEN}${BOLD}       IKE-UI Server & Panel Successfully Deployed!        ${NC}"
    echo -e "${GREEN}${BOLD}====================================================================${NC}"
    echo ""
    echo -e "  ${BOLD}Server Domain:${NC}    ${CYAN}https://${DOMAIN}${NC}"
    echo -e "  ${BOLD}Server IP:${NC}        ${YELLOW}${SERVER_IP}${NC}"
    echo -e "  ${BOLD}VPN Protocol:${NC}     ${GREEN}IKEv2 / IPsec (UDP 500 / 4500)${NC}"
    echo ""
    echo -e "  ${BOLD}Panel Login:${NC}"
    echo -e "     • URL:       ${CYAN}https://${DOMAIN}${NC}"
    echo -e "     • Username:  ${BOLD}${ADMIN_USER}${NC}"
    echo -e "     • Password:  ${BOLD}${ADMIN_PASS}${NC}"
    echo ""
    echo -e "  ${BOLD}Default VPN User:${NC}"
    echo -e "     • Username:  ${BOLD}${DEFAULT_VPN_USER}${NC}"
    echo -e "     • Password:  ${BOLD}${DEFAULT_VPN_PASS}${NC}"
    echo ""
    echo -e "${CYAN}====================================================================${NC}"
    echo -e "${YELLOW}Zero-Cert Setup: No certificates or profiles needed on clients.${NC}"
    echo -e "Enter Server: ${BOLD}${DOMAIN}${NC}, Username, and Password on iOS, Windows, Android, macOS."
    echo -e "${CYAN}====================================================================${NC}"
    echo ""
}

update_ike_ui() {
    show_banner
    echo -e "${CYAN}${BOLD}[*] Starting IKE-UI Update Process...${NC}"
    echo ""

    if ! command -v git >/dev/null 2>&1; then
        echo -e "${YELLOW}[*] Installing git...${NC}"
        apt-get update -y && apt-get install -y git
    fi

    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"

    if [ -d "$INSTALL_DIR/.git" ]; then
        echo -e "${CYAN}[1/4] Pulling latest updates from GitHub repository...${NC}"
        git remote set-url origin "$REPO_URL" 2>/dev/null || true
        git fetch --all --tags --prune
        git reset --hard origin/main
        echo -e "${GREEN}[+] Git repository updated successfully.${NC}"
    else
        echo -e "${YELLOW}[1/4] Initializing Git repository in ${INSTALL_DIR}...${NC}"
        TEMP_CLONE="/tmp/ike-ui-update-temp"
        rm -rf "$TEMP_CLONE"
        git clone -b main "$REPO_URL" "$TEMP_CLONE"
        cp -r "$TEMP_CLONE/.git" "$INSTALL_DIR/"
        rm -rf "$TEMP_CLONE"
        git reset --hard origin/main
        echo -e "${GREEN}[+] Converted to tracked Git repository.${NC}"
    fi

    chmod +x "${INSTALL_DIR}/install.sh" 2>/dev/null || true
    setup_cli_shortcut

    echo -e "${CYAN}[2/4] Updating Python dependencies...${NC}"
    if [ ! -d "${INSTALL_DIR}/venv" ]; then
        python3 -m venv "${INSTALL_DIR}/venv"
    fi
    "${INSTALL_DIR}/venv/bin/pip" install --disable-pip-version-check --no-cache-dir -r "${INSTALL_DIR}/panel/requirements.txt" >/dev/null
    echo -e "${GREEN}[+] Python dependencies updated.${NC}"

    echo -e "${CYAN}[3/4] Running database migrations...${NC}"
    "${INSTALL_DIR}/venv/bin/python" -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}/panel')
import app
app.init_db()
"
    echo -e "${GREEN}[+] Database schema verified and updated.${NC}"

    echo -e "${CYAN}[4/4] Restarting IKE-UI panel service...${NC}"
    if [ -f /etc/systemd/system/ike-ui.service ]; then
        sed -i 's|gunicorn .* app:app|gunicorn --workers 2 --threads 8 --worker-class gthread --worker-connections 1000 --timeout 30 --graceful-timeout 2 -b 127.0.0.1:8000 app:app|g' /etc/systemd/system/ike-ui.service
        if ! grep -q "TimeoutStopSec=" /etc/systemd/system/ike-ui.service; then
            sed -i '/RestartSec=/a TimeoutStopSec=5s' /etc/systemd/system/ike-ui.service
        fi
    fi
    systemctl daemon-reload
    systemctl restart ike-ui.service

    sleep 1

    # Read newly pulled version
    local new_ver=""
    if [ -f "${INSTALL_DIR}/install.sh" ]; then
        new_ver=$(grep -oP '^APP_VERSION=["\x27]?\K[^"\x27\s]+' "${INSTALL_DIR}/install.sh" 2>/dev/null || true)
    fi
    if [ -z "$new_ver" ] && [ -f "${INSTALL_DIR}/panel/app.py" ]; then
        new_ver=$(grep -oP '^APP_VERSION\s*=\s*["\x27]?\K[^"\x27\s]+' "${INSTALL_DIR}/panel/app.py" 2>/dev/null || true)
    fi
    if [ -n "$new_ver" ]; then
        APP_VERSION="1.4.1"
    fi

    if systemctl is-active --quiet ike-ui.service; then
        echo ""
        echo -e "${GREEN}${BOLD}====================================================================${NC}"
        echo -e "${GREEN}${BOLD}       IKE-UI Successfully Updated to Version v${APP_VERSION}!      ${NC}"
        echo -e "${GREEN}${BOLD}====================================================================${NC}"
        local commit_info
        commit_info=$(cd "$INSTALL_DIR" && git log -1 --pretty=format:"%h - %s (%cr)" 2>/dev/null || echo "Latest")
        echo -e "  ${BOLD}Version:${NC}  ${GREEN}${BOLD}v${APP_VERSION}${NC} (${CYAN}${commit_info}${NC})"
        echo -e "  ${BOLD}Status:${NC}   ${GREEN}Active & Running${NC}"
        echo -e "${GREEN}${BOLD}====================================================================${NC}"
        echo ""
    else
        echo -e "${RED}[X] Error: Service failed to start after update. Check logs with 'ike-ui logs'.${NC}"
    fi
}

start_services() {
    echo -e "${YELLOW}[*] Starting all services...${NC}"
    systemctl start strongswan-starter 2>/dev/null || systemctl start strongswan 2>/dev/null || ipsec start 2>/dev/null || true
    systemctl start ike-ui 2>/dev/null || systemctl start ikev2-panel 2>/dev/null || true
    systemctl start nginx
    echo -e "${GREEN}[+] All services started.${NC}"
}

stop_services() {
    echo -e "${YELLOW}[*] Stopping all services...${NC}"
    systemctl stop ike-ui 2>/dev/null || systemctl stop ikev2-panel 2>/dev/null || true
    systemctl stop nginx
    systemctl stop strongswan-starter 2>/dev/null || systemctl stop strongswan 2>/dev/null || ipsec stop 2>/dev/null || true
    echo -e "${GREEN}[+] All services stopped.${NC}"
}

restart_services() {
    echo -e "${YELLOW}[*] Restarting all services...${NC}"
    systemctl restart strongswan-starter 2>/dev/null || systemctl restart strongswan 2>/dev/null || ipsec restart 2>/dev/null || true
    systemctl restart ike-ui 2>/dev/null || systemctl restart ikev2-panel 2>/dev/null || true
    systemctl restart nginx
    echo -e "${GREEN}[+] All services restarted successfully.${NC}"
}

check_status() {
    show_banner
    echo -e "${CYAN}=== StrongSwan IPsec VPN Status ===${NC}"
    ipsec statusall 2>/dev/null || true
    echo ""
    echo -e "${CYAN}=== IKE-UI Panel Status ===${NC}"
    systemctl status ike-ui --no-pager -l 2>/dev/null || systemctl status ikev2-panel --no-pager -l 2>/dev/null || true
    echo ""
    echo -e "${CYAN}=== Nginx Web Server Status ===${NC}"
    systemctl status nginx --no-pager -l || true
}

view_logs() {
    show_banner
    echo -e "${BOLD}Select log stream to view:${NC}"
    echo -e "  ${CYAN}1)${NC} IKE-UI Panel Logs (Live journalctl)"
    echo -e "  ${CYAN}2)${NC} StrongSwan VPN Logs"
    echo -e "  ${CYAN}3)${NC} Nginx Access & Error Logs"
    echo -e "  ${CYAN}4)${NC} Back to Main Menu"
    echo ""
    read -rp "Enter choice [1-4]: " log_choice
    case $log_choice in
        1) journalctl -u ike-ui -n 50 -f ;;
        2) journalctl -u strongswan-starter -u strongswan -n 50 -f ;;
        3) tail -n 50 -f /var/log/nginx/access.log /var/log/nginx/error.log ;;
        *) return ;;
    esac
}

reset_admin_credentials() {
    show_banner
    echo -e "${BOLD}Administrator Credentials Manager${NC}"
    echo ""
    echo -e "${CYAN}[*] Existing Administrators:${NC}"
    "${INSTALL_DIR}/venv/bin/python" -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}/panel')
import app
conn = app.get_db()
cursor = conn.cursor()
cursor.execute('SELECT id, username FROM admin ORDER BY id ASC')
rows = cursor.fetchall()
conn.close()
for r in rows:
    print(f'   • {r[\"username\"]} (ID: {r[\"id\"]})')
" 2>/dev/null || true
    echo ""
    read -rp "Enter Admin Username to add/reset [default: admin]: " NEW_USER
    NEW_USER=${NEW_USER:-admin}

    read -rp "Enter new Admin Password: " NEW_PASS
    if [ -z "$NEW_PASS" ]; then
        echo -e "${RED}[X] Password cannot be empty.${NC}"
        return
    fi
    "${INSTALL_DIR}/venv/bin/python" -c "
import sys
sys.path.insert(0, '${INSTALL_DIR}/panel')
import app
import datetime
from werkzeug.security import generate_password_hash
conn = app.get_db()
cursor = conn.cursor()
cursor.execute('SELECT id FROM admin WHERE username = ?', ('${NEW_USER}',))
row = cursor.fetchone()
if row:
    cursor.execute('UPDATE admin SET password_hash = ? WHERE id = ?', (generate_password_hash('${NEW_PASS}'), row['id']))
else:
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT INTO admin (username, password_hash, created_at) VALUES (?, ?, ?)', ('${NEW_USER}', generate_password_hash('${NEW_PASS}'), now))
conn.commit()
conn.close()
print('[+] Administrator credentials for \'${NEW_USER}\' updated successfully.')
"
}

renew_ssl() {
    echo -e "${YELLOW}[*] Testing and renewing Let's Encrypt certificates...${NC}"
    certbot renew --deploy-hook "/etc/letsencrypt/renewal-hooks/deploy/strongswan.sh"
    echo -e "${GREEN}[+] SSL renewal completed.${NC}"
}

uninstall_all() {
    show_banner
    echo -e "${RED}${BOLD}[!] WARNING: You are about to uninstall IKE-UI!${NC}"
    echo ""
    read -rp "Are you sure you want to proceed with uninstallation? [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[yY]([eE][sS])?$ ]]; then
        echo -e "${YELLOW}Uninstallation cancelled.${NC}"
        return
    fi

    echo ""
    read -rp "Do you want to delete user database & credentials (/etc/strongswan-panel)? [y/N]: " del_db

    echo -e "${CYAN}[*] Stopping and disabling services...${NC}"
    systemctl stop ike-ui 2>/dev/null || true
    systemctl disable ike-ui 2>/dev/null || true
    rm -f /etc/systemd/system/ike-ui.service /etc/systemd/system/ikev2-panel.service

    systemctl stop ike-rules 2>/dev/null || true
    systemctl disable ike-rules 2>/dev/null || true
    rm -f /etc/systemd/system/ike-rules.service

    systemctl daemon-reload

    rm -f /etc/nginx/sites-enabled/ike-ui /etc/nginx/sites-available/ike-ui
    systemctl reload nginx 2>/dev/null || true

    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_PATH" "$ALT_BIN_PATH"

    if [[ "$del_db" =~ ^[yY]([eE][sS])?$ ]]; then
        rm -rf "$DB_DIR"
        echo -e "${YELLOW}[*] Database and credentials removed.${NC}"
    else
        echo -e "${GREEN}[*] Database preserved at ${DB_DIR}.${NC}"
    fi

    echo -e "${GREEN}${BOLD}[+] IKE-UI has been completely uninstalled.${NC}"
    exit 0
}

show_version() {
    local cur_ver="$APP_VERSION"
    if [ -f "${INSTALL_DIR}/install.sh" ]; then
        local disk_ver
        disk_ver=$(grep -oP '^APP_VERSION=["\x27]?\K[^"\x27\s]+' "${INSTALL_DIR}/install.sh" 2>/dev/null || true)
        if [ -n "$disk_ver" ]; then
            cur_ver="$disk_ver"
        fi
    fi
    if [ -d "$INSTALL_DIR/.git" ]; then
        COMMIT=$(cd "$INSTALL_DIR" && git log -1 --pretty=format:"%h (%ci)" 2>/dev/null || echo "git")
        echo -e "${CYAN}IKE-UI Version:${NC} ${BOLD}v${cur_ver}${NC} (${COMMIT})"
    else
        echo -e "${CYAN}IKE-UI Version:${NC} ${BOLD}v${cur_ver}${NC}"
    fi
}

show_help() {
    echo -e "${BOLD}IKE-UI Management CLI${NC}"
    echo ""
    echo -e "Usage: ${CYAN}ike-ui${NC} [command]"
    echo ""
    echo -e "Commands:"
    echo -e "  ${CYAN}(no arg)${NC}      Open interactive management menu"
    echo -e "  ${CYAN}install, -i${NC}   Full installation and deployment"
    echo -e "  ${CYAN}update, -u${NC}    Update IKE-UI to latest version from GitHub"
    echo -e "  ${CYAN}restart, -r${NC}   Restart all services (StrongSwan, Panel, Nginx)"
    echo -e "  ${CYAN}start${NC}         Start all services"
    echo -e "  ${CYAN}stop${NC}          Stop all services"
    echo -e "  ${CYAN}status, -s${NC}    Check service status and active VPN connections"
    echo -e "  ${CYAN}logs, -l${NC}      View live service logs"
    echo -e "  ${CYAN}password, -p${NC}  Reset admin web panel credentials"
    echo -e "  ${CYAN}ssl${NC}           Renew SSL certificates"
    echo -e "  ${CYAN}uninstall${NC}     Uninstall IKE-UI and clean up"
    echo -e "  ${CYAN}version, -v${NC}   Show current installed version"
    echo -e "  ${CYAN}help, -h${NC}      Show this help message"
    echo ""
}

menu() {
    while true; do
        show_banner
        echo -e "${BOLD}Select an action:${NC}"
        echo -e "  ${CYAN}1)${NC}  Full Install / Re-deploy"
        echo -e "  ${CYAN}2)${NC}  Update IKE-UI (Pull Latest from GitHub)"
        echo -e "  ${CYAN}3)${NC}  Restart All Services (StrongSwan, Panel, Nginx)"
        echo -e "  ${CYAN}4)${NC}  Stop All Services"
        echo -e "  ${CYAN}5)${NC}  Start All Services"
        echo -e "  ${CYAN}6)${NC}  Check Status & Active VPN Connections"
        echo -e "  ${CYAN}7)${NC}  View Live Logs"
        echo -e "  ${CYAN}8)${NC}  Reset Admin Panel Credentials"
        echo -e "  ${CYAN}9)${NC}  Renew SSL Certificate"
        echo -e "  ${CYAN}10)${NC} Uninstall IKE-UI"
        echo -e "  ${CYAN}0)${NC}  Exit"
        echo ""
        read -rp "Enter your choice [0-10]: " choice
        case $choice in
            1) install_all; break ;;
            2) 
                update_ike_ui
                echo ""
                read -rp "Press Enter to return to menu..."
                if [ -x "${INSTALL_DIR}/install.sh" ]; then
                    exec "${INSTALL_DIR}/install.sh"
                elif [ -f "${INSTALL_DIR}/install.sh" ]; then
                    exec bash "${INSTALL_DIR}/install.sh"
                fi
                ;;
            3) restart_services; read -rp "Press Enter to continue..." ;;
            4) stop_services; read -rp "Press Enter to continue..." ;;
            5) start_services; read -rp "Press Enter to continue..." ;;
            6) check_status; read -rp "Press Enter to continue..." ;;
            7) view_logs ;;
            8) reset_admin_credentials; read -rp "Press Enter to continue..." ;;
            9) renew_ssl; read -rp "Press Enter to continue..." ;;
            10) uninstall_all ;;
            0) exit 0 ;;
            *) echo -e "${RED}Invalid option.${NC}"; sleep 1 ;;
        esac
    done
}

case "$1" in
    version|-v|--version)
        show_version
        exit 0
        ;;
    help|-h|--help)
        show_help
        exit 0
        ;;
    --apply-firewall)
        apply_firewall
        exit 0
        ;;
esac

bootstrap_environment "$@"

check_root

case "$1" in
    install|-i|--install)
        install_all "$2"
        ;;
    update|-u|--update)
        update_ike_ui
        ;;
    restart|-r|--restart)
        restart_services
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    status|-s|--status)
        check_status
        ;;
    logs|-l|--logs)
        view_logs
        ;;
    password|-p|--password)
        reset_admin_credentials
        ;;
    ssl|--ssl)
        renew_ssl
        ;;
    uninstall|--uninstall)
        uninstall_all
        ;;
    "")
        menu
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac

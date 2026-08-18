#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANEL_SRC_DIR="${SCRIPT_DIR}/panel"
INSTALL_DIR="/opt/ike-ui"
DB_DIR="/etc/strongswan-panel"
DB_PATH="${DB_DIR}/panel.db"
SECRETS_PATH="/etc/ipsec.secrets"
SECRET_KEY_PATH="${DB_DIR}/secret.key"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo -e "${RED}[✗] Error: This script must be run as root (or with sudo).${NC}"
        exit 1
    fi
}

show_banner() {
    clear
    echo -e "${PURPLE}${BOLD}"
    cat << "EOF"
  ██╗██╗  ██╗███████╗      ██╗   ██╗██╗
  ██║██║ ██╔╝██╔════╝      ██║   ██║██║
  ██║█████╔╝ █████╗  █████╗██║   ██║██║
  ██║██╔═██╗ ██╔══╝  ╚════╝██║   ██║██║
  ██║██║  ██╗███████╗      ╚██████╔╝██║
  ╚═╝╚═╝  ╚═╝╚══════╝       ╚═════╝ ╚═╝
              IKE-UI Manager
EOF
    echo -e "${CYAN}====================================================${NC}"
    echo -e "${NC}"
}

detect_network() {
    NET_IFACE=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $5; exit}')
    if [ -z "$NET_IFACE" ]; then
        NET_IFACE=$(ip route show default 2>/dev/null | awk '{print $5; exit}')
    fi
    if [ -z "$NET_IFACE" ]; then
        NET_IFACE="eth0"
    fi

    SERVER_IP=$(curl -s4 https://api.ipify.org || curl -s4 https://ifconfig.me || echo "Unknown")
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
        read -rp "Enter Domain Name (e.g. faghir.seytann.com): " DOMAIN
    fi

    if [ -z "$DOMAIN" ]; then
        echo -e "${RED}[✗] Error: Domain name cannot be empty.${NC}"
        exit 1
    fi

    echo ""
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
        iptables-persistent \
        netfilter-persistent \
        nginx \
        python3 \
        python3-pip \
        python3-venv \
        sqlite3 \
        curl \
        ufw

    echo -e "${CYAN}[2/7] Checking Let's Encrypt SSL for ${DOMAIN}...${NC}"
    systemctl stop nginx 2>/dev/null || true

    if [ -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
        echo -e "${GREEN}[✓] Existing certificate found for ${DOMAIN}.${NC}"
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

    echo -e "${CYAN}[3/7] Setting up certificates and auto-renewal...${NC}"
    mkdir -p /etc/ipsec.d/certs /etc/ipsec.d/cacerts /etc/ipsec.d/private
    cp "/etc/letsencrypt/live/${DOMAIN}/cert.pem" /etc/ipsec.d/certs/cert.pem
    cp "/etc/letsencrypt/live/${DOMAIN}/chain.pem" /etc/ipsec.d/cacerts/chain.pem
    cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" /etc/ipsec.d/private/privkey.pem

    chmod 600 /etc/ipsec.d/private/privkey.pem
    chmod 644 /etc/ipsec.d/certs/cert.pem /etc/ipsec.d/cacerts/chain.pem

    mkdir -p /etc/letsencrypt/renewal-hooks/deploy
    cat > /etc/letsencrypt/renewal-hooks/deploy/strongswan.sh << 'EOF'
#!/usr/bin/env bash
for domain_dir in /etc/letsencrypt/live/*; do
    if [ -d "$domain_dir" ] && [ -f "$domain_dir/cert.pem" ]; then
        cp "$domain_dir/cert.pem" /etc/ipsec.d/certs/cert.pem
        cp "$domain_dir/chain.pem" /etc/ipsec.d/cacerts/chain.pem
        cp "$domain_dir/privkey.pem" /etc/ipsec.d/private/privkey.pem
        chmod 600 /etc/ipsec.d/private/privkey.pem
        chmod 644 /etc/ipsec.d/certs/cert.pem /etc/ipsec.d/cacerts/chain.pem
        ipsec reload || true
        ipsec rereadsecrets || true
        systemctl reload nginx 2>/dev/null || true
        break
    fi
done
EOF
    chmod +x /etc/letsencrypt/renewal-hooks/deploy/strongswan.sh

    echo -e "${CYAN}[4/7] Generating StrongSwan configs...${NC}"
    cat > /etc/ipsec.conf << EOF
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
EOF

    mkdir -p "${DB_DIR}"
    if [ ! -f "${SECRETS_PATH}" ]; then
        cat > "${SECRETS_PATH}" << 'EOF'
: RSA privkey.pem
mehran : EAP "12345678"
EOF
        chmod 600 "${SECRETS_PATH}"
    fi

    echo -e "${CYAN}[5/7] Configuring network, forwarding and TCP MSS...${NC}"
    cat > /etc/sysctl.d/99-ikev2-vpn.conf << 'EOF'
net.ipv4.ip_forward = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
EOF
    sysctl -p /etc/sysctl.d/99-ikev2-vpn.conf >/dev/null

    iptables -t nat -C POSTROUTING -s 10.10.10.0/24 -o "$NET_IFACE" -j MASQUERADE 2>/dev/null || \
        iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o "$NET_IFACE" -j MASQUERADE

    iptables -C FORWARD -s 10.10.10.0/24 -j ACCEPT 2>/dev/null || \
        iptables -A FORWARD -s 10.10.10.0/24 -j ACCEPT

    iptables -C FORWARD -d 10.10.10.0/24 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || \
        iptables -A FORWARD -d 10.10.10.0/24 -m state --state RELATED,ESTABLISHED -j ACCEPT

    iptables -t mangle -C FORWARD -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1360 2>/dev/null || \
        iptables -t mangle -A FORWARD -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1360

    netfilter-persistent save >/dev/null 2>&1 || true

    echo -e "${CYAN}[6/7] Installing IKE-UI Panel to ${INSTALL_DIR}...${NC}"
    mkdir -p "${INSTALL_DIR}"
    cp -r "${PANEL_SRC_DIR}/"* "${INSTALL_DIR}/"

    python3 -m venv "${INSTALL_DIR}/venv"
    "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip >/dev/null
    "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" >/dev/null

    SERVER_DOMAIN="${DOMAIN}" DB_PATH="${DB_PATH}" SECRETS_PATH="${SECRETS_PATH}" SECRET_KEY_PATH="${SECRET_KEY_PATH}" \
    "${INSTALL_DIR}/venv/bin/python" -c "
import app
from werkzeug.security import generate_password_hash
app.init_db()
conn = app.get_db()
cursor = conn.cursor()
cursor.execute('UPDATE admin SET password_hash = ? WHERE username = ?', (generate_password_hash('${ADMIN_PASS}'), 'admin'))
conn.commit()
conn.close()
"

    cat > /etc/systemd/system/ike-ui.service << EOF
[Unit]
Description=IKE-UI Management Panel
After=network.target strongswan-starter.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
Environment="SERVER_DOMAIN=${DOMAIN}"
Environment="DB_PATH=${DB_PATH}"
Environment="SECRETS_PATH=${SECRETS_PATH}"
Environment="SECRET_KEY_PATH=${SECRET_KEY_PATH}"
ExecStart=${INSTALL_DIR}/venv/bin/gunicorn -w 1 -b 127.0.0.1:8000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    ln -sf /etc/systemd/system/ike-ui.service /etc/systemd/system/ikev2-panel.service 2>/dev/null || true

    echo -e "${CYAN}[7/7] Configuring Nginx reverse proxy...${NC}"
    cat > /etc/nginx/sites-available/ike-ui << EOF
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
EOF

    rm -f /etc/nginx/sites-enabled/default
    ln -sf /etc/nginx/sites-available/ike-ui /etc/nginx/sites-enabled/ike-ui

    systemctl daemon-reload
    systemctl enable strongswan-starter.service 2>/dev/null || systemctl enable strongswan.service 2>/dev/null || true
    systemctl enable ike-ui.service
    systemctl enable nginx.service

    systemctl restart strongswan-starter.service 2>/dev/null || systemctl restart strongswan.service 2>/dev/null || ipsec restart
    systemctl restart ike-ui.service
    systemctl restart nginx.service

    show_banner
    echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}       🎉 IKE-UI Server & Panel Successfully Deployed!        ${NC}"
    echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}🌐 Server Domain:${NC}    ${CYAN}https://${DOMAIN}${NC}"
    echo -e "  ${BOLD}🖥️ Server IP:${NC}        ${YELLOW}${SERVER_IP}${NC}"
    echo -e "  ${BOLD}🛡️ VPN Protocol:${NC}     ${GREEN}IKEv2 / IPsec (UDP 500 / 4500)${NC}"
    echo ""
    echo -e "  ${BOLD}🔑 Panel Login:${NC}"
    echo -e "     • URL:       ${CYAN}https://${DOMAIN}${NC}"
    echo -e "     • Username:  ${BOLD}admin${NC}"
    echo -e "     • Password:  ${BOLD}${ADMIN_PASS}${NC}"
    echo ""
    echo -e "  ${BOLD}👤 Default VPN User:${NC}"
    echo -e "     • Username:  ${BOLD}mehran${NC}"
    echo -e "     • Password:  ${BOLD}12345678${NC}"
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Zero-Cert Setup: No certificates or profiles needed on clients!${NC}"
    echo -e "Enter Server: ${BOLD}${DOMAIN}${NC}, Username, and Password on iOS, Windows, Android, macOS."
    echo -e "${CYAN}════════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

restart_services() {
    echo -e "${YELLOW}[*] Restarting services...${NC}"
    systemctl restart strongswan-starter 2>/dev/null || systemctl restart strongswan 2>/dev/null || ipsec restart
    systemctl restart ike-ui 2>/dev/null || systemctl restart ikev2-panel 2>/dev/null || true
    systemctl restart nginx
    echo -e "${GREEN}[✓] All services restarted.${NC}"
}

check_status() {
    show_banner
    echo -e "${CYAN}--- StrongSwan VPN Status ---${NC}"
    ipsec statusall || true
    echo ""
    echo -e "${CYAN}--- Service Status ---${NC}"
    systemctl status ike-ui --no-pager -l 2>/dev/null || systemctl status ikev2-panel --no-pager -l 2>/dev/null || true
    echo ""
    systemctl status nginx --no-pager -l || true
}

reset_admin_password() {
    read -rp "Enter new Admin Password: " NEW_PASS
    if [ -z "$NEW_PASS" ]; then
        echo -e "${RED}[✗] Password cannot be empty.${NC}"
        return
    fi
    "${INSTALL_DIR}/venv/bin/python" -c "
import app
from werkzeug.security import generate_password_hash
conn = app.get_db()
cursor = conn.cursor()
cursor.execute('UPDATE admin SET password_hash = ? WHERE username = ?', (generate_password_hash('${NEW_PASS}'), 'admin'))
conn.commit()
conn.close()
print('[✓] Admin password updated successfully.')
"
}

renew_ssl() {
    echo -e "${YELLOW}[*] Testing and renewing Let's Encrypt certificates...${NC}"
    certbot renew --deploy-hook "/etc/letsencrypt/renewal-hooks/deploy/strongswan.sh"
    echo -e "${GREEN}[✓] SSL renewal completed.${NC}"
}

menu() {
    while true; do
        show_banner
        echo -e "${BOLD}Select an action:${NC}"
        echo -e "  ${CYAN}1)${NC} Full Install / Re-deploy (VPN Server + SSL + IKE-UI)"
        echo -e "  ${CYAN}2)${NC} Restart All Services (StrongSwan, Panel, Nginx)"
        echo -e "  ${CYAN}3)${NC} Check Status & Active VPN Connections"
        echo -e "  ${CYAN}4)${NC} Reset Admin Panel Password"
        echo -e "  ${CYAN}5)${NC} Renew SSL Certificate"
        echo -e "  ${CYAN}6)${NC} Exit"
        echo ""
        read -rp "Enter your choice [1-6]: " choice
        case $choice in
            1) install_all; break ;;
            2) restart_services; read -rp "Press Enter to continue..." ;;
            3) check_status; read -rp "Press Enter to continue..." ;;
            4) reset_admin_password; read -rp "Press Enter to continue..." ;;
            5) renew_ssl; read -rp "Press Enter to continue..." ;;
            6) exit 0 ;;
            *) echo -e "${RED}Invalid option.${NC}"; sleep 1 ;;
        esac
    done
}

check_root

if [ "$1" == "--install" ] || [ "$1" == "-i" ]; then
    install_all "$2"
elif [ "$1" == "--restart" ] || [ "$1" == "-r" ]; then
    restart_services
elif [ "$1" == "--status" ] || [ "$1" == "-s" ]; then
    check_status
else
    menu
fi

#!/usr/bin/env bash
set -e

# ==============================================================================
#  IKE-UI One-Line Quick Installer & Bootstrap
#  Repo: https://github.com/MehranPNG/IKE-UI
# ==============================================================================

REPO_URL="https://github.com/MehranPNG/IKE-UI.git"
INSTALL_DIR="/opt/ike-ui"
BIN_PATH="/usr/local/bin/ike-ui"
ALT_BIN_PATH="/usr/bin/ike-ui"

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
PURPLE="\033[0;35m"
CYAN="\033[0;36m"
BOLD="\033[1m"
NC="\033[0m"

show_banner() {
    clear 2>/dev/null || true
    echo -e "${PURPLE}${BOLD}"
    cat << "BANNER"
  ██╗██╗  ██╗███████╗      ██╗   ██╗██╗
  ██║██║ ██╔╝██╔════╝      ██║   ██║██║
  ██║█████╔╝ █████╗  █████╗██║   ██║██║
  ██║██╔═██╗ ██╔══╝  ╚════╝██║   ██║██║
  ██║██║  ██╗███████╗      ╚██████╔╝██║
  ╚═╝╚═╝  ╚═╝╚══════╝       ╚═════╝ ╚═╝
              IKE-UI Installer
BANNER
    echo -e "${CYAN}====================================================${NC}"
    echo -e "${NC}"
}

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo -e "${RED}[✗] Error: This script must be run as root (or with sudo).${NC}" >&2
        exit 1
    fi
}

check_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        echo -e "${RED}[✗] Unsupported Linux distribution. Only Debian/Ubuntu are officially supported.${NC}" >&2
        exit 1
    fi

    if [[ "$OS" != "ubuntu" && "$OS" != "debian" && "$OS" != "raspbian" && "$OS" != "kali" && "$OS" != "pop" && "$OS" != "linuxmint" ]]; then
        echo -e "${YELLOW}[!] Warning: Your OS ($OS) is not Debian/Ubuntu based.${NC}"
        echo -e "${YELLOW}    IKE-UI uses apt-get for strongSwan and dependencies.${NC}"
        read -rp "Do you want to continue anyway? [y/N]: " confirm
        if [[ ! "$confirm" =~ ^[yY]([eE][sS])?$ ]]; then
            echo -e "${RED}Installation cancelled.${NC}"
            exit 1
        fi
    fi
}

install_dependencies() {
    echo -e "${CYAN}[*] Updating system packages and installing base dependencies...${NC}"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y curl git ca-certificates tar iptables ufw sudo
    echo -e "${GREEN}[✓] Base dependencies installed.${NC}"
}

clone_or_update_repo() {
    echo -e "${CYAN}[*] Downloading / Synchronizing IKE-UI repository...${NC}"
    mkdir -p "$(dirname "$INSTALL_DIR")"

    if [ -d "$INSTALL_DIR/.git" ]; then
        echo -e "${YELLOW}[*] Existing Git repository detected at ${INSTALL_DIR}.${NC}"
        cd "$INSTALL_DIR"
        git remote set-url origin "$REPO_URL" 2>/dev/null || true
        git fetch --all --tags --prune
        git reset --hard origin/main
        echo -e "${GREEN}[✓] Repository updated to latest main branch.${NC}"
    else
        if [ -d "$INSTALL_DIR" ]; then
            echo -e "${YELLOW}[*] Non-git directory found at ${INSTALL_DIR}. Re-initializing...${NC}"
            rm -rf "${INSTALL_DIR:?}"/*
        fi
        git clone -b main "$REPO_URL" "$INSTALL_DIR"
        echo -e "${GREEN}[✓] Repository cloned successfully.${NC}"
    fi

    chmod +x "${INSTALL_DIR}/run.sh" 2>/dev/null || true
    chmod +x "${INSTALL_DIR}/install.sh" 2>/dev/null || true
}

setup_cli_shortcut() {
    echo -e "${CYAN}[*] Configuring global command shortcut ike-ui...${NC}"
    mkdir -p "$(dirname "$BIN_PATH")"
    echo "#!/usr/bin/env bash" > "$BIN_PATH"
    echo "exec /opt/ike-ui/run.sh \"\$@\"" >> "$BIN_PATH"
    chmod +x "$BIN_PATH"
    ln -sf "$BIN_PATH" "$ALT_BIN_PATH" 2>/dev/null || true
    echo -e "${GREEN}[✓] Command shortcut created! You can run \033[1mike-ui\033[0m anytime from anywhere.${NC}"
}

main() {
    check_root
    show_banner
    check_os

    install_dependencies
    clone_or_update_repo
    setup_cli_shortcut

    echo ""
    echo -e "${GREEN}${BOLD}[✓] Bootstrap completed successfully.${NC}"
    echo ""

    if [ $# -gt 0 ]; then
        exec "${INSTALL_DIR}/run.sh" "$@"
    else
        exec "${INSTALL_DIR}/run.sh"
    fi
}

main "$@"

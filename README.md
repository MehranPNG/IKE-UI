# 🛡️ IKE-UI

> **All-in-One IKEv2/IPsec VPN Server & Web Management Panel**

<p align="left">
  <img src="https://img.shields.io/badge/Release-v1.0.1-7452ff?style=flat-square" alt="Version 1.0.0" />
  <img src="https://img.shields.io/badge/VPN-IKEv2%20%2F%20IPsec-blue?style=flat-square" alt="IKEv2 VPN" />
  <img src="https://img.shields.io/badge/SSL-Let's%20Encrypt%20Auto-brightgreen?style=flat-square" alt="Let's Encrypt" />
  <img src="https://img.shields.io/badge/OS-Ubuntu%20%2F%20Debian-orange?style=flat-square" alt="Ubuntu / Debian" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="MIT License" />
</p>

**IKE-UI** is a lightweight, zero-configuration **IKEv2/IPsec VPN Server** with automated **Let's Encrypt SSL** and a real-time **Web Management Panel**.

It requires **NO client-side certificates or configuration profiles**. Clients connect natively on **iOS, Android, Windows, and macOS** using only Server Domain, Username, and Password.

---

## 📋 Prerequisites

Before installing, make sure you have:

1. **Linux Server**: Ubuntu 20.04 / 22.04 / 24.04 or Debian 11 / 12 with `root` or `sudo` access.
2. **Domain / Subdomain**: A domain (e.g. `vpn.example.com`) with an **DNS `A` Record** pointing to your server's public IP address.
3. **Open Ports**: Ensure the following ports are open on your firewall / cloud provider:
   - `UDP 500` & `UDP 4500` (IKEv2 / IPsec VPN)
   - `TCP 80` & `TCP 443` (SSL Certificate & Web Panel)

---

## 🚀 Quick Install

Run this command on your server to start the interactive installation:

```bash
bash <(curl -Ls https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh)
```

The script will automatically install dependencies, issue Let's Encrypt SSL, configure StrongSwan & Nginx, set up the web panel, and create the global `ike-ui` command.

---

## ⚡ Server Management (`ike-ui`)

Once installed, you can manage your server anytime by simply running:

```bash
ike-ui
```

This opens the interactive manager for checking status, restarting services, viewing live logs, managing SSL, or updating the panel.

### 🛠️ Command Shortcuts

You can also run subcommands directly:

| Command | Description |
| :--- | :--- |
| `ike-ui` | Open interactive management menu |
| `ike-ui status` / `-s` | Check service status and active VPN connections |
| `ike-ui update` / `-u` | Update IKE-UI to the latest version |
| `ike-ui restart` / `-r` | Restart StrongSwan, Panel, and Nginx |
| `ike-ui logs` / `-l` | View live service logs |
| `ike-ui password` / `-p` | Reset web panel admin credentials |
| `ike-ui ssl` | Renew Let's Encrypt SSL certificates |
| `ike-ui start` / `stop` | Start or stop all services |
| `ike-ui uninstall` | Completely uninstall IKE-UI |

---

## 🔄 Updates

To update IKE-UI to the latest release on GitHub without losing any user accounts or database settings:

```bash
ike-ui update
```

---

## 📱 Client Connection Guides

### 🍏 iOS / iPadOS
1. **Settings** ➡️ **VPN & Device Management** ➡️ **Add VPN Configuration...**
2. **Type**: `IKEv2`
3. **Server** & **Remote ID**: `your-domain.com`
4. **User Authentication**: `Username`
5. Enter **Username** & **Password**.

### 💻 Windows 10 & 11
1. **Settings** ➡️ **Network & Internet** ➡️ **VPN** ➡️ **Add a VPN connection**
2. **VPN provider**: `Windows (built-in)`
3. **Server name or address**: `your-domain.com`
4. **VPN type**: `IKEv2`
5. **Type of sign-in info**: `User name and password`
6. Enter **Username** & **Password**.

### 🤖 Android
1. **Settings** ➡️ **Connections / VPN** ➡️ **Add VPN (+)**
2. **Type**: `IKEv2/IPSec MSCHAPv2`
3. **Server address** & **IPSec identifier**: `your-domain.com`
4. **CA certificate**: `(Unspecified)` or `Select automatically`
5. Enter **Username** & **Password**.

### 🍎 macOS
1. **System Settings** ➡️ **Network** ➡️ **VPN** ➡️ **Add VPN Configuration** ➡️ **IKEv2**
2. **Server Address** & **Remote ID**: `your-domain.com`
3. **Authentication**: `Username`
4. Enter **Username** & **Password**.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).

# 🛡️ IKE-UI — All-in-One IKEv2/IPsec VPN Server & Web Panel

<p align="center">
  <img src="https://img.shields.io/badge/VPN-IKEv2%20%2F%20IPsec-blue?style=for-the-badge&logo=wireguard" alt="IKEv2 VPN" />
  <img src="https://img.shields.io/badge/SSL-Let's%20Encrypt%20Auto-brightgreen?style=for-the-badge&logo=letsencrypt" alt="Let's Encrypt" />
  <img src="https://img.shields.io/badge/UI-Neo--Brutalist%20Panel-ff5c5c?style=for-the-badge" alt="Neo-Brutalist Web Panel" />
  <img src="https://img.shields.io/badge/Mobile-TCP%20MSS%20Optimized-yellow?style=for-the-badge" alt="MSS Clamped" />
  <img src="https://img.shields.io/badge/OS-Ubuntu%20%2F%20Debian-orange?style=for-the-badge&logo=ubuntu" alt="Ubuntu / Debian" />
</p>

---

**IKE-UI** is a zero-config, production-grade **IKEv2/IPsec VPN Server** with automated **Let's Encrypt SSL** and a real-time **Web Management Panel** (CPU/RAM/Disk/Network monitoring, live user status, traffic quotas, and connection generator).

It requires **ZERO client-side certificates or configuration profiles**. Users connect natively across **iOS, iPadOS, macOS, Windows 10/11, and Android** using only **Server Domain, Username, and Password**.

---

## 🚀 Quick Install (One-Line Command)

Run this command as `root` (or with `sudo`) on an Ubuntu/Debian server:

```bash
bash <(curl -Ls https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh)
```
*or:*
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh)"
```

The script automatically installs dependencies, secures an SSL certificate from Let's Encrypt, configures StrongSwan & Nginx, sets up the web panel service, and binds the global `ike-ui` CLI command to your system.

---

## 🔄 In-Place Updates (Zero Data Loss)

Updating your IKE-UI server to the latest release on GitHub is instant and safe. **Your user database, credentials, and SSL certificates are never deleted or affected.**

#### Method 1: Using the CLI (Recommended)
```bash
ike-ui update
```

#### Method 2: Running the One-Liner Script
```bash
bash <(curl -Ls https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh) update
```

---

## ⚡ Management CLI (`ike-ui`)

After installation, simply type `ike-ui` anywhere in your terminal to open the interactive manager or execute subcommands directly.

### 🛠️ CLI Commands & Subcommands

| Command | Description |
| :--- | :--- |
| `ike-ui` | Open interactive management menu |
| `ike-ui install [domain]` | Run automated full deployment |
| `ike-ui update` / `ike-ui -u` | Update IKE-UI to latest release |
| `ike-ui restart` / `ike-ui -r` | Restart StrongSwan, Panel, and Nginx |
| `ike-ui start` | Start all services |
| `ike-ui stop` | Stop all services |
| `ike-ui status` / `ike-ui -s` | Show service status & active VPN sessions (`ipsec statusall`) |
| `ike-ui logs` / `ike-ui -l` | View live panel and VPN logs |
| `ike-ui password` / `ike-ui -p` | Reset admin web panel credentials |
| `ike-ui ssl` | Manually renew Let's Encrypt SSL certificates |
| `ike-ui uninstall` | Completely uninstall IKE-UI |
| `ike-ui version` / `ike-ui -v` | Show installed version & commit hash |

---

## 🌟 Key Features

1. **Zero Client Certificate (Let's Encrypt RSA)**:
   - Eliminates tedious CA installation or `.mobileconfig` profiles.
   - Works immediately with native OS VPN clients using MSCHAPv2 / EAP.
2. **Cellular Network Optimization (TCP MSS 1360)**:
   - Automated TCP MSS Clamping prevents MTU packet fragmentation drops on mobile carrier networks.
3. **Live SSE Web Management Dashboard**:
   - Real-time CPU, RAM, Disk, and Network traffic speed meters.
   - User creation, traffic quota limits (GB), expiration dates, and note fields.
   - One-click client connection details copy.
4. **Automated SSL Renewal**:
   - Includes a Certbot deploy hook that automatically reloads StrongSwan IPsec and Nginx when certificates renew.

---

## 📱 Client Setup Guides

### 📱 iOS / iPadOS
1. Go to **Settings** ➡️ **VPN & Device Management** ➡️ **Add VPN Configuration...**
2. **Type**: `IKEv2`
3. **Description**: `IKEv2 VPN`
4. **Server**: `your-domain.com`
5. **Remote ID**: `your-domain.com`
6. **User Authentication**: `Username`
7. **Username & Password**: *(Your user credentials)*

### 💻 Windows 10 & 11
1. Go to **Settings** ➡️ **Network & Internet** ➡️ **VPN** ➡️ **Add a VPN connection**
2. **VPN provider**: `Windows (built-in)`
3. **Connection name**: `IKEv2 VPN`
4. **Server name or address**: `your-domain.com`
5. **VPN type**: `IKEv2`
6. **Type of sign-in info**: `User name and password`
7. Enter **Username** & **Password** and click **Save**.

### 🤖 Android
1. Go to **Settings** ➡️ **Network & internet / Connections** ➡️ **VPN** ➡️ **Add VPN (+)**
2. **Type**: `IKEv2/IPSec MSCHAPv2`
3. **Server address**: `your-domain.com`
4. **IPSec identifier**: `your-domain.com`
5. **CA certificate**: `(Unspecified)` or `Select automatically`
6. Enter **Username** and **Password**.

### 🍏 macOS
1. Go to **System Settings** ➡️ **Network** ➡️ **VPN** ➡️ **Add VPN Configuration** ➡️ **IKEv2**
2. **Server Address**: `your-domain.com`
3. **Remote ID**: `your-domain.com`
4. **Authentication**: `Username`
5. Enter **Username** and **Password**.

---

## 📂 Project Structure

```
IKE-UI/
├── install.sh                 # ⚡ Master all-in-one setup & management CLI
├── README.md                  # 📖 Project documentation
├── panel/                     # 🌐 IKE-UI Web Panel
│   ├── app.py                 # Backend with SSE stream & system meters
│   ├── requirements.txt       # Python dependencies
│   ├── static/
│   │   └── style.css          # Neo-brutalist styling
│   └── templates/
│       ├── dashboard.html     # Dashboard with live meters & table
│       ├── login.html         # Login page
│       └── settings.html      # Settings page
└── /etc/strongswan-panel/     # 🗄️ Persistent database & session key
```

---

## 📄 License
Released under the [MIT License](LICENSE).

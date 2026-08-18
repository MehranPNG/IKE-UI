# 🛡️ IKE-UI - All-in-One IKEv2/IPsec VPN Server & Management Panel

A zero-config **IKEv2/IPsec VPN Server** with **Public Let's Encrypt SSL** and a real-time **Neo-Brutalist Web Management Panel** (CPU/RAM/Disk/Network monitoring, live user status, quota limits, and instant connection generator).

---

## 🚀 Quick Start

### 1. Transfer this folder to your server:
```bash
scp -r /home/mehranpng/Mehran/IKEv2 root@YOUR_SERVER_IP:/root/
```

### 2. Connect to the server & run:
```bash
cd /root/IKEv2
sudo bash run.sh
```

---

## 🌟 Features

1. **Zero Client Certificate**:
   - Uses Let's Encrypt RSA SSL certificates (ISRG Root X1).
   - Users connect on iOS, Windows, Android, and macOS using only **Server, Username, and Password**.
2. **Cellular Network Optimization**:
   - Automated **TCP MSS Clamping (1360)** prevents fragmentation drops on mobile carrier networks (Irancell, MCI, Rightel).
3. **IKE-UI Web Panel**:
   - Real-time SSE (Server-Sent Events) live metrics (CPU, RAM, Disk, Network speeds).
   - Instant account creation & connection details copy.
   - Traffic limits and duration expiration management.

---

## 📋 Interactive Management Menu

Running `sudo bash run.sh` on the server opens the manager:

```
  ██╗██╗  ██╗███████╗      ██╗   ██╗██╗
  ██║██║ ██╔╝██╔════╝      ██║   ██║██║
  ██║█████╔╝ █████╗  █████╗██║   ██║██║
  ██║██╔═██╗ ██╔══╝  ╚════╝██║   ██║██║
  ██║██║  ██╗███████╗      ╚██████╔╝██║
  ╚═╝╚═╝  ╚═╝╚══════╝       ╚═════╝ ╚═╝
              IKE-UI Manager

Select an action:
  1) Full Install / Re-deploy (VPN Server + SSL + IKE-UI)
  2) Restart All Services (StrongSwan, Panel, Nginx)
  3) Check Status & Active VPN Connections
  4) Reset Admin Panel Password
  5) Renew SSL Certificate
  6) Exit
```

---

## 📱 Client Connection Guides

### 📱 iOS / iPadOS
- **Settings** ➡️ **VPN & Device Management** ➡️ **Add VPN Configuration...**
- **Type**: `IKEv2`
- **Server**: `your-domain.com`
- **Remote ID**: `your-domain.com`
- **User Authentication**: `Username`
- **Username & Password**: *(Your credentials)*

### 💻 Windows 10 & 11
- **Settings** ➡️ **Network & Internet** ➡️ **VPN** ➡️ **Add a VPN connection**
- **VPN provider**: `Windows (built-in)`
- **Server name**: `your-domain.com`
- **VPN type**: `IKEv2`
- **Type of sign-in**: `User name and password`

### 🤖 Android
- **Settings** ➡️ **Connections / VPN** ➡️ **Add VPN**
- **Type**: `IKEv2/IPSec MSCHAPv2`
- **Server address**: `your-domain.com`
- **IPSec identifier**: `your-domain.com`
- **CA certificate**: `Select automatically`

---

## 📂 Project Structure

```
IKEv2/
├── run.sh                     # ⚡ Master all-in-one setup & runner script
├── README.md                  # 📖 Documentation
├── SKILL.md                   # 🛠️ Technical architecture reference
└── panel/                     # 🌐 IKE-UI Web Panel
    ├── app.py                 # Backend with SSE stream & system meters
    ├── requirements.txt       # Python dependencies
    ├── static/
    │   └── style.css          # Neo-brutalist styling
    └── templates/
        ├── dashboard.html     # Dashboard with live meters & table
        ├── login.html         # Login page
        └── settings.html      # Settings page
```

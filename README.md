# IKE-UI

An all-in-one IKEv2/IPsec VPN server management tool with an integrated web panel and automated SSL certificate handling.

![Release](https://img.shields.io/github/v/release/MehranPNG/IKE-UI?style=flat-square)
![License](https://img.shields.io/github/license/MehranPNG/IKE-UI?style=flat-square)

IKE-UI simplifies the setup and maintenance of an IKEv2/IPsec VPN server on Debian-based systems. It uses standard EAP-MSCHAPv2 authentication, allowing clients to connect using native OS network settings without requiring custom apps, client-side certificates, or profiles.

---

## Prerequisites

Ensure your system meets the following requirements before installation:

* **Operating System:** Ubuntu (20.04, 22.04, 24.04) or Debian (11, 12) with root/sudo privileges.
* **Domain Name:** A valid domain or subdomain (e.g., `vpn.example.com`) pointed to your server's public IP address (DNS A Record).
* **Firewall Ports:**
  * `500/UDP` & `4500/UDP` (IKEv2 / IPsec)
  * `80/TCP` & `443/TCP` (Let's Encrypt SSL & Web Panel)

---

## Installation

Run the installation script to start the setup process:

```bash
bash <(curl -Ls https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh)
```

The script automates the following tasks:
* Installing required dependencies (StrongSwan, Nginx, Certbot, etc.)
* Obtaining and configuring Let's Encrypt SSL certificates
* Setting up the IPsec service and web panel
* Adding the `ike-ui` CLI utility for system management

---

## Usage & Management

You can manage the VPN server and web panel using the interactive CLI tool:

```bash
ike-ui
```

### Direct CLI Commands

The tool also supports quick management subcommands:

```bash
ike-ui status    # Check service status
ike-ui restart   # Restart all services
ike-ui logs      # View live system logs
ike-ui ssl       # Manage or renew SSL certificates
ike-ui update    # Update IKE-UI to the latest version
```

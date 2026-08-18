IKE-UI

Web management panel for an IKEv2/IPsec VPN server.

IKE-UI uses StrongSwan for the VPN service and Nginx for the web panel and TLS termination. It includes an installation script that configures the required services and can obtain a Let's Encrypt certificate for the VPN domain.

<p align="left">
  <img src="https://img.shields.io/badge/Release-v1.0.5-7452ff?style=flat-square" alt="Version 1.0.5" />
  <img src="https://img.shields.io/badge/VPN-IKEv2%20%2F%20IPsec-blue?style=flat-square" alt="IKEv2 VPN" />
  <img src="https://img.shields.io/badge/SSL-Let's%20Encrypt%20Auto-brightgreen?style=flat-square" alt="Let's Encrypt" />
  <img src="https://img.shields.io/badge/OS-Ubuntu%20%2F%20Debian-orange?style=flat-square" alt="Ubuntu / Debian" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="MIT License" />
</p>Features

- IKEv2/IPsec VPN using StrongSwan
- Web-based server management
- Let's Encrypt certificate setup
- Nginx configuration
- User management
- Service status and logs
- SSL certificate management
- Panel update support
- "ike-ui" command-line manager

Clients can connect using the native IKEv2 support available on iOS, Android, Windows, and macOS. The default setup does not require a client-side certificate.

Requirements

Before installation, make sure the server meets the following requirements:

- Ubuntu 20.04, 22.04, or 24.04
- Debian 11 or 12
- Root or "sudo" access
- A domain or subdomain pointing to the server
- The following ports available:

Port| Protocol| Purpose
500| UDP| IKE
4500| UDP| IPsec NAT-T
80| TCP| Let's Encrypt
443| TCP| Web panel

The domain must have an "A" record pointing to the server's public IP address.

Installation

Run the installation script:

bash <(curl -Ls https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh)

The installer will configure the required packages and services, including:

- StrongSwan
- Nginx
- Let's Encrypt
- IKE-UI
- The "ike-ui" command

The installer will prompt for the required configuration during setup.

Server Management

After installation, run:

ike-ui

This opens the management interface for common server operations.

You can use it to:

- Check service status
- Restart services
- View logs
- Manage SSL certificates
- Update IKE-UI
- Manage VPN users

Client Configuration

IKE-UI uses standard IKEv2/IPsec authentication.

Depending on the client platform, the connection can be configured with:

- Server address
- Username
- Password

No custom client application is required.

Supported Systems

Server

- Ubuntu 20.04
- Ubuntu 22.04
- Ubuntu 24.04
- Debian 11
- Debian 12

Clients

IKEv2 is supported by most modern operating systems, including:

- iOS
- Android
- Windows
- macOS

License

IKE-UI is released under the MIT License. See "LICENSE" (LICENSE) for details.

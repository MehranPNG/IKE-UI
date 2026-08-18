# 🛡️ IKE-UI — All-in-One IKEv2/IPsec VPN Server & Management Panel

<p align="center">
  <img src="https://img.shields.io/badge/VPN-IKEv2%20%2F%20IPsec-blue?style=for-the-badge&logo=wireguard" alt="IKEv2 VPN" />
  <img src="https://img.shields.io/badge/SSL-Let's%20Encrypt%20Auto-brightgreen?style=for-the-badge&logo=letsencrypt" alt="Let's Encrypt" />
  <img src="https://img.shields.io/badge/UI-Neo--Brutalist%20Panel-ff5c5c?style=for-the-badge" alt="Neo-Brutalist Web Panel" />
  <img src="https://img.shields.io/badge/Mobile-TCP%20MSS%20Optimized-yellow?style=for-the-badge" alt="MSS Clamped" />
  <img src="https://img.shields.io/badge/OS-Ubuntu%20%2F%20Debian-orange?style=for-the-badge&logo=ubuntu" alt="Ubuntu / Debian" />
</p>

---

### 🌐 Language / زبان
- [English Documentation](#-english)
- [راهنمای فارسی (Persian Documentation)](#-راهنمای-فارسی)

---

<a name="english"></a>
## 🇬🇧 English

**IKE-UI** is a production-ready, zero-config **IKEv2/IPsec VPN Server** bundled with **Public Let's Encrypt SSL** and a real-time **Web Management Panel**.

It requires **ZERO client-side certificates or profile installations**. Users connect natively on **iOS, iPadOS, macOS, Windows, and Android** using only Server Domain, Username, and Password.

---

### 🚀 Quick Installation (One-Line Command)

Run this single command as `root` or with `sudo` on your Ubuntu/Debian server:

```bash
bash <(curl -Ls https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh)
```
*or:*
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh)"
```

The script will automatically install dependencies, clone the repo to `/opt/ike-ui`, create the global `ike-ui` CLI shortcut, obtain Let's Encrypt SSL, configure StrongSwan & Nginx, and launch your Web Panel!

---

### 🔄 In-Place Update (Zero Data Loss)

Updating your IKE-UI panel to the latest version on GitHub is instant and safe. **Your user database, credentials, and SSL certificates are never deleted or affected.**

#### Method 1: Using the CLI Shortcut (Recommended)
```bash
ike-ui update
```

#### Method 2: Running the One-Liner Script
```bash
bash <(curl -Ls https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh) update
```

---

### ⚡ Management CLI (`ike-ui`)

After installation, you can run the `ike-ui` command anywhere in your terminal:

```bash
ike-ui
```

```
  ██╗██╗  ██╗███████╗      ██╗   ██╗██╗
  ██║██║ ██╔╝██╔════╝      ██║   ██║██║
  ██║█████╔╝ █████╗  █████╗██║   ██║██║
  ██║██╔═██╗ ██╔══╝  ╚════╝██║   ██║██║
  ██║██║  ██╗███████╗      ╚██████╔╝██║
  ╚═╝╚═╝  ╚═╝╚══════╝       ╚═════╝ ╚═╝
              IKE-UI Manager
====================================================

Select an action:
  1)  🚀 Full Install / Re-deploy
  2)  🔄 Update IKE-UI (Pull Latest from GitHub)
  3)  🔁 Restart All Services (StrongSwan, Panel, Nginx)
  4)  ⏹️  Stop All Services
  5)  ▶️  Start All Services
  6)  📊 Check Status & Active VPN Connections
  7)  📜 View Live Logs
  8)  🔑 Reset Admin Panel Password
  9)  🌐 Renew SSL Certificate
  10) 🗑️  Uninstall IKE-UI
  0)  ❌ Exit
```

#### 🛠️ Direct CLI Commands:
| Command | Description |
| :--- | :--- |
| `ike-ui` | Open interactive menu |
| `ike-ui install [domain]` | Run automated installer |
| `ike-ui update` / `ike-ui -u` | Update IKE-UI to latest release |
| `ike-ui restart` / `ike-ui -r` | Restart StrongSwan, Panel, and Nginx |
| `ike-ui start` | Start all services |
| `ike-ui stop` | Stop all services |
| `ike-ui status` / `ike-ui -s` | Show status & live VPN sessions (`ipsec statusall`) |
| `ike-ui logs` / `ike-ui -l` | View live panel and VPN logs |
| `ike-ui password` / `ike-ui -p` | Reset admin panel password |
| `ike-ui ssl` | Manually renew Let's Encrypt SSL |
| `ike-ui uninstall` | Completely uninstall IKE-UI |
| `ike-ui version` / `ike-ui -v` | Show installed version & commit |

---

### 🌟 Key Features

1. **Zero Client Certificates (Let's Encrypt RSA)**:
   - Eliminates tedious CA installation or `.mobileconfig` profiles.
   - Works immediately with native OS VPN clients using MSCHAPv2 / EAP.
2. **Cellular Network Optimization (TCP MSS 1360)**:
   - Prevents MTU packet fragmentation drops on mobile carriers (e.g. Irancell, MCI, Rightel).
3. **Live SSE Web Management Dashboard**:
   - Live CPU, RAM, Disk, and Network traffic speed meters.
   - User creation, traffic quota limits (GB), expiration dates, and note fields.
   - One-click client connection info copy.
4. **Automated SSL Renewal Hook**:
   - Certbot renewal automatically updates StrongSwan IPsec and reloads Nginx.

---

### 📱 Client Setup Guides

#### 📱 iOS / iPadOS
1. Open **Settings** ➡️ **VPN & Device Management** ➡️ **Add VPN Configuration...**
2. **Type**: `IKEv2`
3. **Description**: `My IKEv2 VPN`
4. **Server**: `your-domain.com`
5. **Remote ID**: `your-domain.com`
6. **User Authentication**: `Username`
7. **Username**: `your_username`
8. **Password**: `your_password`

#### 💻 Windows 10 & 11
1. Open **Settings** ➡️ **Network & Internet** ➡️ **VPN** ➡️ **Add a VPN connection**
2. **VPN provider**: `Windows (built-in)`
3. **Connection name**: `IKEv2 VPN`
4. **Server name or address**: `your-domain.com`
5. **VPN type**: `IKEv2`
6. **Type of sign-in info**: `User name and password`
7. Enter **Username** & **Password** and click **Save**.

#### 🤖 Android
1. Open **Settings** ➡️ **Network & internet / Connections** ➡️ **VPN** ➡️ **Add VPN (+)**
2. **Type**: `IKEv2/IPSec MSCHAPv2`
3. **Server address**: `your-domain.com`
4. **IPSec identifier**: `your-domain.com`
5. **CA certificate**: `(Unspecified)` or `Select automatically`
6. Enter **Username** and **Password**.

#### 🍏 macOS
1. Open **System Settings** ➡️ **Network** ➡️ **VPN** ➡️ **Add VPN Configuration** ➡️ **IKEv2**
2. **Server Address**: `your-domain.com`
3. **Remote ID**: `your-domain.com`
4. **Authentication**: `Username`
5. Enter **Username** and **Password**.

---

<a name="راهنمای-فارسی"></a>
## 🇮🇷 راهنمای فارسی

پروژه **IKE-UI** یک اسکریپت و پنل مدیریتی همه‌کاره برای راه‌اندازی و مدیریت سرور **IKEv2/IPsec** به همراه گواهی امنیتی معتبر **Let's Encrypt** و رابط کاربری وب مدرن (Neo-Brutalist) است.

اتصال به این سرور نیازمند **هیچ‌گونه فایل کانفیگ، پروفایل یا نصب گواهی CA نیست** و کاربران در تمام سیستم‌عامل‌ها (آیفون، اندروید، ویندوز و مک) تنها با وارد کردن **آدرس دامنه، نام کاربری و پسورد** متصل می‌شوند.

---

### 🚀 دستور نصب سریع (تک خطی)

کافیست دستور زیر را با دسترسی `root` یا `sudo` در ترمینال سرور لینوکس (اوبونتو / دبیان) اجرا کنید:

```bash
bash <(curl -Ls https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh)
```
*یا:*
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh)"
```

پس از اجرای دستور، پیش‌نیازها به صورت خودکار نصب شده و منوی مدیریت و نصب برای شما باز خواهد شد.

---

### 🔄 نحوه آپدیت بدون از دست رفتن داده‌ها

برای به‌روزرسانی پروژه به آخرین نسخه گیت‌هاب بدون حذف داده‌ها و اکانت‌های ساخته‌شده:

#### روش اول: با دستور `ike-ui`
```bash
ike-ui update
```

#### روش دوم: اجرای مجدد اسکریپت نصب
```bash
bash <(curl -Ls https://raw.githubusercontent.com/MehranPNG/IKE-UI/main/install.sh) update
```

---

### ⚡ منو و دستورات مدیریت (`ike-ui`)

پس از نصب، در هر کجای ترمینال با تایپ عبارت `ike-ui` منوی مدیریتی برای شما باز می‌شود:

```bash
ike-ui
```

#### 🛠️ جدول دستورات خط فرمان:
| دستور | توضیح |
| :--- | :--- |
| `ike-ui` | باز کردن منوی تعاملی مدیریت |
| `ike-ui install [domain]` | نصب و راه‌اندازی کامل سرور و پنل |
| `ike-ui update` یا `ike-ui -u` | آپدیت خودکار پنل به آخرین نسخه |
| `ike-ui restart` یا `ike-ui -r` | ری‌استارت تمام سرویس‌ها (StrongSwan، پنل و Nginx) |
| `ike-ui start` | روشن کردن سرویس‌ها |
| `ike-ui stop` | خاموش کردن سرویس‌ها |
| `ike-ui status` یا `ike-ui -s` | بررسی وضعیت سرویس‌ها و اتصالات آنلاین VPN |
| `ike-ui logs` یا `ike-ui -l` | مشاهده لاگ‌های زنده پنل و VPN |
| `ike-ui password` یا `ike-ui -p` | بازنشانی رمز عبور ادمین پنل |
| `ike-ui ssl` | تمدید دستی گواهی SSL |
| `ike-ui uninstall` | حذف کامل IKE-UI از روی سرور |
| `ike-ui version` یا `ike-ui -v` | نمایش نسخه و کامیت نصب شده |

---

### 🌟 ویژگی‌های برجسته

1. **بدون نیاز به گواهی در کلاینت (Zero-Cert)**:
   - استفاده از سرتیفیکیت رسمی Let's Encrypt RSA (مورد اعتماد تمام دیوایس‌ها).
   - بدون نیاز به نصب هیچ‌گونه فایل Certificate روی گوشی و سیستم.
2. **بهینه‌سازی ویژه اینترنت موبایل (TCP MSS Clamping)**:
   - تنظیم خودکار اندازه بسته‌ها روی `1360` برای جلوگیری از افت بسته در دیتای همراه اول، ایرانسل و رایتل.
3. **داشبورد وب بلادرنگ (Real-Time SSE)**:
   - نمایش سرعت لحظه‌ای شبکه (Upload/Download) و مصرف CPU/RAM/Disk بدون فشار به سرور.
   - مدیریت کاربران، محدودیت حجم (گیگابایت)، تاریخ انقضا، فعال/غیرفعال کردن آنی و یادداشت.
4. **تمدید خودکار SSL**:
   - مجهز به Deploy Hook اختصاصی Certbot جهت اعمال خودکار سرتیفیکیت‌های جدید روی StrongSwan و Nginx.

---

### 📂 ساختار فایل‌های پروژه

```
IKE-UI/
├── install.sh                 # 🚀 اسکریپت نصب تک‌خطی سریع
├── run.sh                     # ⚡ ابزار مدیریت و فرمان خطی (ike-ui)
├── README.md                  # 📖 مستندات پروژه
├── panel/                     # 🌐 اپلیکیشن تحت وب
│   ├── app.py                 # بک‌اند Flask + استریم SSE + مدیریت StrongSwan
│   ├── requirements.txt       # کتابخانه‌های پایتون
│   ├── static/
│   │   └── style.css          # استایل نئو-بروتالیست
│   └── templates/
│       ├── dashboard.html     # داشبورد اصلی و لیست کاربران
│       ├── login.html         # صفحه لاگین
│       └── settings.html      # تنظیمات و تغییر پسورد
└── /etc/strongswan-panel/     # 🗄️ دیتابیس کاربران و کلید سشن (خارج از رپو، پایدار در آپدیت)
```

---

## 📄 مجوز / License
منتشر شده تحت مجوز [MIT License](LICENSE).

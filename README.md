# WakeDeck

> **Remote PC management dashboard built for self-hosted homelab environments.**  
> Wake, monitor, shut down and schedule your PCs from anywhere — all from one clean web UI.

![WakeDeck UI](https://img.shields.io/badge/status-stable-brightgreen?style=flat-square)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)
![TrueNAS SCALE](https://img.shields.io/badge/TrueNAS-SCALE-0095D5?style=flat-square&logo=truenas&logoColor=white)
![Python](https://img.shields.io/badge/python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)

---

## ✨ Features

| Feature | Description |
|---|---|
| ⚡ **Wake-on-LAN** | Send magic packets to power on PCs from anywhere |
| 🔴 **Remote Shutdown/Restart** | Graceful control via SSH (key-based + password fallback) |
| 🖥️ **Multi-OS Support** | Windows and Linux device management with OS-specific icons |
| 📡 **Real-time Monitoring** | ICMP ping + TCP port probe (SSH/RDP/VNC) |
| 🔍 **LAN Scanner** | Auto-detect devices via nmap → arp-scan → ARP table |
| ⏰ **Scheduled Tasks** | Cron-based wake/shutdown automation (APScheduler) |
| 🔔 **Push Notifications** | Discord webhook + Telegram bot alerts |
| 🔑 **SSH Key Auth** | Auto-generated 4096-bit RSA keypair, stored in persistent volume |
| 🌐 **Timezone Support** | Configurable UTC offset for correct activity log timestamps |
| 📱 **Mobile Responsive** | Collapsible sidebar, optimized for phones and tablets |

---

## 🖼️ UI Preview

> Dark-themed single-page dashboard inspired by [Linear](https://linear.app). No frameworks, no build step, instant load.

```
┌─────────────────────────────────────────────────┐
│  🌊 WakeDeck          [Devices]   [⚙ Settings]  │
├──────────────┬──────────────────────────────────┤
│  📋 Devices  │  ┌──────────────────────────────┐  │
│  ⏰ Schedules│  │  🪟 My Windows PC     ● Online│  │
│  📜 Activity │  │  192.168.1.10 · WoL / SSH    │  │
│  ⚙ Settings  │  ├──────────────────────────────┤  │
│              │  │  🐧 Ubuntu Server     ● Online│  │
│              │  │  192.168.1.20 · WoL / SSH    │  │
└──────────────┴──────────────────────────────────┘
```

---

## 🚀 Quick Start

### Option 1: Load Pre-built Image (Recommended)

```bash
# Download wakedeck.tar, then on your server:
docker load -i wakedeck.tar
docker compose -f docker-compose.truenas.yml up -d
```

### Option 2: Build from Source

```bash
git clone <your-repo-url>
cd control-pc
docker build -t wakedeck:latest .
docker compose -f docker-compose.truenas.yml up -d
```

Access the UI at: `http://<your-server-ip>:36912`

On first launch, you'll be prompted to create an admin account.

---

## 🐳 Docker Compose (TrueNAS SCALE)

```yaml
version: '3.8'
services:
  wakedeck:
    image: wakedeck:latest
    container_name: wakedeck
    network_mode: host          # Required for WoL broadcast
    user: "568:568"             # TrueNAS apps user
    volumes:
      - /mnt/storage/Apps/wakedeck/data:/app/data
    environment:
      - SECRET_KEY=<your-64-char-random-string>
      - PORT=36912
      - DATA_DIR=/app/data
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 256M
        reservations:
          cpus: '0.10'
          memory: 64M
```

> ⚠️ **`network_mode: host` is required.** Bridge networking blocks WoL UDP broadcast packets.

---

## 🔧 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `changeme...` | JWT signing + Fernet encryption key. **Change this to a unique 64-char random string.** |
| `PORT` | `36912` | Web UI and API port |
| `DATA_DIR` | `/app/data` | Persistent data directory |

Generate a secure key:
```bash
openssl rand -hex 32
```

---

## 🗂️ Persistent Data

All state is stored in `/app/data` (mount this as a volume):

| File | Description |
|---|---|
| `wakedeck.db` | SQLite database (users, devices, schedules, logs) |
| `ssh_keys/id_rsa` | Auto-generated private key (chmod 600) |
| `ssh_keys/id_rsa.pub` | Public key — copy this to target PCs |
| `ssh_keys/known_hosts` | TOFU host fingerprint cache |

---

## 🔑 SSH Key Setup on Windows Target

1. Open WakeDeck → **Settings → SSH Key Authentication** → copy the public key
2. On the Windows PC, open **PowerShell as Administrator**:

```powershell
# Enable OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

# For standard user
mkdir "$env:USERPROFILE\.ssh" -Force
Add-Content "$env:USERPROFILE\.ssh\authorized_keys" "ssh-rsa AAAA...<paste key>"

# For Administrator user
Add-Content "C:\ProgramData\ssh\administrators_authorized_keys" "ssh-rsa AAAA...<paste key>"
icacls "C:\ProgramData\ssh\administrators_authorized_keys" /inheritance:r /grant "SYSTEM:(R)" /grant "Administrators:(R)"
```

---

## 🔑 SSH Key Setup on Linux Target

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-rsa AAAA...<paste key>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Allow sudo shutdown without password (add to sudoers):
echo "$(whoami) ALL=(ALL) NOPASSWD: /sbin/shutdown" | sudo tee /etc/sudoers.d/wakedeck
```

---

## 🌐 Wake-on-LAN Setup

1. **BIOS**: Enable "Wake on LAN" / "Power on by PCIE"
2. **Windows**: Device Manager → Network Adapter → Power Management → ✅ "Allow this device to wake the computer" + Advanced → "Wake on Magic Packet: Enabled"
3. **Linux**: `sudo ethtool -s eth0 wol g` (add to systemd service for persistence)

---

## 🛡️ Security Highlights

- **JWT authentication** with 4-hour token expiry
- **bcrypt** password hashing (12 rounds)
- **Rate limiting**: 5 login attempts / 60s per IP
- **4096-bit RSA SSH keypair** auto-generated on startup
- **Webhook secrets masked** in UI — full URL never returned to frontend
- **SSRF protection**: Notification URLs restricted to Discord/Telegram domains only
- **Input validation**: MAC, IP, subnet, cron, OS type — all validated via Pydantic
- **HTTP security headers**: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **No CORS**: Frontend served from same origin
- **Swagger/OpenAPI disabled** in production

---

## 📊 Resource Usage

| State | CPU | RAM |
|---|---|---|
| Idle | ~0.01 core | ~50 MB |
| Status polling (5 devices) | ~0.05 core | ~60 MB |
| Network scan | ~0.15 core | ~80 MB |
| SSH command | ~0.05 core | ~65 MB |

---

## 🤝 Tech Stack

**Backend**: FastAPI · Uvicorn · SQLite + SQLAlchemy · PyJWT · bcrypt · Paramiko · APScheduler · wakeonlan · httpx · Cryptography

**Frontend**: Vanilla HTML + CSS + JavaScript (zero dependencies, no build step)

---

## 📄 License

MIT — feel free to use, modify, and self-host.

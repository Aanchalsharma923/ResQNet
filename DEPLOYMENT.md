# ResQNet — Cloud Production Deployment Guide

This document provides exhaustive, step-by-step instructions for deploying ResQNet to a Linux Virtual Private Server (VPS) using Docker Compose and Nginx with SSL/TLS encryption.

---

## 1. Architecture Overview

In production, ResQNet runs as a multi-container system behind a single public ingress point (Nginx):

```
       Internet / Remote Clients (HTTPS & WSS)
                         │
                         ▼
             +───────────────────────+
             │   Host Port 80 / 443   │
             │   (Public Ingress)    │
             +───────────┬───────────+
                         │
        +────────────────▼────────────────+
        │   resqnet-frontend (Nginx)     │
        │   - Serves React SPA (Static)  │
        │   - Proxies /api/ to Backend   │
        │   - Proxies /ws to Backend     │
        │   - Handles SSL Termination    │
        +────────────────┬────────────────+
                         │
        Docker Internal Bridge Network (resqnet-net)
                         │
        +────────────────▼────────────────+
        │   resqnet-backend (FastAPI)    │
        │   - REST API & WebSockets      │
        │   - Dynamic AODV Routing Engine│
        │   - 5 Independent Node Procs   │
        │     (Ports 50010-50014 UDP)    │
        │   - Central Event Bridge       │
        │     (Port 50099 UDP)           │
        │   - Localhost Control Sockets   │
        │     (Ports 51010-51014 UDP)    │
        +─────────────────────────────────+
```

### Key Security & Reliability Guarantees
- **Explicit Real Network Mode:** In production, ResQNet executes bona fide multi-process UDP networking where Nodes A, B, C, D, and H run as independent OS processes communicating over physical datagram sockets. Production pre-flight assertions **strictly prohibit running in simulation mode**.
- **Consolidated Public Ingress:** Only standard web ports (`80` and `443`) are exposed publicly.
- **Internalized UDP Mesh:** Node UDP sockets (`50010`–`50014`), control listeners (`51010`–`51014`), and the event bridge (`50099`) remain entirely inside the private container network (`resqnet-net`). They are inaccessible from the open Internet, preventing packet injection and amplification attacks.
- **Isolated Backend:** Port `8000` is bound strictly to `127.0.0.1` on the host for administrative debugging or SSH tunneling; external traffic flows solely through Nginx.
- **Role Privilege Separation:** Network administration (`RESQNET_ADMIN_KEY`) and medical clinician triage (`RESQNET_HOSPITAL_KEY`) use separate credentials.

---

## 2. Minimum Hosting Requirements

- **Operating System:** Ubuntu 22.04 LTS or 24.04 LTS (Debian 12+ also supported).
- **CPU:** 2 vCPU cores minimum (recommended: 4 vCPU cores for smooth real-time multi-process UDP scheduling).
- **RAM:** 2 GB RAM minimum (4 GB recommended).
- **Disk:** 20 GB SSD storage.
- **Networking:** Static public IPv4 address with ports 80 and 443 accessible.

---

## 3. Linux VPS Preparation

Connect to your VPS via SSH as `root` or a user with `sudo` privileges:

```bash
ssh root@your_server_ip
```

### Step 1: Update System Packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git ufw jq wget
```

### Step 2: Configure UFW Firewall
Allow SSH, HTTP, and HTTPS only:
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

### Step 3: Install Docker and Docker Compose
```bash
# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add repository to Apt sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker packages
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

---

## 4. Deploying ResQNet with Docker Compose

### Step 1: Clone Repository
```bash
cd /opt
sudo git clone https://github.com/your-username/ResQNet.git resqnet
cd /opt/resqnet
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
nano .env
```
Ensure you configure the mandatory production parameters:
```ini
# Production assertion: Must be true
RESQNET_PRODUCTION=true

# Operating Mode: MUST be "real" in production
RESQNET_MODE=real

# Network Administrator Secret (Required for node failures, mode switches, resets)
RESQNET_ADMIN_KEY=your_very_secure_admin_key_98765

# Hospital Clinician Secret (Required for submitting triage responses)
RESQNET_HOSPITAL_KEY=your_very_secure_doctor_key_43210

# Permitted CORS origins (Replace with your actual domain or VPS IP)
RESQNET_CORS_ORIGINS=https://resqnet.yourdomain.com,http://your_server_ip

# Enforce strict WebSocket origin checks (Prevents CSWSH)
RESQNET_STRICT_WS_ORIGIN=true

# Rate limit for emergency SOS requests (per minute per client IP)
RESQNET_RATE_LIMIT_SOS_PER_MIN=60
```

> [!CAUTION]
> **Production Pre-Flight Guard:**
> When `RESQNET_PRODUCTION=true`, ResQNet validates on startup that:
> 1. `RESQNET_MODE` is explicitly set to `real`. Setting `simulation` causes immediate startup failure.
> 2. `RESQNET_ADMIN_KEY` and `RESQNET_HOSPITAL_KEY` are configured with non-default secrets.
> 3. `RESQNET_ADMIN_KEY` and `RESQNET_HOSPITAL_KEY` are not identical.

### Step 3: Build and Launch Containers
```bash
sudo docker compose build --no-cache
sudo docker compose up -d
```

### Step 4: Verify Container Status & Health
```bash
sudo docker compose ps
curl -s http://127.0.0.1:8000/health | jq .
```
Expected output:
```json
{
  "status": "ok",
  "service": "ResQNet",
  "runtime_mode": "real",
  "real_runtime_running": true
}
```

---

## 5. Domain, HTTPS & WebSocket Secure (WSS) Setup

ResQNet supports two distinct production TLS termination strategies.

### Strategy A: Host-Level Reverse Proxy (Recommended for Standard VPS)
In this pattern, host-level Nginx handles SSL on port 443 with automated Let's Encrypt renewal, and proxies internally to Docker on `127.0.0.1:8080`.

1. **Install Nginx & Certbot on Host:**
   ```bash
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```
2. **Bind Docker Frontend to 127.0.0.1:8080:**
   In `docker-compose.yml`, change the frontend port mapping:
   ```yaml
     frontend:
       ports:
         - "127.0.0.1:8080:80"
   ```
   Restart Docker Compose:
   ```bash
   sudo docker compose up -d
   ```
3. **Configure Host Nginx (`/etc/nginx/sites-available/resqnet`):**
   ```nginx
   server {
       listen 80;
       server_name resqnet.yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_read_timeout 86400s;
           proxy_send_timeout 86400s;
       }
   }
   ```
4. **Obtain SSL Certificate & Enable HTTPS:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/resqnet /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   sudo certbot --nginx -d resqnet.yourdomain.com
   ```
   Certbot configures HTTP-to-HTTPS redirect, WSS proxy headers, and creates an automatic renewal cron job (`certbot renew --dry-run`).

### Strategy B: Containerized TLS (Dockerized Nginx with Mounted Certs)
If you prefer Docker to terminate TLS directly on host ports `80` and `443`:

1. Obtain or place certificates in `/opt/resqnet/certs/`:
   - `/opt/resqnet/certs/fullchain.pem`
   - `/opt/resqnet/certs/privkey.pem`
2. In `docker-compose.yml`, uncomment the certificate volume mounts:
   ```yaml
     frontend:
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - ./certs:/etc/nginx/certs:ro
         - ./frontend/nginx.ssl.conf:/etc/nginx/conf.d/default.conf:ro
   ```
3. Restart containers:
   ```bash
   sudo docker compose up -d
   ```
   `nginx.ssl.conf` automatically redirects port 80 to port 443 HTTPS and proxies WebSocket Secure connections.

---

## 6. Security & Credential Management

### 1. Zero Secrets in Static Bundles
- `RESQNET_ADMIN_KEY` and `RESQNET_HOSPITAL_KEY` are **never baked into Vite build variables** (`VITE_ADMIN_KEY` has been completely eliminated from static builds).
- Administrators and clinicians enter their credentials securely in the web UI. Credentials are kept in the browser's `localStorage` and dispatched as `X-Admin-Key` or `X-Hospital-Key` headers.

### 2. Role Privilege Separation
- **Network Administrator:** Controls node failure injection (`/api/nodes/*/fail`), node recovery (`/api/nodes/*/recover`), link breaks (`/api/links/*`), mode switching, and network resets. Requires `X-Admin-Key`.
- **Hospital Clinician:** Reviews incidents and submits medical triage advice (`/api/hospital/respond`). Requires `X-Hospital-Key`. Cannot manipulate node routing tables or fail nodes.
- **Field Rescue Unit / Citizen:** Dispatches emergency distress calls (`/api/sos`). Fully public; requires no credentials.

### 3. Rate Limiting Architecture
- In-memory sliding-window limiter on `/api/sos` restricts submissions to 60 requests per minute per IP address.
- Behind Nginx, client IP resolution inspects `X-Real-IP` and `X-Forwarded-For` **only if the connecting proxy IP is a trusted private/docker bridge address** (`127.0.0.1`, `172.x.x.x`, `10.x.x.x`), preventing header spoofing from untrusted external networks.
- *Limitation:* The rate limiter is single-instance in-memory and resets on backend restart. For horizontally scaled multi-replica cloud clusters, a shared Redis store is recommended.

---

## 7. Ports and Firewall Reference

| Port | Protocol | Interface | Access | Purpose |
| :---: | :---: | :---: | :---: | :--- |
| **80** | TCP | `0.0.0.0` | **Public** | HTTP ingress (ACME challenges & redirect to HTTPS). |
| **443** | TCP | `0.0.0.0` | **Public** | HTTPS & WSS secure ingress (SSL/TLS termination). |
| **8000** | TCP | `127.0.0.1` | **Localhost Only** | FastAPI direct backend port (internal container bridge & local host debug). |
| **50010–50014** | UDP | Container Bridge | **Internal Only** | AODV Node Mesh sockets (Nodes A–H). Not exposed to public. |
| **51010–51014** | UDP | `127.0.0.1` | **Internal Only** | Local node process command listeners (kill, stop, status). |
| **50099** | UDP | Container Bridge | **Internal Only** | Central runtime telemetry event bridge. |

---

## 8. Operations, Startup & Shutdown Commands

### Start Services (Real Mode)
```bash
sudo docker compose up -d
```

### Stop Services
```bash
sudo docker compose down
```

### Restart Services
```bash
sudo docker compose restart
```

### Inspect Container Logs
```bash
# Real-time tail of all services
sudo docker compose logs -f

# Backend logs only
sudo docker compose logs -f backend
```

---

## 9. Post-Deployment Verification Checklist

Execute the following checklist after deployment to certify production readiness:

- [ ] `curl -f http://<host>/health` returns `{"status":"ok","service":"ResQNet","runtime_mode":"real","real_runtime_running":true}`.
- [ ] Navigating to `https://<domain>` loads the React dashboard over valid HTTPS without SSL warnings.
- [ ] Header WebSocket status badge shows `CONNECTED` (green) over secure WebSocket (`wss://`).
- [ ] All 5 topology nodes (A, B, C, D, H) show `UP` status on the SVG canvas.
- [ ] Clicking **Dispatch SOS** from Rescue-A animates the packet along `A → B → C → H`.
- [ ] Return transport ACK arrives with measured RTT and transitions status to `CONFIRMED`.
- [ ] Submitting a hospital triage response with a valid clinician key succeeds and renders on Rescue-A's triage card.
- [ ] Submitting a hospital response with an invalid key or invalid SOS ID returns HTTP 401 or HTTP 404.
- [ ] Providing the Admin Key in the Network Controls panel allows failing Node B; route dynamically failovers to `A → D → C → H`.
- [ ] Attempting to fail a node without the Admin Key returns HTTP 401 Unauthorized.

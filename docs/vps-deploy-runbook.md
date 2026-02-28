# VPS Deployment Runbook — TALKER Service

> **Purpose**: Step-by-step instructions to deploy the TALKER multi-tenant service on a Hetzner VPS.
> Designed to be executed by a human or Claude Code session on the remote server.

## Prerequisites

| Item | Value |
|------|-------|
| **Provider** | Hetzner Cloud |
| **Server type** | CCX23 (4 dedicated AMD vCPU, 16 GB RAM, 80 GB NVMe) |
| **OS** | Debian 12 (Bookworm) |
| **Location** | Nuremberg (nbg1) or Falkenstein (fsn1) |
| **SSH key** | Pre-added to Hetzner account |
| **Domain** | A record pointing to server IP (e.g. `talker.yourdomain.com`) |

Create the server via Hetzner web console, then SSH in as root.

---

## 1. Base System Setup

```bash
# Update system
apt update && apt upgrade -y

# Install essentials
apt install -y curl git ufw htop

# Configure firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (Caddy redirect)
ufw allow 443/tcp   # HTTPS (Caddy TLS)
ufw --force enable
ufw status verbose

# Create non-root user (optional but recommended)
adduser --disabled-password --gecos "" talker
usermod -aG sudo talker
cp -r ~/.ssh /home/talker/.ssh
chown -R talker:talker /home/talker/.ssh
```

## 2. Install Docker

```bash
# Docker official install (Debian)
curl -fsSL https://get.docker.com | sh

# Enable and start Docker
systemctl enable docker
systemctl start docker

# Verify
docker --version
docker compose version

# Allow non-root user to use Docker (if created above)
usermod -aG docker talker
```

## 3. Create Application Directory

```bash
mkdir -p /opt/talker
cd /opt/talker
```

## 4. Create Docker Compose Stack

Create `/opt/talker/docker-compose.yml`:

```yaml
services:
  # ─── Reverse Proxy ───────────────────────────
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - talker-service
    logging:
      driver: loki
      options:
        loki-url: "http://localhost:3100/loki/api/v1/push"
        labels: "service=caddy"

  # ─── TALKER Service ──────────────────────────
  talker-service:
    build:
      context: ./talker-service
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file: .env
    environment:
      - WS_HOST=0.0.0.0
      - WS_PORT=5557
      - LOG_LEVEL=INFO
    volumes:
      - ./logs:/app/logs
      - ./voices:/app/voices
    expose:
      - "5557"
    logging:
      driver: loki
      options:
        loki-url: "http://localhost:3100/loki/api/v1/push"
        labels: "service=talker"

  # ─── Logging ─────────────────────────────────
  loki:
    image: grafana/loki:3.0.0
    restart: unless-stopped
    ports:
      - "127.0.0.1:3100:3100"
    volumes:
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    logging:
      driver: json-file
      options:
        max-size: "10m"

  grafana:
    image: grafana/grafana:11.0.0
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-changeme}
      - GF_SERVER_ROOT_URL=https://${DOMAIN}/grafana/
      - GF_SERVER_SERVE_FROM_SUB_PATH=true
    depends_on:
      - loki
    logging:
      driver: loki
      options:
        loki-url: "http://localhost:3100/loki/api/v1/push"
        labels: "service=grafana"

volumes:
  caddy_data:
  caddy_config:
  loki_data:
  grafana_data:
```

## 5. Create Caddyfile

Create `/opt/talker/Caddyfile`:

```caddyfile
{DOMAIN} {
    # WebSocket endpoint — proxied to talker-service
    handle /ws {
        reverse_proxy talker-service:5557
    }

    # Health check endpoint
    handle /health {
        reverse_proxy talker-service:5557
    }

    # Debug endpoint (restrict in production)
    handle /debug/* {
        reverse_proxy talker-service:5557
    }

    # Grafana dashboard (admin access)
    handle_path /grafana/* {
        reverse_proxy grafana:3000
    }

    # Default: return 404
    handle {
        respond "Not found" 404
    }
}
```

Replace `{DOMAIN}` with your actual domain (e.g. `talker.yourdomain.com`). Caddy auto-provisions TLS via Let's Encrypt.

## 6. Create Dockerfile for TALKER Service

Create `/opt/talker/talker-service/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/
COPY run.py .

# Create logs dir
RUN mkdir -p logs

EXPOSE 5557

CMD ["python", "run.py"]
```

## 7. Deploy Application Source

Clone or copy the talker-service code into the build context:

```bash
cd /opt/talker

# Option A: Clone from git (if repo is accessible)
git clone https://github.com/YOUR_REPO/TALKER-Expanded.git /tmp/talker-repo
cp -r /tmp/talker-repo/talker_service/src talker-service/src
cp /tmp/talker-repo/talker_service/run.py talker-service/run.py
cp /tmp/talker-repo/talker_service/requirements.txt talker-service/requirements.txt

# Option B: SCP from local machine (run on your PC, not the server)
# scp -r talker_service/src talker_service/run.py talker_service/requirements.txt root@YOUR_IP:/opt/talker/talker-service/
```

## 8. Create Environment File

Create `/opt/talker/.env`:

```bash
# ─── Domain ────────────────────────────────────
DOMAIN=talker.yourdomain.com

# ─── Auth Tokens ───────────────────────────────
# Format: name:token,name:token
# name = session_id, token = invite code
TALKER_TOKENS=player1:invite-code-abc123,player2:invite-code-def456

# ─── LLM API Keys ─────────────────────────────
# These are server-side defaults; per-player config overrides via MCM
# (Set whichever providers you use)
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...

# ─── Grafana ───────────────────────────────────
GRAFANA_PASSWORD=your-secure-grafana-password

# ─── Outbox (multi-tenant) ────────────────────
# OUTBOX_TTL_MINUTES=30
# OUTBOX_MAX_SIZE=500
```

## 9. Install Loki Docker Log Driver

```bash
docker plugin install grafana/loki-docker-driver:3.0.0 --alias loki --grant-all-permissions
```

## 10. Start the Stack

```bash
cd /opt/talker
docker compose up -d

# Watch logs
docker compose logs -f

# Check individual services
docker compose ps
curl -s http://localhost:5557/health
curl -s https://YOUR_DOMAIN/health
```

## 11. Configure Grafana

1. Navigate to `https://YOUR_DOMAIN/grafana/`
2. Login with admin / `${GRAFANA_PASSWORD}`
3. Add Loki data source:
   - URL: `http://loki:3100`
   - Save & Test
4. Create a dashboard with:
   - Panel: Logs → `{service="talker"}` — shows all talker-service logs
   - Panel: Logs → `{service="caddy"}` — shows request logs
   - Panel: Stat → count of log lines with "error" in last hour

---

## Verification Checklist

After completing all steps, verify:

- [ ] `ufw status` shows only 22, 80, 443 open
- [ ] `docker compose ps` shows all 4 services healthy
- [ ] `curl https://YOUR_DOMAIN/health` returns 200
- [ ] WebSocket connects: `wscat -c "wss://YOUR_DOMAIN/ws?token=invite-code-abc123"` (install with `npm i -g wscat`)
- [ ] Grafana accessible at `https://YOUR_DOMAIN/grafana/`
- [ ] Loki receiving logs (check Grafana Explore → `{service="talker"}`)
- [ ] Bridge service from player PC connects and establishes session

---

## Operations

### View Logs
```bash
# All services
docker compose logs -f

# Just talker-service
docker compose logs -f talker-service

# Or use Grafana → Explore → {service="talker"}
```

### Update Application
```bash
cd /opt/talker

# Pull new source code (or scp updated files)
git -C /tmp/talker-repo pull
cp -r /tmp/talker-repo/talker_service/src talker-service/src
cp /tmp/talker-repo/talker_service/run.py talker-service/run.py

# Rebuild and restart (zero-downtime is not critical for a game mod)
docker compose build talker-service
docker compose up -d talker-service
```

### Add a New Player Token
```bash
# Edit .env, add to TALKER_TOKENS
nano /opt/talker/.env

# Restart service to pick up new tokens
docker compose restart talker-service
```

### Full Restart
```bash
docker compose down
docker compose up -d
```

### Wipe and Rebuild
```bash
docker compose down -v   # -v removes volumes (logs, Grafana data)
docker compose up -d --build
```

---

## Cost Summary

| Resource | Monthly Cost |
|----------|-------------|
| CCX23 (4 CPU, 16 GB) | ~€23 |
| 80 GB NVMe included | €0 |
| IPv4 address | included |
| Bandwidth (20 TB) | included |
| TLS certificates | free (Let's Encrypt via Caddy) |
| **Total** | **~€23/mo** |

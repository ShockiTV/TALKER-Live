# VPS Deployment Runbook — TALKER Service (Multi-Branch)

> **Purpose**: Step-by-step instructions to deploy the TALKER multi-branch service on a Hetzner VPS.
> Designed to be executed by a human or Claude Code session on the remote server.

## Architecture

```
                         ┌──────────────────────────────────────────┐
                         │              Hetzner VPS (CCX23)         │
  Players                │                                          │
  ───────                │  ┌────────┐                              │
                         │  │ Caddy  │  :80 / :443                  │
  wss://.../ws/main ────►│  │        ├──► talker-main :5557         │
  wss://.../ws/dev  ────►│  │        ├──► talker-dev  :5557         │
  https://.../grafana ──►│  │        ├──► grafana     :3000         │
                         │  └────────┘                              │
                         │       ▲                                  │
                         │       │  All talker instances share:     │
                         │  ┌────┴─────┐    ┌─────────────┐        │
                         │  │ tts-svc  │    │   stt-svc   │        │
                         │  │  :8100   │    │   :8000     │        │
                         │  └──────────┘    └─────────────┘        │
                         │                                          │
                         │  ┌──────┐  ┌─────────┐                  │
                         │  │ Loki │  │ Grafana │                  │
                         │  └──────┘  └─────────┘                  │
                         └──────────────────────────────────────────┘
```

**Key design points:**
- Each git branch gets its own `talker-*` container, routed via Caddy path prefix
- TTS and STT run as shared containers — all branches share one instance of each
- Per-branch `.env` files provide independent config (tokens, LLM keys, pins)
- Git worktrees manage per-branch source checkouts from a single clone

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
mkdir -p /opt/talker-live
cd /opt/talker-live
```

## 4. Setting Up Git Worktrees

Clone the repo once, then create lightweight worktrees per branch:

```bash
# Clone the repo (shared .git object store)
git clone https://github.com/YOUR_ORG/TALKER-live.git /opt/talker-live/repo
cd /opt/talker-live/repo

# Create worktree directories
mkdir -p /opt/talker-live/branches

# Create worktrees for each branch you want to deploy
git worktree add /opt/talker-live/branches/main main
git worktree add /opt/talker-live/branches/dev dev
```

After this, the directory layout is:

```
/opt/talker-live/
├── repo/                (clone — shared .git)
├── branches/
│   ├── main/            (worktree → main branch)
│   │   ├── talker_service/
│   │   └── tts_service/
│   └── dev/             (worktree → dev branch)
│       ├── talker_service/
│       └── tts_service/
├── docker-compose.yml
├── Caddyfile
├── .env.main
├── .env.dev
├── voices/              (shared voice files)
└── logs/
    ├── main/
    └── dev/
```

## 5. Deploy Config Files

Copy the template files from any branch checkout:

```bash
cd /opt/talker-live

# Docker Compose and Caddyfile from the repo
cp branches/main/docs/deploy/docker-compose.yml .
cp branches/main/docs/deploy/Caddyfile .

# Create per-branch env files from template
cp branches/main/docs/deploy/.env.template .env.main
cp branches/main/docs/deploy/.env.template .env.dev

# Edit each env file with branch-specific values
nano .env.main
nano .env.dev

# Create shared directories
mkdir -p logs/main logs/dev voices
```

## 6. Upload Voice Files

Copy `.safetensors` voice files to the shared voices directory:

```bash
# From your local machine:
scp voices/*.safetensors root@YOUR_IP:/opt/talker-live/voices/
```

## 7. Install Loki Docker Log Driver

```bash
docker plugin install grafana/loki-docker-driver:3.0.0 --alias loki --grant-all-permissions
```

## 8. Start the Stack

```bash
cd /opt/talker-live
docker compose up -d

# Watch logs
docker compose logs -f

# Check individual services
docker compose ps
```

## 9. Verify Deployment

```bash
# Health checks per branch
curl -s https://YOUR_DOMAIN/health/main
curl -s https://YOUR_DOMAIN/health/dev

# WebSocket test (install with: npm i -g wscat)
wscat -c "wss://YOUR_DOMAIN/ws/main?token=invite-code-abc123"
wscat -c "wss://YOUR_DOMAIN/ws/dev?token=invite-code-def456"

# TTS service health
docker compose exec tts-service curl -s http://localhost:8100/health

# Grafana
# Navigate to https://YOUR_DOMAIN/grafana/
# Login with admin / ${GRAFANA_PASSWORD}
```

### Verification Checklist

- [ ] `ufw status` shows only 22, 80, 443 open
- [ ] `docker compose ps` shows all services healthy
- [ ] `curl https://YOUR_DOMAIN/health/main` returns 200
- [ ] `curl https://YOUR_DOMAIN/health/dev` returns 200
- [ ] WebSocket connects on both branches
- [ ] Grafana accessible at `https://YOUR_DOMAIN/grafana/`
- [ ] Loki receiving logs (Grafana Explore → `{service="talker-main"}`)
- [ ] Bridge connects from player PC

## 10. Configure Grafana

1. Navigate to `https://YOUR_DOMAIN/grafana/`
2. Login with admin / `${GRAFANA_PASSWORD}`
3. Add Loki data source:
   - URL: `http://loki:3100`
   - Save & Test
4. Create a dashboard with:
   - Panel: Logs → `{service="talker-main"}` — main branch logs
   - Panel: Logs → `{service="talker-dev"}` — dev branch logs
   - Panel: Logs → `{service="caddy"}` — request logs
   - Panel: Logs → `{service="tts"}` — TTS service logs
   - Panel: Stat → count of log lines with "error" in last hour

---

## Operations

### View Logs

```bash
# All services
docker compose logs -f

# One branch
docker compose logs -f talker-main
docker compose logs -f talker-dev

# Shared services
docker compose logs -f tts-service
docker compose logs -f stt-service

# Or use Grafana → Explore → {service="talker-main"}
```

### Per-Branch Health Checks

```bash
curl -s https://YOUR_DOMAIN/health/main | python3 -m json.tool
curl -s https://YOUR_DOMAIN/health/dev | python3 -m json.tool
```

### Adding a New Branch

1. **Create worktree:**
   ```bash
   cd /opt/talker-live/repo
   git worktree add /opt/talker-live/branches/feature-x feature-x
   ```

2. **Add compose entry** — edit `docker-compose.yml`, duplicate a `talker-*` block:
   ```yaml
   talker-feature-x:
     build:
       context: ./branches/feature-x/talker_service
       dockerfile: Dockerfile
     restart: unless-stopped
     env_file: .env.feature-x
     environment:
       - WS_HOST=0.0.0.0
       - WS_PORT=5557
       - LOG_LEVEL=INFO
       - TTS_SERVICE_URL=http://tts-service:8100
       - STT_ENDPOINT=http://stt-service:8000/v1
     volumes:
       - ./logs/feature-x:/app/logs
     expose:
       - "5557"
     depends_on:
       - tts-service
       - stt-service
     logging:
       driver: loki
       options:
         loki-url: "http://localhost:3100/loki/api/v1/push"
         labels: "service=talker-feature-x"
   ```

3. **Create env file:**
   ```bash
   cp .env.main .env.feature-x
   nano .env.feature-x   # adjust tokens, pins as needed
   mkdir -p logs/feature-x
   ```

4. **Add Caddy route** — edit `Caddyfile`, add before the default handler:
   ```caddyfile
   handle_path /ws/feature-x {
       reverse_proxy talker-feature-x:5557
   }

   handle /health/feature-x {
       reverse_proxy talker-feature-x:5557
   }
   ```

5. **Build and start:**
   ```bash
   docker compose build talker-feature-x
   docker compose up -d
   ```

### Updating a Branch

```bash
cd /opt/talker-live/branches/main
git pull

cd /opt/talker-live
docker compose build talker-main
docker compose up -d talker-main
```

### Removing a Branch

1. **Stop and remove the container:**
   ```bash
   docker compose stop talker-feature-x
   docker compose rm -f talker-feature-x
   ```

2. **Remove compose entry** — edit `docker-compose.yml`, delete the service block.

3. **Remove Caddy route** — edit `Caddyfile`, delete the `handle_path` and `handle` blocks.

4. **Remove worktree and env:**
   ```bash
   cd /opt/talker-live/repo
   git worktree remove /opt/talker-live/branches/feature-x
   rm .env.feature-x
   rm -rf logs/feature-x
   ```

5. **Restart Caddy to apply config change:**
   ```bash
   docker compose restart caddy
   ```

### Add a New Player Token

```bash
# Edit the branch's env file
nano /opt/talker-live/.env.main

# Restart that branch's service
docker compose restart talker-main
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

**Resource budget per branch:** ~100 MB RAM for talker_service. With shared TTS (~500 MB) and STT (~300 MB), 2-3 branches fit comfortably in 16 GB. Monitor with `docker stats` if adding more.

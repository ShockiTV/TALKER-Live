## Tasks

### 1. Create multi-branch docker-compose.yml

**Files:** `docs/deploy/docker-compose.yml` (template for VPS)

- [x] Define `caddy` service (ports 80/443, Caddyfile mount)
- [x] Define `talker-main` service: build from `./branches/main/talker_service`, env_file `.env.main`, environment `TTS_SERVICE_URL=http://tts-service:8100` + `STT_ENDPOINT=http://stt-service:8000/v1`, logs mount `./logs/main:/app/logs`
- [x] Define `talker-dev` service: same pattern, build from `./branches/dev/talker_service`, env_file `.env.dev`, logs mount `./logs/dev:/app/logs`
- [x] Define `tts-service`: build from `./tts_service`, volumes `./voices:/app/voices:ro`, expose 8100
- [x] Define `stt-service`: image `fedirz/faster-whisper-server:latest-cpu`, expose 8000
- [x] Define `loki` and `grafana` services (same as current runbook)
- [x] Define volumes for caddy_data, caddy_config, loki_data, grafana_data

### 2. Create multi-branch Caddyfile

**Files:** `docs/deploy/Caddyfile` (template for VPS)

- [x] `handle_path /ws/main` → `reverse_proxy talker-main:5557`
- [x] `handle_path /ws/dev` → `reverse_proxy talker-dev:5557`
- [x] `handle /health/main` → `reverse_proxy talker-main:5557`
- [x] `handle /health/dev` → `reverse_proxy talker-dev:5557`
- [x] `handle_path /grafana/*` → `reverse_proxy grafana:3000`
- [x] Default → 404

### 3. Create .env template

**Files:** `docs/deploy/.env.template`

- [x] Document all fields: DOMAIN, TALKER_TOKENS, LLM keys, server-authority pins, TTS_SERVICE_URL, STT_SERVICE_URL, GRAFANA_PASSWORD
- [x] Indicate which fields differ per branch (TALKER_TOKENS, pins) vs shared (DOMAIN)

### 4. Rewrite VPS deploy runbook

**Files:** `docs/vps-deploy-runbook.md`

- [x] Update architecture diagram for multi-branch + shared TTS/STT
- [x] Update docker-compose section to reference multi-branch compose
- [x] Add section: "Setting up git worktrees" (clone repo, create worktrees per branch)
- [x] Add section: "Adding a new branch" (worktree + compose entry + env + Caddy route)
- [x] Add section: "Updating a branch" (git pull + build + restart)
- [x] Add section: "Removing a branch" (remove compose entry + worktree + env)
- [x] Update operations section for per-branch logs, health checks
- [x] Replace all references from `TALKER-Expanded` to `TALKER-live`
- [x] Update directory paths from `/opt/talker/` to `/opt/talker-live/`

### 5. Update repo name references

**Files:** `AGENTS.md`, `README.md`, `docs/Python_Service_Setup.md`, `.github/copilot-instructions.md`

- [x] Find and replace `TALKER-Expanded` → `TALKER-live` in documentation files
- [x] Update any git clone URLs to use new repo name
- [x] Note: Actual GitHub repo rename is done manually via GitHub Settings

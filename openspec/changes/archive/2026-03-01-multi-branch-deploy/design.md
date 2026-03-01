## Context

The current VPS runbook (`docs/vps-deploy-runbook.md`) deploys a single `talker-service` Docker container behind Caddy. We need to run N branch instances (typically 2-3: main + dev) from a single VPS, each accessible via a distinct URL path. The repo is being renamed from `TALKER-Expanded` to `TALKER-live`.

The `tts-stt-microservices` change (prerequisite) provides shared TTS and STT containers. This change wires them into the compose stack and adds per-branch routing.

## Goals / Non-Goals

**Goals:**
- Multiple talker_service instances, one per git branch, on a single VPS
- Path-based WebSocket routing via Caddy (`/ws/main`, `/ws/dev`)
- Per-branch environment files (`.env.main`, `.env.dev`) with independent config
- Shared TTS and STT containers referenced from the compose stack
- Git worktree-based branch management
- Updated runbook covering the full multi-branch workflow
- Repo rename from TALKER-Expanded to TALKER-live in all docs/scripts

**Non-Goals:**
- Auto-deploy on push (CI/CD) — manual `git pull && docker compose build` is fine
- Dynamic branch creation API — branches are added by editing compose + creating worktree
- Separate VPS per branch
- Any changes to `talker_service` Python code (already handled by change 1)

## Decisions

### 1. Path-based routing with Caddy `handle_path`

Each branch gets `/ws/<branch>` routed to its container. Caddy's `handle_path` strips the branch prefix before proxying, so `talker_service` receives requests at `/ws` — **zero code changes needed**.

```
/ws/main → talker-main:5557/ws
/ws/dev  → talker-dev:5557/ws
```

**Alternatives considered:**
- Subdomain routing (`main.talker.domain.com`): Cleaner isolation but requires wildcard DNS + TLS. Overkill for 2-3 branches.
- Port-based routing: Requires firewall holes, client port config, ugly.
- Token-prefix routing: Fragile, leaks routing concerns into auth tokens.

### 2. Git worktrees, not separate clones

`git worktree add ../branches/main main` creates a lightweight checkout sharing the same `.git` object store. Efficient disk use, easy branch switching.

Update flow: `cd branches/main && git pull && cd ../.. && docker compose build talker-main && docker compose up -d talker-main`.

### 3. Per-branch .env files

Each instance loads `env_file: .env.<branch>`. Allows independent LLM keys, tokens, server-authority pins. A `.env.template` documents all fields.

### 4. All internal ports stay :5557

Each container exposes 5557 internally. Docker networking isolates them — `talker-main:5557` and `talker-dev:5557` are different containers. No port conflict.

### 5. Shared services in same compose stack

TTS (`tts-service:8100`) and STT (`stt-service:8000`) live in the same `docker-compose.yml`. All `talker-*` instances reference them via `TTS_SERVICE_URL=http://tts-service:8100` and `STT_ENDPOINT=http://stt-service:8000/v1` in their env files.

### 6. Repo rename is cosmetic

GitHub handles redirects for renamed repos. Update references in `docs/vps-deploy-runbook.md`, `AGENTS.md`, `README.md`, and any scripts that reference the repo URL. VPS directory becomes `/opt/talker-live/`.

## Risks / Trade-offs

- **[Stale branches]** Forgotten dev branches consume resources → Operator responsibility. Could add a monitoring dashboard panel showing running branches.
- **[Compose complexity]** Each new branch requires editing docker-compose.yml + creating worktree → Acceptable for 2-3 branches. If needed later, a helper script can automate.
- **[Shared config drift]** Branches might need different LLM providers/models → Handled by per-branch `.env` files with server-authority pins.
- **[Repo rename]** Existing local clones on dev machines continue working via GitHub redirect → Update remote URL when convenient.

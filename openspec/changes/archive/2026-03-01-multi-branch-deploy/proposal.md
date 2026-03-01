# Proposal: Multi-Branch VPS Deployment

## Problem

The current VPS runbook deploys a single `talker-service` instance. We need to run multiple instances from different git branches (main, dev, feature branches) so testers can switch between versions. We also want to rename the repo from `TALKER-Expanded` to `TALKER-live`.

## Solution

### Path-based WebSocket routing via Caddy

Each branch instance gets its own URL path:

```
wss://talker.domain.com/ws/main?token=abc123   → talker-main:5557
wss://talker.domain.com/ws/dev?token=abc123     → talker-dev:5557
```

Caddy `handle_path` strips the `/main` or `/dev` prefix before proxying, so `talker_service` code requires **zero changes** — it still serves `/ws` internally.

Players switch branches by changing the Server URL in MCM settings (the bridge already reads this).

### Per-branch isolation

- Each branch instance runs from its own git worktree under `/opt/talker-live/branches/<name>/`
- Each branch has its own `.env.<branch>` file (separate tokens, LLM keys, pins)
- Logs are separated: `./logs/main/`, `./logs/dev/`
- TTS and STT are shared containers (from `tts-stt-microservices` change)

### Git worktrees for branch management

```bash
git clone repo.git /opt/talker-live/repo
cd repo
git worktree add ../branches/main main
git worktree add ../branches/dev dev
```

Update a branch: `cd branches/main && git pull`, then `docker compose build talker-main && docker compose up -d talker-main`.

### Repo rename

`TALKER-Expanded` → `TALKER-live`. GitHub handles redirects for existing clones. Update references in docs, scripts, and the runbook.

## Scope

- Rewritten: `docs/vps-deploy-runbook.md` — multi-branch architecture, docker-compose with N branch services + shared TTS/STT, updated Caddyfile, worktree-based deploys
- Modified: Docker compose — multiple `talker-*` services with per-branch build contexts and env files, shared `tts-service` and `stt-service`
- Modified: Caddyfile — path-based routing `/ws/<branch>`
- New: Per-branch `.env` template
- Docs: Update any references from `TALKER-Expanded` to `TALKER-live`
- NOT in scope: TTS/STT service extraction — that's `tts-stt-microservices`

## Dependencies

- `tts-stt-microservices` — shared TTS/STT containers must exist before the compose stack references them

## Risks

- **Resource ceiling**: Each branch instance is ~100 MB RAM. 2-3 instances is fine on CCX23 (16 GB). 5+ would need monitoring.
- **Worktree drift**: Forgotten branches stay running and consuming resources. Operator must manually remove stale worktrees and compose entries.
- **Repo rename**: Existing local clones keep working via GitHub redirect, but any hardcoded URLs in CI or scripts need updating.

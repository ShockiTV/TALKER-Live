## Purpose

Multi-branch VPS deployment: run N talker_service instances (one per git branch) behind Caddy with path-based WS routing, shared TTS/STT containers, and per-branch environment isolation.

## Requirements

### Requirement: Path-based WebSocket routing
Caddy SHALL route WebSocket connections to branch-specific talker_service instances based on URL path prefix.

#### Scenario: Main branch connection
- **WHEN** a client connects to `wss://domain/ws/main?token=abc123`
- **THEN** Caddy SHALL proxy the connection to the `talker-main` container at `/ws?token=abc123`

#### Scenario: Dev branch connection
- **WHEN** a client connects to `wss://domain/ws/dev?token=abc123`
- **THEN** Caddy SHALL proxy the connection to the `talker-dev` container at `/ws?token=abc123`

#### Scenario: Unknown branch path returns 404
- **WHEN** a client connects to `wss://domain/ws/unknown`
- **THEN** Caddy SHALL return HTTP 404

### Requirement: Per-branch health check endpoints
Caddy SHALL expose per-branch health check endpoints.

#### Scenario: Health check for main branch
- **WHEN** a GET request is sent to `https://domain/health/main`
- **THEN** Caddy SHALL proxy to `talker-main:5557/health` and return the response

#### Scenario: Health check for dev branch
- **WHEN** a GET request is sent to `https://domain/health/dev`
- **THEN** Caddy SHALL proxy to `talker-dev:5557/health` and return the response

### Requirement: Per-branch environment isolation
Each branch instance SHALL load its configuration from a branch-specific `.env` file.

#### Scenario: Main branch loads own env
- **WHEN** the `talker-main` container starts
- **THEN** it SHALL read configuration from `.env.main`

#### Scenario: Dev branch has different tokens
- **WHEN** `.env.dev` contains different `TALKER_TOKENS` from `.env.main`
- **THEN** the `talker-dev` instance SHALL authenticate using its own token set

### Requirement: Shared TTS and STT services in compose stack
The Docker compose stack SHALL include shared TTS and STT service containers accessible to all branch instances.

#### Scenario: Branch instances use shared TTS
- **WHEN** `talker-main` and `talker-dev` both have `TTS_SERVICE_URL=http://tts-service:8100`
- **THEN** both SHALL send TTS requests to the same `tts-service` container

#### Scenario: Shared voices directory
- **WHEN** the `tts-service` container starts
- **THEN** it SHALL load voice files from the shared `./voices` directory mounted read-only

### Requirement: Git worktree-based branch management
The deployment SHALL use git worktrees to manage per-branch source directories.

#### Scenario: Create worktree for new branch
- **WHEN** an operator runs `git worktree add ../branches/dev dev` from the repo clone
- **THEN** a lightweight checkout of the `dev` branch SHALL appear at `branches/dev/`

#### Scenario: Update a branch
- **WHEN** an operator runs `cd branches/main && git pull`
- **THEN** the `main` branch checkout SHALL be updated to the latest commit

### Requirement: Updated VPS deploy runbook
The runbook SHALL document the multi-branch architecture including compose stack, Caddyfile, worktree setup, env template, and per-branch operations.

#### Scenario: Runbook covers adding a new branch
- **WHEN** an operator reads the runbook
- **THEN** they SHALL find step-by-step instructions for adding a new branch instance (worktree + compose entry + env file + Caddy route)

#### Scenario: Runbook covers branch update
- **WHEN** an operator reads the runbook
- **THEN** they SHALL find instructions for updating a branch (`git pull` + rebuild + restart)

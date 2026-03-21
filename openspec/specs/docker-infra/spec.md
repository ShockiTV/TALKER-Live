## Requirements

### Requirement: Neo4j Community 5.x added to Docker Compose

A `neo4j` service using `neo4j:5.26-community` SHALL be added to `docs/deploy/docker-compose.yml`. It SHALL use named volumes for data and logs, be exposed internally on 7474 (HTTP) and 7687 (Bolt), and NOT expose Bolt externally. Auth SHALL be configured via `NEO4J_AUTH` environment variable.

#### Scenario: Neo4j starts and is reachable internally
- **WHEN** `docker compose up` completes
- **THEN** `talker-main` and `talker-dev` can connect to `bolt://neo4j:7687`

#### Scenario: Bolt not exposed on host
- **WHEN** `docker compose ps` shows neo4j ports
- **THEN** port 7687 is NOT published to the host interface

### Requirement: Ollama added to Docker Compose

An `ollama` service using `ollama/ollama:latest` SHALL be added, exposed internally only on port 11434. Model data SHALL persist in a named volume. `talker-*` services SHALL have `OLLAMA_BASE_URL=http://ollama:11434` in their environment.

#### Scenario: Ollama reachable from talker service
- **WHEN** `talker-main` calls `http://ollama:11434/api/embeddings`
- **THEN** the request succeeds without network error

#### Scenario: Model volume persists across restarts
- **WHEN** the Ollama container is restarted
- **THEN** `nomic-embed-text` does not need to be re-downloaded

### Requirement: Keycloak and its Postgres added to Docker Compose

A `keycloak` service using `quay.io/keycloak/keycloak:26.0` and a `postgres-keycloak` service using `postgres:16-alpine` SHALL be added. Keycloak SHALL be configured with `KC_HTTP_RELATIVE_PATH=/auth`, `KC_PROXY_HEADERS=xforwarded`, and `KC_HOSTNAME` pointing to the public domain.

#### Scenario: Keycloak persists realm config across restarts
- **WHEN** the Keycloak container is restarted
- **THEN** realm, client, and user config are preserved via the postgres volume

### Requirement: Caddyfile updated for new services

`docs/deploy/Caddyfile` SHALL be updated to: route `/auth/*` to Keycloak (no auth gate); apply JWT authorization to `/ws/*` and `/neo4j/*`; inject `X-Player-ID` from JWT `sub` on WS routes; inject static `X-Branch` per route; route `/neo4j/*` to `neo4j:7474` (admin role required).

#### Scenario: /ws/main injects correct branch header
- **WHEN** a valid JWT player connects to `/ws/main`
- **THEN** `talker-main` receives `X-Branch: main` and `X-Player-ID: {sub}`

#### Scenario: /auth routes bypass JWT check
- **WHEN** an unauthenticated browser navigates to `/auth/realms/talker/...`
- **THEN** the request reaches Keycloak without 401 rejection

### Requirement: Local dev compose file

A `docker-compose.yml` at the repository root SHALL provide a minimal local development setup with Neo4j only. The file SHALL be the default compose file so developers can use `docker compose up -d` without specifying `-f`. The talker_service Python process is run manually (via `launch_talker_service.bat`) for development purposes.

#### Scenario: Local dev starts Neo4j with default compose
- **WHEN** `docker compose up -d` is run from the repository root
- **THEN** a Neo4j 5.26-community container starts with `NEO4J_AUTH=none`
- **AND** `localhost:7474` is accessible for Neo4j Browser
- **AND** `localhost:7687` is accessible for Bolt connections
- **AND** data and logs persist via named volumes (`neo4j_data`, `neo4j_logs`)

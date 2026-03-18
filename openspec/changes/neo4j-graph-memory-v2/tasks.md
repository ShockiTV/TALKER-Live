## 1. Lua Checksum Module

- [x] 1.1 Create `bin/lua/framework/checksum.lua` with FNV-1a implementation using LuaJIT `bit` library
- [x] 1.2 Add pure-Lua arithmetic fallback path (via `pcall(require, "bit")`) for test environment compatibility
- [x] 1.3 Implement `event_checksum(event)` — hashes `{type, context, game_time_ms}` excluding `ts` and `witnesses`
- [x] 1.4 Implement `background_checksum(bg_data)` — hashes full background table structure
- [x] 1.5 Write `tests/framework/test_checksum.lua` covering: determinism, excludes-ts/witnesses, detects-mutation, background, fallback consistency

## 2. Lua Memory Store Checksum Integration

- [x] 2.1 Update `memory_store_v2:store_event()` to compute and attach `cs` field via `checksum.event_checksum()`
- [x] 2.2 Update compressed tier storage (summaries, digests, cores) to compute `cs` from text content and time range
- [x] 2.3 Verify `get_save_data()` / `load_save_data()` round-trip preserves `cs` field on all items
- [x] 2.4 Add tests in `tests/repo/test_memory_store_v2.lua` for checksum assignment and save/load round-trip

## 3. Lua Session UUID & Persistence

- [x] 3.1 Add UUID generation utility to `bin/lua/framework/utils.lua` (or a new `uuid.lua` in framework)
- [x] 3.2 Update `talker_game_persistence.script` `load_state()` to generate `session_id` if absent and persist it
- [x] 3.3 Update `publish_config_sync()` in `talker_ws_integration.script` to include `session_id` in the payload
- [x] 3.4 Write tests confirming new save generates UUID, existing save preserves it, and `config.sync` includes it

## 4. Lua Silent Event Publishing (index_only)

- [x] 4.1 Update `trigger.store_event()` in `bin/lua/interface/trigger.lua` to publish `game.event` with `flags.index_only = true` after storing
- [x] 4.2 Confirm `trigger.store_and_publish_event()` continues to publish without `index_only` flag (no regression)
- [x] 4.3 Add test in `tests/interface/test_trigger.lua` for both paths

## 5. Lua sync_manifest Query Handler

- [x] 5.1 Register `memory.sync_manifest` resource in `talker_ws_query_handlers.script`
- [x] 5.2 Implement handler: iterate all characters in `memory_store_v2`, build per-tier `{ts, cs}` arrays
- [x] 5.3 Include `global_events` top-level array in manifest response
- [x] 5.4 Write integration test confirming manifest structure and coverage of all characters and tiers

## 6. Python Storage Layer Foundation

- [x] 6.1 Create `talker_service/src/talker_service/storage/__init__.py`
- [x] 6.2 Implement `neo4j_client.py` — driver init, `is_available()` check, MERGE helpers, connection from `NEO4J_URI` env var
- [x] 6.3 Implement `schema.py` — `init_schema()` with `CREATE ... IF NOT EXISTS` for all vector and fulltext indexes
- [x] 6.4 Implement `embedding.py` — `EmbeddingClient` wrapping Ollama `/api/embeddings` with `nomic-embed-text`; graceful failure when Ollama unreachable
- [x] 6.5 Hook `init_schema()` and Ollama model-pull health check into `__main__.py` startup sequence
- [x] 6.6 Add `neo4j` Python driver to `pyproject.toml` / `requirements.txt`
- [x] 6.7 Write unit tests for `neo4j_client.is_available()` (no NEO4J_URI → False) and `embedding.py` graceful failure

## 7. Python Real-time Event Ingest

- [x] 7.1 Define `CONTEXT_ROLES_BY_TYPE` dict in storage layer mapping event type → list of context role keys
- [x] 7.2 Implement `neo4j_client.ingest_event(session_id, event, embedding)` — MERGE Event node, wire `HAS_EVENT`, `WITNESSED`, `INVOLVES` relationships
- [x] 7.3 Implement event text renderer: `"death: killer={DisplayName} [{tech_id}], victim=..."` lean template format
- [x] 7.4 Update `handlers/events.py` to create `asyncio.create_task()` for ingest before dialogue generation
- [x] 7.5 Implement `index_only` check in event handler — skip dialogue when flag is present
- [x] 7.6 Wrap ingest task in try/except so failures are logged without blocking dialogue
- [x] 7.7 Write unit tests: ingest fires before dialogue, index_only skips dialogue, ingest failure non-blocking, duplicate MERGE idempotent

## 8. Python Two-step Sync Protocol

- [x] 8.1 Add `session_id` and `player_id` / `branch` fields to `ConnectionState`
- [x] 8.2 Update `config.sync` handler to detect new `session_id` and trigger two-step sync
- [x] 8.3 Implement `sync.py` — `fetch_manifest()` via `state.query.batch`, diff manifest vs Neo4j, return missing `(ts, cs)` pairs
- [x] 8.4 Implement second fetch — request full entity data for missing items, upsert into Neo4j
- [x] 8.5 Implement entity reuse via MERGE: existing `(ts, cs)` nodes get new Session relationship without re-embedding
- [x] 8.6 Implement same-session reconnect detection: skip sync when `session_id` unchanged
- [x] 8.7 Write integration tests for sync delta logic and reconnect skip

## 9. Python Hybrid Context Retrieval

- [x] 9.1 Implement `retrieval.py` — `retrieve_context(session_id, char_id, query_text, budget, scope)` signature
- [x] 9.2 Implement vector search Cypher query scoped to character or global via Session traversal
- [x] 9.3 Implement BM25 fulltext search Cypher query including Character name fulltext boosting
- [x] 9.4 Implement RRF merge: `score = 1/(60 + rank_v) + 1/(60 + rank_b)`, sort descending
- [x] 9.5 Implement greedy token budget packing using `token_count` property
- [x] 9.6 Sort final result by `game_time_ms` ascending
- [x] 9.7 Write unit tests: character-scoped vs global scope, RRF merge with overlap, budget cutoff, chronological output, `token_count = len(text) // 4`

## 10. Python Auth Header Reading

- [x] 10.1 Update WS upgrade handler in `transport/ws_router.py` to read `X-Player-ID` and `X-Branch` headers
- [x] 10.2 Set `ConnectionState.player_id` (default `"local"`) and `ConnectionState.branch` (default `"main"`) from headers
- [x] 10.3 Pass `player_id` and `branch` through to Neo4j Session node creation
- [x] 10.4 Write unit tests for header extraction with and without Caddy headers present

## 11. Lua Bearer Token in WS Connect

- [x] 11.1 Add `ws_bearer_token` field to MCM config in `talker_mcm.script`
- [x] 11.2 Add getter to `bin/lua/interface/config.lua` for `ws_bearer_token`
- [x] 11.3 Update WS connect logic in `bin/lua/infra/ws/client.lua` to include `Authorization: Bearer <token>` header when token is set
- [x] 11.4 Write test confirming header is set when token non-empty and absent when empty

## 12. Docker Infrastructure

- [x] 12.1 Add `neo4j` service (`neo4j:5.26-community`) to `docs/deploy/docker-compose.yml` with named volumes, internal-only Bolt (7687 not published)
- [x] 12.2 Add `ollama` service (`ollama/ollama:latest`) with named volume, internal port 11434, `OLLAMA_BASE_URL` in talker env
- [x] 12.3 Add `keycloak` service (`quay.io/keycloak/keycloak:26.0`) and `postgres-keycloak` (`postgres:16-alpine`) with volume persistence
- [x] 12.4 Update `docs/deploy/Caddyfile` — add `/auth/*` route to Keycloak (no JWT gate), JWT authorization on `/ws/*` and `/neo4j/*`, header injection, `/neo4j/*` admin-only
- [x] 12.5 Create `docs/deploy/docker-compose.local.yml` override — host port bindings for neo4j (7474, 7687) and ollama (11434), omit loki/grafana
- [x] 12.6 Update `docs/vps-deploy-runbook.md` with Keycloak realm/client setup steps and first-user creation

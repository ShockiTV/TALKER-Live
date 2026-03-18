## Why

The current TALKER memory system is a flat per-character in-memory store (LuaJIT) persisted to a save file. Context for LLM prompt building is assembled by brute-force concatenation — the LLM receives whatever fits rather than what's relevant. There is no semantic search, no cross-character relationship exploitation, no persistent state between sessions at the Python service level, and no way to compute embeddings in the Lua/in-game context.

The goal is to replace brute-force context injection with a Neo4j-backed graph memory layer that mirrors the Lua store, enriches entities with embeddings, and enables hybrid retrieval (vector similarity + BM25 fulltext + graph traversal) against a configurable token budget.

## What Changes

- **Session scoping**: Lua generates a UUID per save slot on load, included in `config.sync`. Python uses this to scope all Neo4j operations. Old session nodes are orphaned (not deleted); entities are reused via content-addressed `(ts, checksum)` identity.
- **Lua checksums**: A FNV-1a checksum module (`framework/checksum.lua`) computes a deterministic composite key for every memory tier item, so Python can diff against Neo4j without sending the full save.
- **Two-step sync protocol**: On new session detection, Python fetches a compact manifest (ts+checksum arrays per character/tier) from Lua, diffs against Neo4j, then fetches only the missing/changed entities.
- **Real-time ingest**: Every `game.event` arriving in the Python event handler is indexed into Neo4j (async fire-and-forget) before dialogue generation. Silent events carry `index_only=true` and skip dialogue.
- **Neo4j graph model**: Nodes: `Session`, `Character` (`:PlayerCharacter` subtype), `Event`, `MemoryNode` (`:Summary/:Digest/:Core` subtypes), `Background`, `GlobalEvent`. Relationships encode witness lists, context roles (killer/victim/actor), and tier membership. Character names are fulltext-indexed; entity text is vector-indexed (768d).
- **Embedding via Ollama**: `nomic-embed-text` (768d) runs in the Docker stack. The Python service computes embeddings once per unique entity and reuses them across sessions.
- **Token-budgeted hybrid retrieval**: A new `storage/retrieval.py` module replaces flat memory injection. It runs hybrid search (RRF over vector + BM25 results), greedy-packs to a token budget, and returns items in chronological order.
- **Auth via Keycloak + Caddy**: Keycloak OIDC is added to the Docker stack. Caddy validates JWTs via JWKS and injects `X-Player-ID` and `X-Branch` headers. Python reads these headers for session scoping. The `?token=` WS param is replaced by `Authorization: Bearer` from Lua.
- **Deployment extensions**: `docker-compose.yml` gains `neo4j`, `ollama`, `keycloak`, and `postgres-keycloak` services. `Caddyfile` is updated for OIDC-gated routing including Neo4j Browser.

## Capabilities

### New Capabilities

- `lua-checksum`: FNV-1a checksum module in Lua (`framework/checksum.lua`); composite `(ts, cs)` identity key on all memory tier items
- `session-sync-protocol`: Session UUID persisted in Lua save; `memory.sync_manifest` resource in query handler; two-step manifest → diff → fetch sync on game load
- `realtime-event-index`: All game events indexed into Neo4j on arrival in the Python handler, before dialogue; silent events use `index_only=true` flag
- `neo4j-graph-model`: Node labels, relationship types, properties, vector index (768d), and fulltext index for Neo4j Community 5.x single-database setup
- `hybrid-context-retrieval`: Ollama embedding (nomic-embed-text), RRF merge of vector + BM25, greedy token-budget packing, chronological output
- `keycloak-auth`: Keycloak 26 OIDC realm `talker`; Caddy `caddy-security` JWT validation; `X-Player-ID` and `X-Branch` header injection; Lua Bearer token field
- `docker-infra`: Neo4j, Ollama, Keycloak, and postgres-keycloak Docker Compose additions; Caddyfile updates

### Modified Capabilities

- `game-event-handling`: Silent events now publish to Python with `index_only=true`; handler indexes first, then conditionally generates dialogue

## Impact

- `talker_service/src/talker_service/storage/`: new layer — `neo4j_client.py`, `embedding.py`, `retrieval.py`, `sync.py`, `schema.py`
- `talker_service/src/talker_service/handlers/events.py`: index before dialogue, respect `index_only` flag
- `talker_service/src/talker_service/__main__.py`: startup sequence includes Neo4j schema init and Ollama model pull
- `bin/lua/framework/checksum.lua`: new FNV-1a module (LuaJIT `bit`-based with pure-Lua fallback for tests)
- `bin/lua/domain/repo/memory_store_v2.lua`: items carry `cs` field alongside `ts`
- `bin/lua/interface/trigger.lua`: `store_event()` publishes silent events with `index_only=true`
- `gamedata/scripts/talker_game_persistence.script`: session UUID generation, save/load roundtrip
- `gamedata/scripts/talker_ws_query_handlers.script`: new `memory.sync_manifest` resource
- `gamedata/scripts/talker_ws_integration.script`: `session_id` in `config.sync` payload
- `docs/deploy/docker-compose.yml`: four new services
- `docs/deploy/Caddyfile`: Keycloak OIDC routes, header injection, Neo4j Browser proxy
- New Python dependency: `neo4j` driver; no new Lua deps

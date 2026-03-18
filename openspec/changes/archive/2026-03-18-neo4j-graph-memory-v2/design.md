## Context

TALKER Expanded uses a Lua-side in-memory store (`memory_store_v2`) for NPC memories. The Python service assembles LLM context by serializing this store verbatim — brute-force token injection with no relevance filtering, no cross-character relationship exploitation, and no persistence between sessions.

Current state:
- Lua: `memory_store_v2` with 5-tier per-character memory (events, summaries, digests, cores, background); items have `ts` but no checksums
- Python: stateless between sessions; assembles context from WS state queries on demand  
- Auth: `?token=` query param checked in Python; Caddy does nothing
- Deploy: docker-compose has caddy, talker-main, talker-dev, tts, stt, loki, grafana

## Goals / Non-Goals

**Goals:**
- Add Neo4j as persistent graph memory mirror, session-scoped and player-scoped
- FNV-1a checksums on Lua memory items for content-addressed entity identity
- Two-step sync on game load (manifest → diff → fetch diff only)
- Real-time ingest of all events (published + silent) into Neo4j with embeddings
- Hybrid retrieval (vector + BM25 + RRF) with token budget packing
- Keycloak OIDC replacing `?token=` auth; Caddy injects `X-Player-ID` + `X-Branch`
- Docker Compose additions: neo4j, ollama, keycloak, postgres-keycloak

**Non-Goals:**
- Multi-database Neo4j (requires Enterprise; single `talker` DB with session_id scoping instead)
- Immediate replacement of flat memory injection in prompts (retrieval is additive first)
- Custom Keycloak extension for invite-code registration (admin creates accounts manually for now)
- GPU support for Ollama (CPU inference acceptable at event-per-game-event frequency)

## Decisions

### D1: Single Neo4j DB, session_id + player_id + branch on Session nodes

Neo4j Community 5.x does not support multiple user databases. All entities go into the default `neo4j` DB. Session nodes carry `(id, player_id, branch)` as the scoping triple. Entity nodes are content-addressed and shared across sessions when underlying game state is identical.

**Rationale:** Avoids Enterprise licensing. Shared entity pool means embeddings computed once per unique event, not duplicated per session/branch.

**Alternative considered:** DB-per-player — requires Neo4j Enterprise or a separate Neo4j instance per tenant, both impractical.

### D2: Composite identity key (ts, cs) for immutable tiers

Time-travel save loading means `ts` alone is not stable — the same `ts` can refer to different content on different save loads. FNV-1a checksum over `{type, context, game_time_ms}` (excluding `ts` and `witnesses`) provides a content hash. `(ts, cs)` is the Neo4j MERGE key for all Event/MemoryNode nodes.

**Rationale:** Minimal CPU cost (1 FNV-1a per event at store time). Survives save reload correctly. Pure Lua + LuaJIT `bit` library, no C dependency.

**Alternative considered:** `ts` alone as identity key — fails on time-travel saves, producing ghost nodes.

### D3: `trigger.store_event()` publishes index_only to Python

Change: `store_event()` (previously Lua-only) also publishes `game.event` with `flags.index_only = true`. Python indexes first (async fire-and-forget), then checks `index_only` before dialogue. Ensures full event history is mirrored in Neo4j including silent events (reloads, jams, transitions).

**Rationale:** All events have retrieval value. Silent events provide timeline density that enriches context even without dialogue.

### D4: Event text uses lean template format

Event text stored on Neo4j nodes: `"death: killer={DisplayName} [{tech_id}], victim={DisplayName} [{tech_id}]"`. Both display name (BM25 name matching) and technical ID (exact matching, edge extraction) are colocated. Text rendered in Python at ingest time from event payload fields.

**Rationale:** Reproducible and stable (no LLM calls at index time). Including tech IDs preserves exact-match capability.

### D5: Ollama nomic-embed-text 768d

`nomic-embed-text` via Ollama for embeddings. 768 dimensions — good quality/speed tradeoff (~15ms CPU for short texts). Model pulled by the Python service on startup via health-check loop if not present.

**Rationale:** Already in stack as Ollama client infrastructure exists. 768d balances quality (vs 384d) and speed (vs 1024d). Strong retrieval performance on 50–300 token texts.

### D6: Python storage layer at `talker_service/src/talker_service/storage/`

New module:
```
storage/
  __init__.py
  neo4j_client.py   # Connection, MERGE helpers, availability check
  embedding.py      # Ollama embedding wrapper
  retrieval.py      # Hybrid search + RRF + token budget packing
  sync.py           # Two-step sync protocol
  schema.py         # Cypher for index/constraint creation on startup
```

Uses official `neo4j` Python driver (sync driver wrapped in executor — simpler than async driver for fire-and-forget tasks). Layer is disabled when `NEO4J_URI` is unset for graceful local dev degradation.

### D7: Keycloak OIDC + Caddy caddy-security plugin

Caddy built with `xcaddy` including `caddy-security`. Keycloak realm `talker`, client `talker-client` (confidential). JWT validated via JWKS. `X-Player-ID` (JWT `sub`) and `X-Branch` (static per route) injected before proxying. Python trusts these headers without re-validation — Caddy is the trust boundary.

Lua MCM adds `ws_bearer_token` field. If set, Lua sends `Authorization: Bearer <token>` on WS upgrade.

**Alternative considered:** Python-issued JWT — more moving parts, harder key rotation.

## Risks / Trade-offs

- **Neo4j Community schema constraints** → Verify `CREATE VECTOR INDEX` and `CREATE FULLTEXT INDEX` on `neo4j:5.26-community` before implementing. Both are confirmed supported.
- **Caddy xcaddy build complexity** → Use pre-built `greenpau/caddy-security` image, pinned to a specific digest, rather than building from source.
- **Ollama CPU latency on VPS (~80–200ms/embedding)** → Fire-and-forget task means ingest queue growth only delays Neo4j state, not dialogue generation. Acceptable.
- **sync_manifest size (200 chars × 100 events = ~500KB)** → Only triggered on new `session_id`, not on every reconnect. Acceptable for a load-time operation.
- **Lua `bit` library absent in lua5.1.exe tests** → Pure-Lua arithmetic fallback via `pcall(require, "bit")` switching automatically.

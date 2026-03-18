## Requirements

### Requirement: Real-time Neo4j ingest in Python event handler

`handlers/events.py` SHALL create a non-blocking `asyncio.create_task()` for Neo4j ingest on every received `game.event`, BEFORE any dialogue generation. The ingest task SHALL render event text, compute embedding via Ollama, MERGE the event node in Neo4j, and wire session/character relationships.

#### Scenario: Ingest fires before dialogue
- **WHEN** a `game.event` arrives with dialogue-triggering content
- **THEN** `asyncio.create_task(neo4j_client.ingest_event(...))` is called before the dialogue generation awaitable

#### Scenario: Ingest failure does not block dialogue
- **WHEN** the Neo4j ingest task raises an exception
- **THEN** the exception is logged but dialogue generation proceeds normally

#### Scenario: Event text uses lean template
- **WHEN** an event of type `death` is ingested with `killer` and `victim` in context
- **THEN** the stored `text` field is `"death: killer={DisplayName} [{technical_id}], victim={DisplayName} [{technical_id}]"`

#### Scenario: Witness relationships created
- **WHEN** an event has a non-empty `witnesses` array
- **THEN** `(:Event)-[:WITNESSED_BY]->(:Character)` edges are created for each witness

#### Scenario: Context role relationships created
- **WHEN** an event has known context roles (e.g., `killer`, `victim`, `actor`)
- **THEN** `(:Event)-[:INVOLVES {role: "killer"}]->(:Character)` edges are created per `CONTEXT_ROLES_BY_TYPE` mapping

#### Scenario: Duplicate events are idempotent
- **WHEN** `ingest_event()` is called with a `(ts, checksum)` pair already in Neo4j
- **THEN** `MERGE` finds the existing node and no re-embedding or duplication occurs

### Requirement: Silent events published to Python with index_only flag

`trigger.store_event()` in `bin/lua/interface/trigger.lua` SHALL publish the stored event to Python via WebSocket with `flags.index_only = true` after storing it in `memory_store_v2`.

#### Scenario: Silent event reaches Python
- **WHEN** `trigger.store_event()` is called
- **THEN** a `game.event` WS message is sent with `flags.index_only = true`

#### Scenario: Published events are not affected
- **WHEN** `trigger.store_and_publish_event()` is called
- **THEN** the event is sent without `index_only` flag (existing behavior preserved)

#### Scenario: index_only events do not trigger dialogue
- **WHEN** Python receives a `game.event` with `flags.index_only = true`
- **THEN** dialogue generation is NOT triggered; only Neo4j indexing occurs

### Requirement: Neo4j ingest disabled gracefully when unavailable

If Neo4j is not configured or not reachable, the ingest path SHALL be skipped entirely without errors or impact to Python service startup.

#### Scenario: Service starts without Neo4j config
- **WHEN** `NEO4J_URI` environment variable is not set
- **THEN** `neo4j_client.is_available()` returns False and ingest calls are no-ops

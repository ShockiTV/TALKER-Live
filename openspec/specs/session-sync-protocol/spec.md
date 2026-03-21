## Requirements

### Requirement: Session UUID generated and persisted in Lua save

Lua SHALL generate a UUID-like session identifier on each new game save slot. The session ID SHALL be stored in the save data and re-used on subsequent loads of the same slot. It MUST be included in every `config.sync` message sent to Python.

#### Scenario: New save generates session ID
- **WHEN** `load_state` is called and the save data has no `session_id` field
- **THEN** a new UUID string is generated and stored in `save_data.session_id`

#### Scenario: Existing save preserves session ID
- **WHEN** `load_state` is called and the save data already has a `session_id`
- **THEN** the existing ID is used unchanged across the session

#### Scenario: Session ID included in config.sync
- **WHEN** `publish_config_sync()` is called (on game load, reconnect, or MCM change)
- **THEN** the published `config.sync` payload includes a `session_id` field matching the current Lua session ID

### Requirement: memory.sync_manifest resource in Lua query handler

A new `memory.sync_manifest` resource SHALL be registered in `talker_ws_query_handlers.script`. When queried, it MUST return a compact manifest of all characters in `memory_store_v2` with their per-tier arrays of `{ts, cs}` pairs, plus the global event buffer as an array of `{ts, cs}` pairs.

#### Scenario: Manifest covers all characters
- **WHEN** Python sends `state.query.batch` with `resource: "memory.sync_manifest"`
- **THEN** the response includes an entry for every character ID currently in `memory_store_v2`

#### Scenario: Manifest structure per character
- **WHEN** the manifest is returned
- **THEN** each character entry has `id` and `tiers` containing `events`, `summaries`, `digests`, `cores` — each being an array of `{ts, cs}` objects

#### Scenario: Global events included
- **WHEN** the manifest is returned
- **THEN** a top-level `global_events` array of `{ts, cs}` objects is present

### Requirement: Python performs two-step sync on new session

When Python receives `config.sync` with a `session_id` that differs from the ID stored on the current `ConnectionState`, it SHALL perform a two-step sync: first fetch the manifest, diff against Neo4j, then fetch only the missing/changed entities.

#### Scenario: New session triggers manifest fetch
- **WHEN** `config.sync` arrives with a `session_id` not matching the stored one
- **THEN** Python issues a `state.query.batch` for `memory.sync_manifest` before any dialogue generation

#### Scenario: Sync only fetches diff
- **WHEN** Python has 80% of a character's events already in Neo4j (matching ts+cs)
- **THEN** only the 20% missing items are fetched from Lua in the second batch query

#### Scenario: Background change detected by hash
- **WHEN** a character's background exists in Neo4j but its content hash differs
- **THEN** that character's background is included in the second fetch batch

#### Scenario: Same-session reconnect skips sync
- **WHEN** `config.sync` arrives with a `session_id` matching the already-stored one
- **THEN** no manifest fetch is triggered; session state is preserved

### Requirement: Existing entities reused across sessions

Neo4j entity nodes identified by `(ts, checksum)` composite key SHALL be reused across sessions when the same save data is loaded. A new Session node MUST be created, but existing Event/MemoryNode/Background nodes already in Neo4j MUST be wired to the new Session without re-insertion or re-embedding.

#### Scenario: Shared entity on same-save reload
- **WHEN** the same save is loaded in a new session (same ts+cs pairs present)
- **THEN** Neo4j `MERGE` finds the existing node and creates the relationship to the new Session without re-embedding

#### Scenario: Time-travel produces new entities
- **WHEN** the player loads an older save causing ts collision with different cs
- **THEN** the new `(ts, cs)` pair is treated as a distinct entity from the previous one

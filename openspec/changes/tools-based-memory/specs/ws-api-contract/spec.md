## MODIFIED Requirements

### Requirement: Service channel topics (Python → Lua)

The service channel SHALL support the following Python-to-Lua topics:

| Topic | Payload | Purpose |
|-------|---------|---------|
| `dialogue.display` | `{speaker, message, display_time}` | Display AI-generated dialogue |
| `state.query.batch` | `{queries: [...]}` | Batch state query request |
| `state.mutate.batch` | `{mutations: [...]}` | Batch state mutation request |
| `state.response` | `{id, results: [...]}` | Response to query or mutation |

#### Scenario: state.mutate.batch is a valid Python→Lua topic
- **WHEN** Python sends `{"t": "state.mutate.batch", "p": {"mutations": [...]}, "r": "corr-1"}`
- **THEN** Lua SHALL accept and dispatch the mutations to memory_store DSL
- **AND** respond with `{"t": "state.response", "p": {"results": [...]}, "r": "corr-1"}`

#### Scenario: memory.update topic is no longer valid
- **WHEN** a message with topic `memory.update` is received
- **THEN** it SHALL be ignored or logged as unknown topic

### Requirement: Game event message format

The `game.event` topic payload SHALL contain:

| Field | Type | Purpose |
|-------|------|---------|
| `event` | object | Serialized event `{type, context, game_time_ms, witnesses}` |
| `candidates` | array | Nearby NPC objects (serialized characters) |
| `world` | object | Scene context (location, time, weather) |
| `traits` | object | Map of `character_id` → `{personality_id, backstory_id}` for all candidates |

The `is_important` field SHALL NOT be present in the payload. Speaker selection is now performed by the LLM via tools.

#### Scenario: game.event payload structure
- **WHEN** Lua sends `game.event` with payload
- **THEN** payload SHALL contain `event`, `candidates`, `world`, `traits`
- **AND** payload SHALL NOT contain `is_important`

#### Scenario: candidates includes witness NPCs
- **WHEN** a death event triggers with 3 nearby NPCs
- **THEN** `candidates` SHALL contain serialized Character objects for those 3 NPCs

### Requirement: Service channel topics (Lua → Python)

The service channel SHALL support the following Lua-to-Python topics:

| Topic | Payload | Purpose |
|-------|---------|---------|
| `game.event` | `{event, candidates, world, traits}` | Game event with full context |
| `player.dialogue` | `{text, candidates, world, traits}` | Player chat with context |
| `player.whisper` | `{text, companion, world, traits}` | Player whisper to companion |
| `config.update` | `{key, value}` | Single MCM setting changed |
| `config.sync` | `{settings: {...}}` | Full MCM sync |
| `system.heartbeat` | `{}` | Connection health check |

#### Scenario: game.event includes traits
- **WHEN** Lua publishes a game.event
- **THEN** payload SHALL include `traits` map of `character_id → {personality_id, backstory_id}`

## REMOVED Requirements

### Requirement: memory.update topic (Python → Lua)
**Reason**: Memory mutations are now initiated by Python via `state.mutate.batch` and written directly to Lua's memory_store. The old `memory.update` command that replaced the entire narrative blob is obsolete.
**Migration**: Python sends `state.mutate.batch` with specific append/delete/set/update operations instead of a whole-narrative replacement.

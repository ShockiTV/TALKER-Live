## Requirements

### Requirement: Node labels and properties

The Neo4j graph SHALL use the following node types. All session-scoped nodes SHALL carry a `session_id` property. Entity identity nodes SHALL carry `(ts, cs)` as their composite MERGE key.

| Label | Identity key | Purpose |
|-------|-------------|---------|
| `Session` | `id` | One per save-load; scopes all queries |
| `Character` | `(game_id, session_id)` | NPC or player character |
| `Character:PlayerCharacter` | `(game_id, session_id)` | Player-controlled character |
| `Event` | `(ts, cs)` | Game event (content-addressed, shareable across sessions) |
| `MemoryNode:Summary` | `(ts, cs)` | Compressed summary tier |
| `MemoryNode:Digest` | `(ts, cs)` | Compressed digest tier |
| `MemoryNode:Core` | `(ts, cs)` | Compressed core tier |
| `Background` | `(character_id, cs)` | Per-character background (versioned by content hash) |
| `GlobalEvent` | `(ts, cs)` | Emission / psi-storm events |

#### Scenario: Session node created on sync
- **WHEN** Python processes a new `session_id` from `config.sync`
- **THEN** a `(:Session {id, player_id, branch, created_at})` node is MERGE'd in Neo4j

#### Scenario: Character node carries display name
- **WHEN** a Character is synced or first encountered in an event context
- **THEN** `(:Character {game_id, name, faction, experience, story_id, is_notable, session_id})` is created with human-readable `name`

#### Scenario: PlayerCharacter has distinct label
- **WHEN** a character is the player character
- **THEN** the node carries both `:Character` and `:PlayerCharacter` labels

### Requirement: Relationship types

The graph SHALL define the following relationship types.

| Relationship | From | To | Purpose |
|-------------|------|----|---------|
| `SCOPES` | Session | Character | Session owns this character instance |
| `HAS_EVENT` | Session | Event | Session includes this event |
| `HAS_GLOBAL_EVENT` | Session | GlobalEvent | Session includes this global event |
| `WITNESSED` | Character | Event/GlobalEvent | Character witnessed this event |
| `HAS_SUMMARY` | Character | MemoryNode:Summary | Character owns this summary |
| `HAS_DIGEST` | Character | MemoryNode:Digest | Character owns this digest |
| `HAS_CORE` | Character | MemoryNode:Core | Character owns this core |
| `HAS_BACKGROUND` | Character | Background | Character's current background |
| `INVOLVES` | Event | Character | Event involves character in a named role |

#### Scenario: INVOLVES carries role property
- **WHEN** a death event has `context.killer = "bandit_raider_1"`
- **THEN** `(:Event)-[:INVOLVES {role: "killer"}]->(:Character {game_id: "bandit_raider_1"})` is created

#### Scenario: WITNESSED edge from fanout
- **WHEN** an event has witnesses `["100", "200"]`
- **THEN** both `(:Character {game_id: "100"})-[:WITNESSED]->(:Event)` and `(:Character {game_id: "200"})-[:WITNESSED]->(:Event)` are created

### Requirement: Vector and fulltext indexes

The Neo4j database SHALL have a vector index on the `embedding` property of `Event`, `MemoryNode`, `Background`, and `GlobalEvent` nodes, and a fulltext index on `Character.name`.

#### Scenario: Character name fulltext index
- **WHEN** a Cypher fulltext query searches for `"Lukash"`
- **THEN** `(:Character {name: "Lukash"})` nodes are returned via the BM25 index

#### Scenario: Vector index supports similarity search
- **WHEN** a Cypher vector query runs against `event_embedding_idx`
- **THEN** Event nodes are returned ordered by cosine similarity to the query vector

#### Scenario: Indexes created on startup
- **WHEN** the Python service starts with Neo4j available
- **THEN** `schema.py` runs `CREATE VECTOR INDEX IF NOT EXISTS` and `CREATE FULLTEXT INDEX IF NOT EXISTS` for all required indexes

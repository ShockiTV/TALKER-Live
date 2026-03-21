# four-tier-memory-store

## Purpose

Per-NPC structured memory storage in Lua with four compactable tiers (events, summaries, digests, cores) plus an optional Background entity. Replaces the flat narrative blob memory store.

## Requirements

### Requirement: Per-NPC four-tier storage structure

The `memory_store` module SHALL store memory per character as a structured table with five fields: `events` (list), `summaries` (list), `digests` (list), `cores` (list), and `background` (table or nil). Each list item SHALL have a globally unique `ts` (timestamp) value assigned by `unique_ts()` that serves as both temporal ordering and identity key. The per-character monotonic `seq` field is removed.

#### Scenario: New character memory entry created
- **WHEN** an event is appended for a character with no existing memory
- **THEN** a new entry SHALL be created with empty `summaries`, `digests`, `cores` lists, nil `background`, and the event in `events`

#### Scenario: Timestamps are globally unique
- **WHEN** multiple events are appended for the same or different characters
- **THEN** each event SHALL receive a `ts` value from `unique_ts()` that is unique across all characters

#### Scenario: Memory entry has all five fields
- **WHEN** a character's memory is queried
- **THEN** the result SHALL contain `events`, `summaries`, `digests`, `cores`, and `background` fields

### Requirement: Event tier storage

The `events` tier SHALL store structured event objects with fields: `ts` (number, globally unique timestamp from `unique_ts()`), `type` (string, EventType), and `context` (table with event-specific fields). Events SHALL NOT store a `text` field — text is generated from templates at read time by Python. The `seq` field is removed; `ts` serves as both ordering and identity.

#### Scenario: Event stored without text or seq field
- **WHEN** a DEATH event is appended to a character's memory
- **THEN** the stored event SHALL contain `ts`, `type`, `context`
- **AND** SHALL NOT contain a `text` field or a `seq` field

#### Scenario: Context contains character references
- **WHEN** a DEATH event is stored
- **THEN** `context.victim` SHALL contain `{game_id, name, faction}` at minimum
- **AND** `context.killer` MAY be present with the same structure

### Requirement: Compressed tier storage

The `summaries`, `digests`, and `cores` tiers SHALL store compressed memory objects with fields: `ts` (number, globally unique timestamp from `unique_ts()`), `tier` (string), `start_ts` (number), `end_ts` (number), `text` (string), and `source_count` (number). The `start_ts` field serves as the dedup key for compacted items. The `seq` field is removed.

#### Scenario: Summary entry structure
- **WHEN** a summary is appended via mutation
- **THEN** it SHALL contain `ts`, `tier="summary"`, `start_ts`, `end_ts`, `text`, `source_count`
- **AND** SHALL NOT contain a `seq` field

#### Scenario: Core entry is self-describing
- **WHEN** a core entry exists
- **THEN** `tier` SHALL be `"core"` and `source_count` SHALL reflect how many lower-tier items it absorbed

#### Scenario: start_ts is unique per compacted item
- **WHEN** compaction produces a new summary from events [ts=100, ts=101, ts=102]
- **THEN** `start_ts` SHALL be 100 (minimum of source timestamps)
- **AND** `start_ts` SHALL be used as the dedup key in the `DeduplicationTracker`

### Requirement: Tier caps with oldest-eviction

Each tier SHALL have a configurable cap. When an append would exceed the cap, the oldest items (lowest `ts`) SHALL be evicted before the append. Default caps: events=100, summaries=10, digests=5, cores=5.

#### Scenario: Events tier at capacity
- **WHEN** events tier has 100 items and a new event is appended
- **THEN** the oldest event (lowest ts) SHALL be evicted
- **AND** the new event SHALL be appended

#### Scenario: Summaries tier at capacity
- **WHEN** summaries tier has 10 items and a new summary is appended
- **THEN** the oldest summary (lowest ts) SHALL be evicted

### Requirement: Background entity

The `background` field SHALL store a structured table with `traits` (list of strings), `backstory` (string), and `connections` (list of `{character_id, name, relation}` tables). Background MAY be nil for characters who have never been selected as speaker.

#### Scenario: Background initially nil
- **WHEN** a new character memory entry is created
- **THEN** `background` SHALL be nil

#### Scenario: Background set via mutation
- **WHEN** `set` operation targets `memory.background` for a character
- **THEN** `background` SHALL contain `traits`, `backstory`, `connections` fields

#### Scenario: Background traits updated
- **WHEN** `update` operation adds a trait and removes another
- **THEN** `traits` list SHALL reflect the addition and removal

### Requirement: Unified store DSL operations

The `memory_store` module SHALL provide five operations: `append(char_id, resource, items)`, `delete(char_id, resource, ids)`, `set(char_id, resource, data)`, `update(char_id, resource, ops)`, `query(char_id, resource, params)`. The `ids` parameter in `delete` SHALL use `ts` values (not `seq`).

#### Scenario: Append adds items to a tier
- **WHEN** `append("12467", "memory.events", {event})` is called
- **THEN** the event SHALL be added to character 12467's events list with a new `ts` from `unique_ts()`

#### Scenario: Delete removes items by ts
- **WHEN** `delete("12467", "memory.events", {100, 101, 102})` is called
- **THEN** events with ts 100, 101, 102 SHALL be removed from character 12467's events
- **AND** non-existent ts values SHALL be silently skipped

#### Scenario: Set replaces entire resource
- **WHEN** `set("12467", "memory.background", {traits={...}, backstory="...", connections={}})` is called
- **THEN** character 12467's background SHALL be replaced with the new value

#### Scenario: Update applies partial operators
- **WHEN** `update("12467", "memory.background", {["$push"]={traits="brave"}, ["$pull"]={traits="timid"}})` is called
- **THEN** "brave" SHALL be added to traits and "timid" SHALL be removed

#### Scenario: Query returns tier data
- **WHEN** `query("12467", "memory.events", {})` is called
- **THEN** all events for character 12467 SHALL be returned

#### Scenario: Query with timestamp filter
- **WHEN** `query("12467", "memory.events", {from_timestamp=300})` is called
- **THEN** only events with `timestamp >= 300` SHALL be returned

### Requirement: Event fan-out to witnesses

When an event occurs, the trigger layer SHALL call `memory_store:append()` for each witness NPC's events tier. A single `unique_ts()` value SHALL be assigned once and shared across all witness copies. This is a direct Lua function call, not a WS roundtrip.

#### Scenario: Event appended to all witnesses with same ts
- **WHEN** a DEATH event occurs with witnesses [Wolf, Fanatic, Stalker_123]
- **THEN** the event SHALL be appended to Wolf's, Fanatic's, and Stalker_123's events tiers
- **AND** all copies SHALL share the same `ts` value

#### Scenario: New witness gets memory entry created
- **WHEN** a witness has no existing memory entry
- **THEN** a new entry SHALL be created with global backfill (if applicable) plus the triggering event

### Requirement: Global event buffer and backfill

The `memory_store` SHALL maintain a `global_event_buffer` (cap: 30) for global events (emissions, psy storms). When a new memory entry is created for a character, all globals from the buffer SHALL be backfilled into the character's events tier before the triggering event.

#### Scenario: Global event stored in buffer
- **WHEN** an emission event occurs
- **THEN** it SHALL be appended to all existing NPCs' event tiers
- **AND** it SHALL be appended to `global_event_buffer`

#### Scenario: Backfill on first contact
- **WHEN** a new NPC is encountered (no memory entry) and `global_event_buffer` has 5 events
- **THEN** those 5 global events SHALL be backfilled into the NPC's events tier
- **AND** the triggering event SHALL be appended after the backfill

#### Scenario: Global buffer respects cap
- **WHEN** `global_event_buffer` has 30 items and a new global event arrives
- **THEN** the oldest global event SHALL be evicted

### Requirement: Save and load persistence

The `memory_store` SHALL provide `get_save_data()` and `load_save_data(data)` for game save/load. The save format SHALL include `memories_version = "4"` for migration detection. The `global_event_buffer` SHALL be included in the save data.

#### Scenario: Save data format
- **WHEN** `get_save_data()` is called
- **THEN** returned table SHALL contain `memories_version = "4"`, `memories` (map of char_id to memory tables), and `global_events` (list)

#### Scenario: Load v4 save data
- **WHEN** `load_save_data` is called with `memories_version = "4"`
- **THEN** all character memories and global buffer SHALL be restored

#### Scenario: Load v3 save data (migration from seq to ts)
- **WHEN** `load_save_data` is called with `memories_version = "3"` (per-character seq)
- **THEN** each item's `seq` field SHALL be replaced with a `ts` field
- **AND** collision-free timestamps SHALL be assigned using the bump algorithm
- **AND** the `next_seq` tracking field SHALL be removed
- **AND** a log message SHALL indicate migration occurred

#### Scenario: Load v2 save data (migration from flat narrative)
- **WHEN** `load_save_data` is called with `memories_version = "2"` (flat narrative blob)
- **THEN** each character's narrative SHALL be migrated to a single core-tier entry
- **AND** all other tiers SHALL start empty
- **AND** a log message SHALL indicate migration occurred

#### Scenario: Load nil save data
- **WHEN** `load_save_data(nil)` is called
- **THEN** the store SHALL be empty with no error

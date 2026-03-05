## Requirements

### Requirement: Static unique backgrounds data file

A static Lua data file `bin/lua/domain/data/unique_backgrounds.lua` SHALL contain structured background data for all unique NPCs (~120 entries), keyed by tech_name.

#### Scenario: Data file structure
- **GIVEN** the file `unique_backgrounds.lua` is loaded
- **THEN** it SHALL export a table keyed by tech_name (e.g., `"esc_2_12_stalker_wolf"`)
- **AND** each entry SHALL contain `backstory` (string), `traits` (list of 3-6 adjective strings), and `connections` (list of connection tables)
- **AND** each connection SHALL contain `name` (display name string), `id` (tech_name string), and `relationship` (descriptive string)

#### Scenario: Backstory text style
- **GIVEN** a backstory entry for any unique NPC
- **THEN** the `backstory` field SHALL be written in GM briefing style — atmospheric, dramatic, emphasizing personality hooks
- **AND** SHALL preserve the factual content from `texts/backstory/unique.py` but rewrite the voice

#### Scenario: Connection cross-references are valid
- **GIVEN** a connection entry with `id = "esc_m_trader"`
- **THEN** that `id` SHALL correspond to a valid tech_name present in `unique_npcs.lua` OR be a well-known non-unique NPC section name
- **AND** the `name` field SHALL match the NPC's in-game display name

#### Scenario: No engine dependencies
- **GIVEN** the data file is required from any Lua context
- **THEN** it SHALL NOT call any STALKER engine APIs, adapter functions, or engine facade methods
- **AND** it SHALL be a pure data module returning a table

### Requirement: One-time background seeding at load_state

The `talker_game_persistence.script :: load_state()` function SHALL seed unique NPC backgrounds into `memory_store_v2` when initializing a brand new save file.

#### Scenario: Brand new save gets seeded
- **WHEN** `load_state()` is called with `saved_data.compressed_memories == nil` (brand new save)
- **THEN** after initializing the empty memory store, the system SHALL iterate all entries in `unique_backgrounds.lua`
- **AND** for each entry, SHALL resolve the tech_name to a game_id
- **AND** SHALL populate `memory_store_v2` background for that game_id with the entry's `{backstory, traits, connections}`

#### Scenario: Existing save is not re-seeded
- **WHEN** `load_state()` is called with `saved_data.compressed_memories ~= nil` (existing save)
- **THEN** no background seeding SHALL occur
- **AND** the existing memory store data SHALL be loaded as normal

#### Scenario: NPC already has a background in new save
- **WHEN** seeding runs for a brand new save
- **AND** a character already has a non-empty background in `memory_store_v2` (e.g., from a previous seeding step)
- **THEN** the existing background SHALL NOT be overwritten

### Requirement: Tech_name to game_id resolution

The seeding function SHALL resolve each tech_name to a numeric game_id using the game engine's object system.

#### Scenario: Resolution via story_objects
- **GIVEN** the tech_name `"esc_2_12_stalker_wolf"`
- **WHEN** `story_objects.object_id_by_story_id["esc_2_12_stalker_wolf"]` returns a numeric game_id
- **THEN** that game_id SHALL be used as the character key in `memory_store_v2`

#### Scenario: Fallback via alife scan
- **GIVEN** a tech_name not found in `story_objects.object_id_by_story_id`
- **WHEN** the system scans `alife()` server objects
- **AND** finds an object where `se_obj:section_name()` matches the tech_name
- **THEN** that object's `id` SHALL be used as the game_id

#### Scenario: Unresolvable tech_name is skipped
- **GIVEN** a tech_name that cannot be resolved via either method (e.g., NPC not yet spawned)
- **THEN** that entry SHALL be silently skipped
- **AND** seeding SHALL continue for remaining entries

### Requirement: Seeded backgrounds are first-class

Seeded backgrounds SHALL be indistinguishable from LLM-written backgrounds. No special markers or metadata.

#### Scenario: No seeded marker
- **WHEN** a background is seeded for a unique NPC
- **THEN** the stored background SHALL NOT contain a `seeded` field or any other marker distinguishing it from LLM-written backgrounds

#### Scenario: Standard read/write/update flow applies
- **WHEN** the LLM later calls `background(action="read")` for a seeded NPC
- **THEN** it SHALL receive the seeded background data
- **AND** the LLM MAY update it via `background(action="update")` using the normal flow

### Requirement: No Python-side changes

This change SHALL NOT modify any Python service code. Background seeding is entirely a Lua-side concern.

#### Scenario: Python service unmodified
- **GIVEN** the background auto-seeding change is implemented
- **THEN** no files under `talker_service/src/` SHALL be modified
- **AND** the existing `_handle_background` handler SHALL continue to work as-is with the already-populated backgrounds

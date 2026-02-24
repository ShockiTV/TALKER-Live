## ADDED Requirements

### Requirement: Story ID from section_name

The task trigger SHALL capture `server_entity:section_name()` as the `story_id` for the task giver character. `section_name()` is a reliable base method on all `cse_alife_object` descendants and SHALL always be available. This story_id (e.g. `"esc_m_trader"`) is the same identifier used by `important.py` on the Python side.

#### Scenario: Server entity provides section_name

- **WHEN** `server_entity:section_name()` returns `"esc_m_trader"`
- **THEN** the task_giver character's `story_id` field SHALL be `"esc_m_trader"`

#### Scenario: Story ID included in character table

- **WHEN** the task_giver character table is constructed
- **THEN** it SHALL include a `story_id` field populated from `section_name()`

### Requirement: Safe character_name access

The task trigger SHALL access `server_entity:character_name()` using a type-checked fallback chain to populate the `name` field with the best-effort resolved display name. If `character_name` is not a function, it SHALL fall back to `"Unknown"`. The `name` field provides the display name (e.g. `"Sidorovich"`), while `story_id` provides the stable identifier.

#### Scenario: Normal server entity with character_name

- **WHEN** `server_entity:character_name()` is a valid function returning `"Sidorovich"`
- **THEN** the task event SHALL use `"Sidorovich"` as the NPC name

#### Scenario: Entity without character_name method

- **WHEN** `server_entity.character_name` is not a function
- **THEN** the task event SHALL use `"Unknown"` as the NPC name

### Requirement: Safe rank access

The task trigger SHALL access `server_entity:rank()` using a type-checked fallback. If `rank` is not a function, it SHALL fall back to `0`.

#### Scenario: Normal entity with rank

- **WHEN** `server_entity:rank()` returns `450`
- **THEN** the task event SHALL use `450` as the rank value

#### Scenario: Entity without rank method

- **WHEN** `server_entity.rank` is not a function
- **THEN** the task event SHALL use `0` as the rank value

### Requirement: Safe community access

The task trigger SHALL access `server_entity:community()` using a type-checked fallback. If `community` is not a function, it SHALL fall back to `"stalker"`.

#### Scenario: Normal entity with community

- **WHEN** `server_entity:community()` returns `"dolg"`
- **THEN** the task event SHALL use `"dolg"` as the community/faction value

#### Scenario: Entity without community method

- **WHEN** `server_entity.community` is not a function
- **THEN** the task event SHALL use `"stalker"` as the community value

### Requirement: Safe rank name resolution

The task trigger SHALL guard the `ranks.get_se_obj_rank_name()` call with a `type()` check on the rank value, falling back gracefully if the call fails.

#### Scenario: Valid rank produces rank name

- **WHEN** rank value is `450` and `ranks.get_se_obj_rank_name()` returns `"experienced"`
- **THEN** the task event SHALL use `"experienced"` as the rank name

#### Scenario: Fallback rank produces safe result

- **WHEN** rank value is `0` (from fallback)
- **THEN** the rank name resolution SHALL not crash and SHALL produce a valid string or default

### Requirement: Serializer includes story_id

The `serialize_character()` function in `infra/zmq/serializer.lua` SHALL include `story_id` in its output when present on the Character object. This is currently missing — `Character.new()` accepts `story_id` but `serialize_character()` drops it.

#### Scenario: Character with story_id serialized

- **WHEN** a Character has `story_id = "esc_m_trader"`
- **THEN** the serialized JSON SHALL include `"story_id": "esc_m_trader"`

#### Scenario: Character without story_id serialized

- **WHEN** a Character has `story_id = nil` (generic NPC)
- **THEN** the serialized JSON SHALL omit `story_id` (nil fields are excluded by default)

- **WHEN** rank value is `0` (from fallback)
- **THEN** the rank name resolution SHALL not crash and SHALL produce a valid string or default

# python-world-context (delta)

## MODIFIED Requirements

### Requirement: Aggregate World Context for Prompts

The system SHALL provide `build_world_context(scene_data, recent_events, state_client)` that aggregates all context sections.

#### Scenario: Full world context built
- **WHEN** build_world_context is called with scene_data
- **THEN** result includes dead leaders section if any
- **AND** includes dead important characters section if any
- **AND** includes info portions section if any disabled
- **AND** includes regional politics section if applicable
- **AND** includes faction standings section from `scene_data.faction_standings` if present
- **AND** includes player goodwill section from `scene_data.player_goodwill` if present

#### Scenario: Faction standings included in world context
- **GIVEN** scene_data contains `faction_standings = {"dolg_freedom": -1500, "army_stalker": 0}`
- **WHEN** build_world_context is called
- **THEN** the result SHALL include a "Faction standings:" section with formatted lines like `"Duty↔Freedom: Hostile"`

#### Scenario: Player goodwill included in world context
- **GIVEN** scene_data contains `player_goodwill = {"dolg": 1200, "freedom": -300}`
- **WHEN** build_world_context is called
- **THEN** the result SHALL include a "Player goodwill:" section with formatted lines like `"Duty: +1200 (Great)"`

#### Scenario: Faction data missing from scene
- **GIVEN** scene_data has no `faction_standings` or `player_goodwill` keys
- **WHEN** build_world_context is called
- **THEN** no faction sections SHALL appear (backward compatible)

#### Scenario: Empty world context when nothing notable
- **GIVEN** all leaders alive, no info portions, no regional context, no faction data
- **WHEN** build_world_context is called
- **THEN** returns empty string or minimal context

## ADDED Requirements

### Requirement: SceneContext faction fields

The `SceneContext` dataclass SHALL include two optional fields for faction data:
- `faction_standings: dict[str, int] | None` — flat dict of faction-pair relation values, default `None`
- `player_goodwill: dict[str, int] | None` — per-faction player goodwill values, default `None`

These fields SHALL be populated from the `query.world` response when present, and default to `None` when absent (backward compatible).

#### Scenario: SceneContext parses faction standings
- **WHEN** `SceneContext.from_dict({"loc": "l01_escape", "faction_standings": {"dolg_freedom": -1500}})` is called
- **THEN** the resulting `SceneContext.faction_standings` SHALL be `{"dolg_freedom": -1500}`

#### Scenario: SceneContext parses player goodwill
- **WHEN** `SceneContext.from_dict({"loc": "l01_escape", "player_goodwill": {"dolg": 1200}})` is called
- **THEN** the resulting `SceneContext.player_goodwill` SHALL be `{"dolg": 1200}`

#### Scenario: SceneContext handles missing faction data
- **WHEN** `SceneContext.from_dict({"loc": "l01_escape"})` is called (no faction keys)
- **THEN** `faction_standings` SHALL be `None`
- **AND** `player_goodwill` SHALL be `None`

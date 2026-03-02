## 1. Lua: Faction Data Builders

- [x] 1.1 Define `GAMEPLAY_FACTIONS` constant list in `talker_game_queries.script` (12 factions: stalker, dolg, freedom, csky, ecolog, killer, army, bandit, monolith, renegade, greh, isg)
- [x] 1.2 Implement `build_faction_matrix()` in `talker_game_queries.script` — iterate faction pairs, call `relation_registry.community_relation()`, return flat dict with alphabetically-sorted underscore-delimited keys
- [x] 1.3 Implement `build_player_goodwill()` in `talker_game_queries.script` — iterate factions, call `actor:community_goodwill()`, return dict keyed by faction ID
- [x] 1.4 Guard both functions against nil `relation_registry` / `db.actor` — return empty table on failure

## 2. Lua: Wire Into query.world

- [x] 2.1 Add `faction_standings = build_faction_matrix()` to the `query.world` handler result table in `talker_ws_query_handlers.script`
- [x] 2.2 Add `player_goodwill = build_player_goodwill()` to the same result table
- [x] 2.3 Verify fields pass through the existing `filter_engine.apply_projection()` when `query.fields` is specified

## 3. Python: Threshold Constants & Label Functions

- [x] 3.1 Add `FACTION_RELATION_THRESHOLDS` constants in `prompts/factions.py` (Allied >= 1000, Hostile <= -1000, Neutral between)
- [x] 3.2 Add `GOODWILL_TIERS` ordered list of (threshold, label) tuples in `prompts/factions.py` matching PDA tiers (Excellent >= 2000 through Terrible <= -2000)
- [x] 3.3 Implement `label_faction_relation(value: int) -> str` function
- [x] 3.4 Implement `label_goodwill(value: int) -> str` function

## 4. Python: Formatter Functions

- [x] 4.1 Implement `format_faction_standings(faction_standings, relevant_factions=None) -> str` — split keys, resolve display names, apply labels, filter by relevant factions
- [x] 4.2 Implement `format_player_goodwill(player_goodwill, relevant_factions=None) -> str` — resolve names, format as "Faction: +/-Value (Label)"
- [x] 4.3 Add `COMPANION_FACTION_TENSION_NOTE` constant string
- [x] 4.4 Export new functions and constants from `prompts/__init__.py`

## 5. Python: SceneContext Extension

- [x] 5.1 Add `faction_standings: dict[str, int] | None = None` field to `SceneContext` in `state/models.py`
- [x] 5.2 Add `player_goodwill: dict[str, int] | None = None` field to `SceneContext`
- [x] 5.3 Update `SceneContext.from_dict()` to parse both fields from response data, defaulting to None

## 6. Python: World Context Integration

- [x] 6.1 Update `build_world_context()` in `prompts/world_context.py` to accept and format `scene_data.faction_standings` using `format_faction_standings()`
- [x] 6.2 Update `build_world_context()` to accept and format `scene_data.player_goodwill` using `format_player_goodwill()`
- [x] 6.3 Inject `COMPANION_FACTION_TENSION_NOTE` into system prompt in the appropriate prompt builder
- [x] 6.4 Enrich world context in `ConversationManager.handle_event()` via `query.world` batch fetch → `build_world_context()` → appended to Lua world string

## 7. Tests

- [x] 7.1 Lua unit test for `build_faction_matrix()` — verify key format, no self-pairs, nil-safety
- [x] 7.2 Lua unit test for `build_player_goodwill()` — verify all factions present, nil-safety
- [x] 7.3 Python unit tests for `label_faction_relation()` — boundary values (1000, -1000, 999, -999)
- [x] 7.4 Python unit tests for `label_goodwill()` — all tier boundaries
- [x] 7.5 Python unit tests for `format_faction_standings()` — full format, filtered format, empty/None input
- [x] 7.6 Python unit tests for `format_player_goodwill()` — full format, filtered format, empty/None input
- [x] 7.7 Python unit test for `SceneContext.from_dict()` — with and without faction fields
- [x] 7.8 Python integration test: `build_world_context()` with faction data in scene_data produces expected sections

## 8. Documentation

- [x] 8.1 Update `docs/ws-api.yaml` — add `faction_standings` and `player_goodwill` fields to `query.world` response schema

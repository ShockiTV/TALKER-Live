## Why

NPCs currently reference a **static** `FACTION_RELATIONS` dict in Python (`prompts/factions.py`) that hardcodes faction pair attitudes as -1/0/1. In STALKER Anomaly — especially with GAMMA's warfare mode — faction relations shift dynamically during gameplay (territory changes, quest completions, kills). Player goodwill with each faction also changes frequently. The static dict cannot reflect any of this, causing NPCs to express attitudes that contradict the actual game state. The `query.world` handler already returns scene data (location, time, weather) but omits faction standings and player goodwill entirely, so Python has no dynamic source to draw from.

## What Changes

- **Add faction matrix and player goodwill to `query.world`**: Lua builds the live faction×faction relation matrix (via `relation_registry.community_relation`) and player goodwill per faction (via `actor:community_goodwill`), returning them as structured data in the existing `query.world` response.
- **Add Python formatter for dynamic faction data**: A new formatter in `prompts/factions.py` converts the raw numeric standings into human-readable prompt text with threshold labels (Allied/Neutral/Hostile for factions; Excellent/Good/Neutral/Bad/Terrible for goodwill).
- **Extend `SceneContext` to carry faction data**: The `state/models.py` `SceneContext` dataclass gains `faction_standings` and `player_goodwill` fields so the data flows through to prompt builders.
- **Replace static `FACTION_RELATIONS` usage**: Prompt builders that currently call `get_faction_relation()` / `get_faction_relations_text()` switch to the dynamic data from `SceneContext`. The static dict remains as a fallback for offline/test use but is no longer the primary source.
- **Inject companion faction tension note**: Add a system prompt note so companions express faction attitudes in dialogue even though they are mechanically safe from hostile factions as companions.

## Capabilities

### New Capabilities
- `dynamic-faction-data`: Lua-side builders for the live faction×faction matrix and player goodwill, added to the `query.world` response payload.
- `faction-prompt-formatter`: Python-side formatter that converts raw numeric faction standings and player goodwill into human-readable prompt text with threshold-based labels.

### Modified Capabilities
- `lua-state-query-handler`: `query.world` resource gains `faction_standings` and `player_goodwill` fields.
- `python-world-context`: `SceneContext` extended with faction standings and player goodwill; world context builder includes formatted faction text in prompts.

## Impact

- **Lua**: `talker_game_queries.script` gains two new functions (`build_faction_matrix`, `build_player_goodwill`). `talker_ws_query_handlers.script` `query.world` handler calls them and includes results in payload. Engine facade may need new delegation if called from `bin/lua/`.
- **Python**: `state/models.py` `SceneContext` gains two optional fields. `prompts/factions.py` gains threshold constants and a formatter. Prompt builders in `prompts/` and `handlers/events.py` updated to pass faction data to prompts. Static `FACTION_RELATIONS` dict and `get_faction_relation()` remain but are no longer the primary path.
- **Wire protocol**: `query.world` response payload grows by two optional keys (`faction_standings`, `player_goodwill`). Backward-compatible — Python defaults missing fields to empty.
- **Token cost**: ~250–350 additional tokens per event message for the full matrix + goodwill text. Acceptable given information density.
- **Tests**: New Lua tests for matrix/goodwill builders. Python unit tests for formatter and `SceneContext` parsing. E2E scenario validating faction data round-trip.

## Why

Event data currently contains human-translated strings for faction names and reputation tiers, which are created on the Lua side before transmission to Python. This prevents Python from doing context-aware text resolution and duplicates translation logic across codebases. Python already has the ID→text lookup pattern for personality/backstory (via `prompts/lookup.py`) - faction and reputation should follow the same pattern to enable consistent text resolution in the AI layer.

## What Changes

- **BREAKING**: `game_adapter.lua` sends technical faction IDs (e.g., "dolg", "killer", "csky") instead of display names (e.g., "Duty", "Mercenary", "Clear Sky")
- **BREAKING**: `game_adapter.lua` sends raw reputation integers (e.g., -1500, 0, 3500) instead of tier strings (e.g., "Terrible", "Neutral", "Excellent")
- `visual_faction` (disguise) already sends technical IDs from Lua - Python now resolves to display names
- Python `prompts/factions.py` re-keyed by technical faction names with new `resolve_faction_name()` function
- Python `prompts/models.py` and `state/models.py` Character.reputation type changed from `str` to `int`
- Prompt builder updated to display numeric reputation values and resolve faction IDs to display names

## Capabilities

### New Capabilities

_None - this is a data format migration, not a new feature_

### Modified Capabilities

- `python-prompt-builder`: Add `resolve_faction_name(faction_id)` lookup function following existing `resolve_personality()` pattern; display numeric reputation directly to LLM

## Impact

- **Lua**: `bin/lua/infra/game_adapter.lua` - stop translating faction/reputation
- **Lua**: `bin/lua/infra/STALKER/factions.lua` - `get_faction_name()` no longer called by game_adapter
- **Python**: `prompts/factions.py` - re-key dict by technical names, add resolve function
- **Python**: `prompts/lookup.py` - add faction resolution export
- **Python**: `prompts/helpers.py` - resolve visual_faction (disguise) to display name
- **Python**: `prompts/models.py`, `state/models.py` - Character.reputation type str→int
- **Python**: `prompts/builder.py` - resolve faction IDs, display numeric reputation, update REPUTATION_RULES for numeric scale
- **Event Store**: No backwards compatibility - existing stored events with old format will have inconsistent data

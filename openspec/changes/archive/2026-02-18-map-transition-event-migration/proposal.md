## Why

Map transition events currently send human-readable location names (e.g., "Cordon") from Lua. This couples Lua to text generation and prevents Python from customizing descriptions based on context (e.g., faction perspective, character knowledge). Moving to technical IDs enables Python to generate richer, context-aware descriptions.

Additionally, TALKER-fork includes detailed location descriptions in map transition events (e.g., "Garbage (an area connecting the Cordon to Rostok) is an area where radioactive trash heaps..."). This context helps the LLM generate more informed dialogue. Currently `destination_description` is sent from Lua but never used by Python's `describe_event()`. We need to port the descriptions to Python and actually use them.

## What Changes

- **Lua trigger**: Send technical location IDs (`l01_escape`) instead of human names (`Cordon`), plus `visit_count`
- **Python locations.py**: Add `LOCATION_DESCRIPTIONS` dict (ported from Lua) and `get_location_description()` function
- **Python helpers.py**: Update `MAP_TRANSITION` handler to:
  - Resolve technical IDs to human names
  - Include visit count text ("for the first time", "for the 2nd time", "again")
  - Append destination description to match fork output format

Event context fields:
- `source`: technical location ID (e.g., `l01_escape`)
- `destination`: technical location ID
- `visit_count`: number of times player has visited destination
- `companions`: array of companion Character objects
- Remove `destination_description` from Lua (generated in Python)

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `lua-event-creation`: MAP_TRANSITION events send technical IDs instead of human names

## Impact

- **Lua modified**: `gamedata/scripts/talker_trigger_map_transition.script`
- **Lua deleted**: `bin/lua/infra/STALKER/locations.lua` (no longer needed - Python handles all location lookups)
- **Python modified**: 
  - `talker_service/texts/locations.py` (add `LOCATION_DESCRIPTIONS` dict and `get_location_description()`)
  - `talker_service/src/talker_service/prompts/helpers.py` (update MAP_TRANSITION handler)
- **Breaking change**: None

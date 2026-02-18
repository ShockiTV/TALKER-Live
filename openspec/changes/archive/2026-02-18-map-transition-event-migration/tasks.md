## 1. Python Location Data

- [x] 1.1 Add `LOCATION_DESCRIPTIONS` dict to `talker_service/texts/locations.py` (port from Lua `bin/lua/infra/STALKER/locations.lua`)
- [x] 1.2 Add `get_location_description(technical_id)` function that returns description or empty string
- [x] 1.3 Add `format_description(text)` helper to resolve faction placeholders like `%stalker%` → "Loners"

## 2. Python Event Formatting

- [x] 2.1 Add `_format_visit_count(count)` helper to return "for the first time", "for the 2nd time", "for the 3rd time", or "again"
- [x] 2.2 Add `_format_companions(companions)` helper to return "Hip" or "Hip and Fanatic" format
- [x] 2.3 Update `MAP_TRANSITION` handler in `helpers.py` to resolve `source`/`destination` technical IDs to names
- [x] 2.4 Update `MAP_TRANSITION` handler to include visit count text in output
- [x] 2.5 Update `MAP_TRANSITION` handler to include companion names in output
- [x] 2.6 Update `MAP_TRANSITION` handler to append destination description

## 3. Lua Trigger Update

- [x] 3.1 Update `talker_trigger_map_transition.script` to send raw `level.name()` as `source` and `destination`
- [x] 3.2 Remove calls to `locations.get_location_name()` and `locations.describe_location_detailed()`
- [x] 3.3 Remove `destination_description` from event context
- [x] 3.4 Keep `visit_count` and `companions` fields as-is

## 4. Python Tests

- [x] 4.1 Add test for `get_location_description()` with known location
- [x] 4.2 Add test for `get_location_description()` with unknown location
- [x] 4.3 Add test for `format_description()` faction placeholder resolution
- [x] 4.4 Add test for `describe_event()` MAP_TRANSITION with companions
- [x] 4.5 Add test for `describe_event()` MAP_TRANSITION solo travel
- [x] 4.6 Add test for `describe_event()` MAP_TRANSITION visit count formatting

## 5. Cleanup

- [x] 5.1 Delete `bin/lua/infra/STALKER/locations.lua`
- [x] 5.2 Remove `require("infra.STALKER.locations")` from trigger script
- [x] 5.3 Verify no other files import `locations.lua`

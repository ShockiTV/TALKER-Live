## Why

The Lua `Event.is_junk_event()` function and its `JUNK_EVENT_TYPES` table are **100% dead code**. In Phase 2 architecture, Python handles all AI processing including event filtering. Lua's only job is to create events and publish them via ZMQ—it never needs to classify events as "junk."

Additionally, the function contains legacy event-type flag checks (`is_artifact`, `is_anomaly`, etc.) from TALKER-fork that are never set in TALKER-Expanded. This dead code clutters the codebase and confuses contributors.

## What Changes

- **Delete** `JUNK_EVENT_TYPES` table from `bin/lua/domain/model/event.lua`
- **Delete** `Event.is_junk_event()` function from `bin/lua/domain/model/event.lua`
- **Delete** tests for `is_junk_event()` from `tests/entities/test_event.lua`

## Capabilities

### New Capabilities

*None* - this is a cleanup change removing dead code.

### Modified Capabilities

*None* - no spec-level requirements are changing. The removed function was never called in production.

## Impact

- **Code**: `bin/lua/domain/model/event.lua` - delete ~30 lines of dead code
- **Tests**: `tests/entities/test_event.lua` - delete tests for removed function
- **Risk**: None. Function has zero callers in production code (only tests exercise it).
- **Breaking**: No breaking changes. Function was internal and unused.

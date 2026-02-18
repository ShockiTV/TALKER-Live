## 1. Remove Dead Code from Event Module

- [x] 1.1 Delete `JUNK_EVENT_TYPES` table from `bin/lua/domain/model/event.lua`
- [x] 1.2 Delete `Event.is_junk_event()` function from `bin/lua/domain/model/event.lua`

## 2. Remove Associated Tests

- [x] 2.1 Delete `test_is_junk_event_typed_events` test from `tests/entities/test_event.lua`
- [x] 2.2 Delete `test_is_junk_event_legacy_flags` test from `tests/entities/test_event.lua`

## 3. Verify

- [x] 3.1 Run Lua tests to confirm no regressions: `lua5.1.exe tests/entities/test_event.lua`

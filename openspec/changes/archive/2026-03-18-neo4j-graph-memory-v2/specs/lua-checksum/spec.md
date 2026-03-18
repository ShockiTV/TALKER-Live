## ADDED Requirements

### Requirement: FNV-1a checksum module

A pure-Lua FNV-1a checksum module SHALL exist at `bin/lua/framework/checksum.lua`. It MUST use the `bit` LuaJIT library for 32-bit bitwise operations when available and MUST fall back to pure-Lua arithmetic when `bit` is not present (e.g., test environment with lua5.1.exe). The module SHALL expose `event_checksum(event)` and `background_checksum(bg_data)` functions that return an 8-character lowercase hex string.

#### Scenario: Event checksum is deterministic
- **WHEN** `checksum.event_checksum(event)` is called twice with the same `type`, `context`, and `game_time_ms` fields
- **THEN** both calls return the same 8-character hex string

#### Scenario: Checksum excludes ts and witnesses
- **WHEN** two events have identical `type`, `context`, and `game_time_ms` but different `ts` values or different `witnesses` arrays
- **THEN** `event_checksum()` returns the same value for both

#### Scenario: Checksum detects context mutation
- **WHEN** two events differ in any `context` field value
- **THEN** `event_checksum()` returns different hex strings

#### Scenario: Background checksum covers full structure
- **WHEN** `checksum.background_checksum(bg_data)` is called with a background table
- **THEN** it returns an 8-character hex string that changes if any field in `bg_data` changes

#### Scenario: Pure-Lua fallback produces same result
- **WHEN** `bit` library is not available and the fallback arithmetic path is used
- **THEN** `event_checksum()` returns the same value as it would with `bit` for the same input

### Requirement: memory_store_v2 items carry checksum

Every item stored in `memory_store_v2` events tier SHALL have a `cs` field populated by `checksum.event_checksum()` at store time. Compressed tier items (summaries, digests, cores) SHALL have a `cs` field computed from their text content and time range.

#### Scenario: Checksum assigned on store_event
- **WHEN** `memory_store_v2:store_event(character_id, event)` is called
- **THEN** the stored item has a `cs` field with an 8-character hex string

#### Scenario: Checksum survives save/load round-trip
- **WHEN** `memory_store_v2:get_save_data()` is called and the result is passed to `memory_store_v2:load_save_data()`
- **THEN** all items retain their `cs` field unchanged

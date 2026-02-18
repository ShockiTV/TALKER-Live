## Context

The Lua codebase contains dead code from the pre-Phase 2 architecture when AI processing happened in Lua. After migrating to Python-based AI via ZMQ, several HTTP-related modules became unused. Additionally, `talker_game_load_check.script` references modules that were never created (`unique_backstories`, `unique_personalities`), which will cause errors during the dependency check.

**Current state:**
- `infra/HTTP/HTTP.lua` and `pollnet.lua` are only called by test files, not production code
- `infra/HTTP/json.lua` is still used (by ZMQ bridge, recorder)
- `domain/model/item.lua` is imported but never used by typed events
- `game_adapter.lua` has 2 functions (`get_player_weapon`, `create_item`) that are never called

## Goals / Non-Goals

**Goals:**
- Remove broken module references that cause load check errors
- Delete vestigial HTTP modules no longer needed after Python migration
- Remove unused imports and functions to reduce confusion
- Clean up related test code that tests dead modules

**Non-Goals:**
- Changing any production behavior (pure cleanup)
- Removing `json.lua` (still actively used)
- Refactoring working code
- Touching the Python codebase

## Decisions

### Decision 1: Delete HTTP.lua and pollnet.lua entirely

**Choice:** Delete both files rather than deprecate.

**Rationale:** These files have zero production callers. The only references are in:
- `tests/live/real_http_requests/test_REST.lua` (tests the dead code)
- Internal `require` within each other

**Alternatives considered:**
- Mark as deprecated: Adds noise, no benefit since nothing calls them
- Keep for potential future use: Violates YAGNI, Python handles all AI now

### Decision 2: Keep json.lua in infra/HTTP/

**Choice:** Keep `json.lua` in place despite other HTTP code being deleted.

**Rationale:** Still actively used by:
- `infra/zmq/bridge.lua`
- `infra/game_adapter_recorder.lua`
- `interface/recorder.lua`

**Alternatives considered:**
- Move to `infra/json.lua`: Would require updating all imports; no real benefit
- Move to `framework/`: Would create incorrect layering (infra depends on framework)

### Decision 3: Keep Item module but remove unused import

**Choice:** Remove `require("domain.model.item")` from `event.lua`, but keep `item.lua` file.

**Rationale:** `item.lua` is still used by `game_adapter.lua` through `create_item()`. However, `create_item()` is never called, so Item is transitively dead. We'll remove the import from event.lua but leave item.lua for now - it can be removed in a future pass once `create_item` is also removed.

### Decision 4: Delete test files that test dead code

**Choice:** Delete `tests/live/real_http_requests/` directory entirely.

**Rationale:** Contains only `test_REST.lua` which tests `HTTP.lua` - both are dead code.

## Risks / Trade-offs

**Risk: Breaking hidden callers**
→ Mitigation: Grep search confirmed zero production callers for all deleted code. Tests will catch any missed references.

**Risk: Losing HTTP capability if needed later**
→ Mitigation: Git history preserves the code. If HTTP is needed again, Python service is the right place for it anyway.

**Trade-off: Leaving Item module partially dead**
→ Accepted: Cleaner to do incremental cleanup. Item is only technically dead through transitive non-use.

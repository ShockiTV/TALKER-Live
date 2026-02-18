## Context

The Lua `Event.is_junk_event()` function and `JUNK_EVENT_TYPES` table exist in `bin/lua/domain/model/event.lua` but have no callers in production code. In Phase 2 architecture, Python handles all event filtering during prompt building. The Lua Event module only needs to create and describe events, not classify them.

## Goals / Non-Goals

**Goals:**
- Remove dead code (`is_junk_event`, `JUNK_EVENT_TYPES`) from Lua Event module
- Remove associated tests that only exercise dead code
- Reduce codebase confusion around "what does Lua do vs Python"

**Non-Goals:**
- Changing Python's `is_junk_event()` implementation (it's actively used)
- Changing event creation or publishing behavior
- Adding any new functionality

## Decisions

**Decision: Delete rather than deprecate**

The function has zero production callers. A deprecation period would serve no purpose since no code needs migration. Immediate deletion is cleaner.

**Decision: Remove tests entirely**

The tests in `test_event.lua` for `is_junk_event()` only exist to test the function being deleted. They should be deleted, not modified.

## Risks / Trade-offs

**Risk: Future need for Lua-side filtering** → *Low*. Phase 2 architecture explicitly delegates all AI logic to Python. If filtering were ever needed in Lua, it would be a new feature with fresh requirements.

**Risk: Fork compatibility** → *N/A*. TALKER-Expanded is the maintained version; TALKER-fork is archived.

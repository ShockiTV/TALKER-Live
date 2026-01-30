## Context

TALKER Expanded currently has two AI processing paths:

1. **Python Service (Phase 2+)**: ZMQ-based communication where Lua publishes events and Python handles all LLM calls, speaker selection, and memory compression
2. **Legacy Lua AI**: HTTP-based LLM calls directly from Lua via pollnet FFI bindings

The Python service path is mature, tested, and actively maintained. The legacy Lua AI path was kept as a fallback but:
- Has not been tested since Phase 2 changes
- References modules that may not exist (`infra.AI.requests`)
- Creates confusion about which path is "correct"
- Adds complexity to `talker.lua` with conditional logic

The MCM currently has toggles for "Enable ZMQ" and "Enable Python AI" which create a confusing matrix of states.

## Goals / Non-Goals

**Goals:**
- Remove all legacy Lua AI code paths and infrastructure
- Make Python service the single, mandatory AI processing path
- Simplify `talker.lua` by removing conditional AI routing
- Clean up MCM by removing now-irrelevant toggles
- Update documentation to reflect new mandatory requirements
- Provide clear error messaging when Python service is unavailable

**Non-Goals:**
- Changing how the Python service works internally
- Adding new AI processing features
- Modifying ZMQ communication protocol
- Supporting "offline" or "no-AI" modes (events still get stored, just no dialogue generated)

## Decisions

### Decision 1: Complete removal vs deprecation warnings

**Choice**: Complete removal of legacy code

**Rationale**: The legacy path is untested and likely broken. Adding deprecation warnings would require maintaining broken code. Clean removal is simpler and avoids confusion.

**Alternatives considered**:
- Deprecation warnings for one release cycle → Rejected: Extra maintenance burden for code nobody uses
- Keep as "emergency fallback" → Rejected: False sense of security, would need significant work to function

### Decision 2: MCM toggle handling

**Choice**: Remove both "Enable ZMQ" and "Enable Python AI" toggles entirely

**Rationale**: 
- "Enable Python AI" is meaningless when there's only one AI path
- "Enable ZMQ" is meaningless when ZMQ is the only communication path
- If users want to disable the mod, they can uninstall it or disable it in MO2
- Fewer toggles = simpler UX and less code to maintain

**Alternatives considered**:
- Keep "Enable ZMQ" as kill-switch → Rejected: Users can just disable the mod in their mod manager
- Keep both as legacy → Rejected: Creates confusing UX with no functional difference

### Decision 3: Error handling when Python service unavailable

**Choice**: Log warning on game load, show HUD message on first event, show recovery message when service reconnects, then continue silently

**Rationale**: 
- Don't spam the user with errors
- One-time notification is sufficient for disconnection
- Recovery notification confirms the service is working again
- Game should remain playable (events still stored)

**Alternatives considered**:
- Hard error preventing game load → Rejected: Too aggressive for a mod
- No notification → Rejected: User might not realize why NPCs are silent
- No recovery message → Rejected: User wouldn't know when to expect dialogue again

### Decision 4: Test handling

**Choice**: Remove tests for deleted code, update remaining tests to not mock legacy AI

**Rationale**: Tests should reflect actual code paths. Mocking removed code makes tests misleading.

**Alternatives considered**:
- Keep tests as documentation → Rejected: Misleading, tests should be executable

## Risks / Trade-offs

**[Risk] Users with broken Python setups get silent failures**
→ Mitigation: Clear error message on first failed dialogue attempt, documentation update

**[Risk] Breaking change may surprise users who haven't updated Python service**
→ Mitigation: Version bump, clear changelog entry marked BREAKING

**[Risk] Removing code that might have edge-case utility**
→ Mitigation: Git history preserves the code if ever needed; clean removal is reversible

**[Trade-off] Less flexibility for users**
→ Accepted: Complexity cost of dual paths outweighs theoretical flexibility benefit

## Migration Plan

1. **Delete legacy AI modules** (`bin/lua/infra/AI/` directory)
2. **Simplify talker.lua** - Remove conditional logic, always expect Python service
3. **Update MCM** - Remove "Enable Python AI" toggle and related strings
4. **Update load check** - Remove references to deleted modules
5. **Update tests** - Remove/update tests that reference legacy AI
6. **Update documentation** - AGENTS.md, Python_Service_Setup.md, README.md
7. **Version bump** - Mark as breaking change in changelog

**Rollback**: Revert git commit. No data migration involved.

## Open Questions

None - all questions resolved:
- ~~Toggle naming~~ → Resolved: Both toggles removed entirely (Decision 2)
- ~~Startup service check~~ → Resolved: Don't delay game load, just show HUD message if service unavailable (Decision 3)

## Context

The Python service receives event data from Lua via ZMQ. Currently, character data in events contains human-translated strings created on the Lua side:
- `faction`: Display names like "Duty", "Mercenary", "Clear Sky"  
- `reputation`: Tier strings like "Terrible", "Neutral", "Excellent"

This prevents Python from doing context-aware text resolution and duplicates translation logic across codebases. Python already has the ID→text lookup pattern for personality and backstory via `prompts/lookup.py` - faction and reputation should follow the same pattern.

The Lua `factions.lua` module already has a registry mapping technical IDs (e.g., "dolg") to display names (e.g., "Duty"). The Python `prompts/factions.py` has faction descriptions keyed by display name.

## Goals / Non-Goals

**Goals:**
- Lua sends technical faction IDs (e.g., "dolg", "killer", "csky") instead of display names
- Lua sends raw reputation integers instead of tier strings
- Python resolves faction IDs to display names using existing lookup pattern
- Python resolves visual_faction (disguise) IDs to display names (already sends technical IDs from Lua)
- Python passes numeric reputation values directly to LLM prompts (no tier conversion)
- Maintain consistent ID→text resolution pattern for faction (matching personality/backstory)

**Non-Goals:**
- Backwards compatibility with existing event store data (events are ephemeral per session)
- Migration of weapon or world_context fields (future phases)
- Changes to how personality/backstory lookup works (only adding new functions)

## Decisions

### Decision 1: Faction ID Format - Lowercase Technical Names

**Choice**: Use lowercase game engine IDs: `dolg`, `killer`, `csky`, `greh`, `ecolog`, `army`, `bandit`, `monolith`, `renegade`, `zombied`, `trader`, `stalker`, `isg`

**Rationale**: These are the actual IDs the game engine uses. No transformation needed on Lua side - just stop calling `get_faction_name()`.

**Note**: `visual_faction` (disguise field) already sends technical IDs from Lua - only Python-side resolution needed.

**Alternatives Considered**:
- Display names (current) - requires Python to reverse-lookup, or send both
- Uppercase IDs - unnecessary transformation

### Decision 2: Reputation as Raw Integer

**Choice**: Send raw reputation integer from game engine (range roughly -5000 to +5000) and pass directly to LLM prompts as numeric value.

**Rationale**: 
- LLMs can interpret numeric values contextually
- Simpler implementation - no tier mapping needed
- More granular information for the model
- Simpler Lua code - just return the number

### Decision 3: Resolution Functions Location

**Choice**: Add `resolve_faction_name()` to existing `prompts/lookup.py`

**Rationale**: Follows established pattern - all ID→text resolution in one place. Consumers already import from `lookup.py` for personality/backstory.

### Decision 4: Faction Descriptions Dict Re-keying

**Choice**: Re-key `FACTION_DESCRIPTIONS` dict in `prompts/factions.py` by technical names

**Rationale**: Direct lookup without mapping. The dict becomes:
```python
FACTION_DESCRIPTIONS = {
    "dolg": "Duty is a paramilitary organization...",
    "killer": "Mercenaries are professional killers...",
    # etc.
}
```

### Decision 5: Character Model Type Change

**Choice**: Change `Character.reputation` from `str` to `int` in both `prompts/models.py` and `state/models.py`

**Rationale**: Type must match the wire format. Numeric value is passed directly to prompts.

### Decision 6: Prompt Reputation Display

**Choice**: Display reputation as numeric value in prompts (e.g., "CURRENT REPUTATION: 1500") with updated REPUTATION_RULES explaining the numeric scale to the LLM.

**Rationale**: LLMs can interpret numeric context. Simpler than maintaining tier mappings.

## Risks / Trade-offs

**Risk: Test Breakage** → Existing tests may use display names for faction or string reputation. Mitigation: Update test fixtures to use technical IDs and integer reputation.

**Risk: Prompt Display Regression** → If resolution function not called, prompts show technical IDs. Mitigation: Audit all prompt builder code paths to ensure resolution is applied.

**Trade-off: Complexity Shift** → Moving translation to Python increases Python code but simplifies Lua and centralizes text in one codebase. Acceptable because Python is the primary prompt-building layer.

## Migration Plan

1. **Lua changes first**: Update `game_adapter.lua` to send technical IDs and raw integers
2. **Python models**: Update Character.reputation type to int
3. **Python factions.py**: Re-key dict by technical names, add `resolve_faction_name()`
4. **Python lookup.py**: Export faction resolution function
5. **Python prompt builders**: Update REPUTATION_RULES for numeric scale, display numeric reputation, resolve faction IDs
6. **Tests**: Update fixtures and assertions
7. No gradual rollout - deploy all changes together (single-player mod, no coordination needed)

## Open Questions

_None - design decisions are finalized based on exploration discussion._

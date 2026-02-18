## Context

TALKER-Expanded uses a typed event system where Lua triggers create structured events sent to Python via ZMQ. Python's `describe_event()` in `helpers.py` converts events to human-readable text for LLM prompts.

Current state:
- `talker_trigger_map_transition.script` sends `source` and `destination` as **human-readable names** (e.g., "Cordon")
- `destination_description` is sent but **never used** by Python
- Python's `MAP_TRANSITION` handler only outputs: `"Wolf traveled from Cordon to Garbage"`

TALKER-fork output (target): `"Wolf and their travelling companions Hip traveled from Cordon to Garbage for the first time. Garbage (an area connecting...) is an area where radioactive trash heaps..."`

## Goals / Non-Goals

**Goals:**
- Send technical location IDs from Lua, resolve names in Python
- Port `LOCATION_DESCRIPTIONS` from Lua to Python
- Match fork's output format: actor + companions + from/to + visit count + description
- Maintain backward compatibility during transition

**Non-Goals:**
- Faction-perspective descriptions (future enhancement)
- Changing MCM settings or trigger behavior
- Modifying other event types

## Decisions

### 1. Context Field Names

Use `source` and `destination` for technical IDs (same field names, different content).

**Rationale**: Simpler migration - same field names, just change what Lua sends from human names to technical IDs.

### 2. Visit Count in Context

Send `visit_count` as integer from Lua. Python formats: "for the first time" / "for the 2nd time" / "again" (>3 visits).

**Alternatives considered**:
- Send pre-formatted string from Lua: Rejected (keeps text generation in Python)
- Don't track visits: Rejected (loses fork functionality)

### 3. Companion Formatting

Python extracts companion names from `context.companions` array and formats: "Wolf and their travelling companions Hip and Fanatic traveled..."

**Rationale**: `witnesses` includes NPCs at destination; `companions` specifically tracks who traveled together.

### 4. Location Data in Python

Add to `talker_service/texts/locations.py`:
- `LOCATION_DESCRIPTIONS`: dict mapping technical ID → description string
- `get_location_description(technical_id)`: lookup function

**Rationale**: Centralize location data in existing locations.py module rather than create new file.

### 5. No Backward Compatibility

Python expects technical IDs in `source` and `destination`:
```python
source_id = ctx.get("source", "somewhere")
dest_id = ctx.get("destination", "somewhere")
```

**Rationale**: Clean break - Lua sends technical IDs, Python resolves to human names.

## Risks / Trade-offs

**[Risk]** Location descriptions contain faction placeholders like `%stalker%` → **Mitigation**: Port `format_description()` logic to Python or pre-resolve in Lua (decision: resolve in Python for consistency).

**[Risk]** Missing description for unknown location ID → **Mitigation**: Gracefully omit description, log warning.

**[Trade-off]** ~~Duplicating location data in Lua and Python~~ → Resolved: delete `bin/lua/infra/STALKER/locations.lua` after migration. Python becomes single source of truth for location data.

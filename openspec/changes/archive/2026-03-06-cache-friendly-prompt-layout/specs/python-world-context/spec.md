# python-world-context (Delta)

> **Change**: `cache-friendly-prompt-layout`
> **Operation**: MODIFIED

---

### MODIFIED: World context split between context block and per-turn instruction

**Was**: `build_world_context()` produced a single text blob injected into the system prompt, containing weather, time, location, inhabitants, faction standings, player goodwill, and info portions.

**Now**: World context output SHALL be split:

| Data | Destination | Rationale |
|------|-------------|-----------|
| Inhabitants (nearby NPCs) | Context block (`_messages[1]`) as BG-like entries | Static during session, benefits from cache |
| Faction standings | Context block (`_messages[1]`) as a static section | Rarely changes during session |
| Player goodwill | Context block (`_messages[1]`) | Rarely changes during session |
| Info portions (Brain Scorcher, Miracle Machine) | Context block (`_messages[1]`) | Static facts |
| Weather/time-of-day | Per-turn user message (Layer 4) | Changes every event |
| Location/level name | Per-turn user message (Layer 4) | Changes on map transition |

#### Scenario: Weather not in context block

WHEN `render_markdown()` is called on the context block
THEN the output SHALL NOT contain weather or time-of-day information

#### Scenario: Weather in turn instruction

WHEN a picker or dialogue user message is built
THEN it SHALL include current weather description and time-of-day

---

### MODIFIED: Inhabitants added as context block entries

**Was**: Inhabitants were rendered as part of the system prompt text.

**Now**: Notable inhabitants (nearby NPCs with importance) SHALL be added to the `ContextBlock` as background-like entries using `add_background()`. Their format in Markdown SHALL match standard BG entries:

```
## Name (Faction) [id:char_id]
Brief descriptor (alive/dead, rank, distance).
```

#### Scenario: Inhabitant added to context block

WHEN `build_world_context()` identifies nearby NPC "Nimble" (id "nim_01", faction "Loners")
THEN `context_block.add_background("nim_01", "Nimble", "Loners", descriptor)` SHALL be called

---

### MODIFIED: build_world_context() return type changes

**Was**: `build_world_context()` returned a single string for system prompt injection.

**Now**: `build_world_context()` SHALL return a structured result (or be split into separate functions) that separates:
1. Static context items (for context block)
2. Dynamic per-turn items (weather, time, location — returned as dict/dataclass for inclusion in turn instructions)

#### Scenario: Structured return

WHEN `build_world_context()` is called
THEN it SHALL return both static items (inhabitants, factions, info portions) and dynamic items (weather, time, location) as separate fields
AND the caller SHALL add static items to the `ContextBlock` and include dynamic items in the turn user message

## Context

The `ConversationManager._build_system_prompt()` constructs IIS the system prompt with faction context, personality, and tool instructions. Separately, `world_context.py` builds a "world context" section (dead leaders, dead important NPCs, info portions, regional politics) that currently only appears in the `_build_event_message()` world string from the Lua side.

The `texts/characters/important.py` already has ~35 characterized NPCs with `ids`, `name`, `role`, `faction`, `area`, and `description`. The filtering infrastructure exists in `world_context.py` (`_is_notable_relevant`, `_get_leaders`, `_get_important`, `_get_notable`, `_get_story_ids_for_area`). But none of this surfaces as a "who are these people" reference in the system prompt — it's only used for dead-character tracking.

The alive/dead status is already fetched via `query.characters_alive` in the pre-fetch batch query. This data flows through `build_world_context()` which already produces the dead leaders/important text.

## Goals / Non-Goals

**Goals:**
- Give the LLM a concise "Notable Zone Inhabitants" reference in the system prompt listing who important NPCs are, what they do, and where they operate
- Merge alive and dead character information into a single coherent section (instead of separate "dead leaders" and "inhabitants" sections)
- Filter by relevance: leaders globally visible, area-matched characters shown when player is nearby, event-referenced characters shown when they appear in recent events
- Keep token budget under ~400 tokens for this section (filtered ~15-20 characters per prompt, not all 35)

**Non-Goals:**
- Changing the `texts/characters/important.py` data model (no new fields)
- Adding Lua-side changes or new WS topics
- Making the inhabitants list dynamic based on game state beyond alive/dead (e.g., no relationship tracking)
- Generating unique backstories for these NPCs (that's Subsystem G)

## Decisions

### 1. Single merged section vs. separate dead/alive sections

**Decision**: Single "Notable Zone Inhabitants" section that lists relevant characters with status annotations.

**Rationale**: A merged section is more natural — "Barkeep runs the 100 Rads bar" or "Barkeep, who ran the 100 Rads bar, is dead" reads better than two separate lists. It also avoids the LLM seeing a character in the dead list but having no context about who they were.

**Format**:
```
**Notable Zone Inhabitants:**
- General Voronin, leader of Duty (alive)
- Barkeep, barkeep at the 100 Rads bar in Rostok (dead)
- Wolf, Head of security for stalkers at Rookie Village in Cordon (alive)
```

### 2. Where to inject in system prompt

**Decision**: Add the inhabitants section after world context, before tool instructions. The prompt order becomes: faction → personality → world context → **inhabitants** → tool instructions → response format.

**Rationale**: World context sets location/time, inhabitants flows naturally from that, and tools come last as the actionable instructions.

### 3. Builder function location

**Decision**: Add `build_inhabitants_context()` to `world_context.py` and integrate it into the existing `build_world_context()` pipeline. The `ConversationManager._build_system_prompt()` receives the complete world context string (already passed as `world` param).

**Alternative considered**: Building it directly in `conversation.py`. Rejected because `world_context.py` already has all the filtering logic and character access.

**Approach**: Refactor `build_world_context()` to include a "Notable Inhabitants" subsection that lists relevant characters with alive/dead annotations. The current separate "dead leaders" and "dead important" sections get folded into this unified view.

### 4. Passing alive_status to the builder

**Decision**: Reuse the existing `alive_status` dict that's already fetched in the pre-fetch batch. The `build_world_context()` function already accepts `alive_status: dict[str, bool]`. No new WS queries needed.

### 5. Character descriptions for characters without them

**Decision**: Characters without a `description` field get a faction-based fallback: "{name}, {faction_name}". The existing data already has descriptions for most characters. We may fill in a few missing ones as part of implementation cleanup but won't block on having descriptions for every single entry.

## Risks / Trade-offs

- **[Token budget]** → Mitigation: Area-based filtering keeps the list to ~10-15 characters per prompt. Leaders (~10) are always shown but are a fixed cost. If too many, we can add a cap.
- **[Stale alive/dead on first query]** → The alive_status is fetched once per event via pre-fetch batch. If an NPC dies mid-dialogue-generation, the status might be stale. Acceptable — same limitation exists for the current dead leaders feature.
- **[System prompt stability]** → The inhabitants section changes when the player moves areas, which means the system prompt isn't perfectly stable across turns. However, the section only changes on area transitions (infrequent), and most providers handle this fine. The existing world context already varies per-event anyway.

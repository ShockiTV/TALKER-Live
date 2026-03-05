## Why

The LLM currently only learns about important NPCs when they die — their names appear in the "dead leaders/characters" section of world context. But when these NPCs are alive, the LLM has no knowledge of who they are, what role they play, or why they matter. This means NPCs can't reference Barkeep when standing in Rostok, don't know Sidorovich runs the trade in Cordon, and can't gossip about faction leaders. The `texts/characters/important.py` registry already has ~35 characterized NPCs with names, factions, areas, and descriptions — this data just needs to be surfaced in the system prompt.

## What Changes

- Add a "Notable Zone Inhabitants" section to the `ConversationManager` system prompt listing characterized NPCs relevant to current context
- Filter inhabitants by relevance: leaders always shown, area-matched characters shown when player is in their area, event-referenced characters shown when they appear in recent events
- Include name, faction, role/description for each listed inhabitant
- Reuse the existing `texts/characters/important.py` CHARACTERS registry and `world_context.py` filtering logic (already has `_is_notable_relevant`, `_get_leaders`, `_get_important`, `_get_notable`)
- Mark dead inhabitants in the listing (merge with existing dead leader/important context) instead of having separate "dead leaders" and "inhabitants" sections

## Capabilities

### New Capabilities
- `notable-inhabitants-prompt`: System prompt section that lists notable NPCs relevant to the current context, built from the existing characters registry and filtered by area/event relevance

### Modified Capabilities
- `tool-based-dialogue`: System prompt construction adds the notable inhabitants section between faction/personality and tool instructions
- `python-world-context`: `build_world_context` gains ability to produce a "Notable Inhabitants" section showing living characters (not just dead ones), with dead characters annotated

## Impact

- **Python only** — no Lua changes needed
- `talker_service/src/talker_service/prompts/world_context.py` — new builder function for inhabitants prompt section
- `talker_service/src/talker_service/dialogue/conversation.py` — system prompt construction updated to include inhabitants
- `texts/characters/important.py` — may gain a few missing descriptions for characters that currently lack them
- Token budget: adds ~200-400 tokens to system prompt (filtered subset of ~35 characters). Leaders (~10) always shown, rest filtered by area/events
- No wire protocol changes, no Lua changes, no new WS topics

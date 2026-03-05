## Why

Unique/story NPCs (Sidorovich, Wolf, Barkeep, Strelok, etc.) have rich hand-written backstory texts in `texts/backstory/unique.py` (~120 entries), but these are only shown as a truncated 200-character snippet in the candidate list during dialogue generation. When the LLM first encounters a unique NPC, it calls `background(action="read")` and gets back null — then has to invent a background from scratch using `background(action="write")`, wasting a tool-call round and producing content that may contradict the established lore in the backstory texts.

Rather than intercepting this at runtime in Python, we pre-generate a static Lua data file (`unique_backgrounds.lua`) containing GM-style backstories, personality traits, and cross-referenced connections for all ~120 unique NPCs. This data is seeded into `memory_store_v2` as a one-time migration on first game start — after which, standard background handling takes over.

## What Changes

- Add `bin/lua/domain/data/unique_backgrounds.lua` — a static Lua table (AI-agent-generated) mapping tech_name → `{backstory, traits, connections}` for all ~120 unique NPCs
- Backstory texts are GM-style rewrites of the `unique.py` source material: atmospheric, dramatic, emphasizing personality and dramatic hooks rather than encyclopedic facts
- Traits are AI-extracted personality adjectives (3-6 per NPC)
- Connections are cross-references to other unique NPCs, parsed from backstory text mentions AND enriched with STALKER universe knowledge
- Add seeding logic in `talker_game_persistence.script`: on first game start (no existing save data), iterate the seed table, resolve tech_name → game_id via `story_objects`, and populate `memory_store_v2` backgrounds
- After seeding, standard background(read/write/update) flow handles everything — no special runtime behavior

## Capabilities

### New Capabilities
- `background-auto-seeding`: One-time background seeding for all unique NPCs on first game start, populating `memory_store_v2` with pre-authored backgrounds

### Modified Capabilities
- None — no Python changes, no wire protocol changes, no tool handler changes

## Impact

- **Lua only** — no Python changes, no wire protocol changes, no new WS topics
- `bin/lua/domain/data/unique_backgrounds.lua` — new static data file (~120 entries)
- `gamedata/scripts/talker_game_persistence.script` — seeding logic in `load_state()` when `compressed_memories` is nil
- Token savings: eliminates one `background(write)` tool-call round per unique NPC's first encounter (~500-1000 tokens saved per interaction)
- Seeded backgrounds are first-class — identical in shape to LLM-written backgrounds, no special markers

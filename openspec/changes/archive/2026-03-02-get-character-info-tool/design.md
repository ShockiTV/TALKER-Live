## Context

The ConversationManager (in `dialogue/conversation.py`) has a working tool loop with two tools: `get_memories` and `background`. The LLM can query memory tiers and read/write backgrounds during dialogue generation. However, it cannot discover who else is in a character's squad, cannot determine gender for generic NPCs, and cannot obtain backgrounds for squad members in a single call.

The design doc (Tool 3: `get_character_info`) specifies a tool that returns a character's full info — including gender derived from `sound_prefix` — plus an array of squad members with their own gender and background data. Calling this tool has a side-effect: squad members not yet in `memory_store` get memory entries created with global event backfill.

Existing infrastructure:
- `query.character` resource handler returns `serialize_character(char)` — flat character data without gender or squad
- `get_squad(obj)` in `talker_game_queries.script` returns the squad object (or nil)
- `get_companions(exclude_npc_id)` returns player companions
- `serialize_character()` in `infra/ws/serializer.lua` includes `sound_prefix` but not `gender`
- `memory_store_v2` has entry creation and global backfill logic

## Goals / Non-Goals

**Goals:**
- Add `get_character_info` tool to the ConversationManager's tool set
- Implement `query.character_info` Lua resource handler that returns character + squad members + gender + backgrounds
- Trigger squad discovery (memory entry creation + global backfill) for squad members not yet in memory store
- Derive gender from `sound_prefix` in the Lua query handler and include it in the response
- Format the response for LLM consumption in the Python handler

**Non-Goals:**
- Changing the `Character` domain model to include a `gender` field (gender is derived at serialization time only)
- Pre-seeding unique NPC backgrounds (deferred to a separate unique-backgrounds change)
- Changing how `get_memories` or `background` tools work
- Adding gender to event messages or the pre-fetch batch
- Player gender in system prompt (already handled by existing MCM `female_gender` toggle)

## Decisions

### D1: New resource name `query.character_info` vs extending `query.character`

**Decision**: Add a new `query.character_info` resource rather than extending `query.character`.

**Rationale**: `query.character` is a simple character-by-ID lookup with field projection. `character_info` has squad resolution, gender derivation, background lookup, and mutation side-effects (memory entry creation). Mixing these into `query.character` would violate its single-responsibility read-only contract. A new resource makes the side-effects explicit and keeps `query.character` lightweight.

### D2: Gender derivation in Lua, not Python

**Decision**: The Lua query handler derives `gender` from `sound_prefix` and includes it in the response. Python receives `gender` as a string field.

**Rationale**: `sound_prefix` is already available on the Character object in Lua (and serialized on the wire). Deriving gender in Lua keeps the mapping close to the engine data source and avoids Python needing to know STALKER's voice system conventions. The mapping is trivial: `sound_prefix == "woman"` → `"female"`, otherwise → `"male"`.

### D3: Squad discovery as side-effect of the query handler

**Decision**: When `query.character_info` is processed, the handler checks each squad member against `memory_store_v2`. If a squad member has no entry, it creates one and backfills globals.

**Rationale**: The design doc specifies two memory entry creation paths: witness (event fan-out) and squad discovery (`get_character_info` call). The side-effect is intentional — the LLM calling `get_character_info` means it's about to generate dialogue involving these characters, so they need memory entries. Doing this in the query handler (Lua) ensures it happens atomically before the response is sent.

### D4: Background included in response from memory store

**Decision**: The query handler reads each character's `memory.background` from `memory_store_v2` and includes it in the response (or `null` if none exists).

**Rationale**: The LLM needs to know existing backgrounds to generate connected backstories. Including backgrounds in the `get_character_info` response eliminates a separate `background(id, "read")` call per squad member. The memory store read is local (no WS roundtrip) since it runs in Lua.

### D5: Serialization via new `serialize_character_info` function

**Decision**: Add `serialize_character_info(char, squad_members, memory_store)` to `infra/ws/serializer.lua` that builds the extended response format. This delegates to `serialize_character()` for the base fields, then adds `gender` and `background`.

**Rationale**: Keeps serialization in the existing serializer module (consistent with `serialize_character`, `serialize_event`, etc.). The function handles the gender derivation and background lookup per character. The query handler calls this function and returns the result.

### D6: Python handler dispatches single sub-query

**Decision**: `_handle_get_character_info(character_id)` sends a single `state.query.batch` with one `query.character_info` sub-query. The Lua side does all the heavy lifting (squad resolution, gender, backgrounds, side-effects).

**Rationale**: This minimizes WS roundtrips. The alternative — Python sending separate queries for character, squad, backgrounds — would require multiple roundtrips or complex batch construction. Since Lua has direct access to game objects and memory store, it's more efficient to resolve everything server-side.

### D7: Tool response shape matches design doc

**Decision**: The tool returns `{"character": {..., "gender": "male"|"female", "background": {...}|null}, "squad_members": [{..., "gender": ..., "background": ...}, ...]}`.

**Rationale**: Matches the design doc specification exactly. The `character` object extends the standard serialized character with `gender` and `background`. `squad_members` is an array of the same shape. Empty squad returns `[]`.

## Risks / Trade-offs

### R1: Squad resolution performance
**Risk**: `get_squad()` iterates game objects, which may be slow for large squads or during heavy gameplay.
**Mitigation**: Squad sizes are typically 2-6 members in STALKER. The `get_squad()` function already exists and is used by game scripts. If performance is an issue, the query handler can cache squad composition per game tick.

### R2: Side-effect in a query handler
**Risk**: `query.character_info` creates memory entries (a mutation) inside a query handler, which violates the read-only convention of query handlers.
**Mitigation**: This is an intentional design choice from the design doc — squad discovery needs to happen when the LLM asks about a character. The mutation is idempotent (creating an entry that already exists is a no-op). Document the side-effect clearly in the handler and spec.

### R3: Background data may be large
**Risk**: If a character has a verbose background, the tool response could be large (especially with multiple squad members).
**Mitigation**: Backgrounds are structured (traits list, backstory paragraph, connections list) with modest sizes (~1.5 KB per background at most). Even a full squad of 6 with backgrounds totals ~10 KB — well within tool response limits.

### R4: Race between squad discovery and event fan-out
**Risk**: An event could trigger fan-out to a witness at the same time `get_character_info` creates their memory entry via squad discovery.
**Mitigation**: Both paths use `memory_store_v2:ensure_entry(character_id)` which is idempotent — if an entry already exists, it's a no-op. The global backfill is also idempotent (skips events already in the character's buffer).

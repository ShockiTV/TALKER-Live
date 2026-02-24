## Context

Four bugs were discovered by diffing the upstream fork (TALKER-Expanded-source) against our fork baseline (TALKER-fork). Three are in `gamedata/scripts/` trigger files (Lua game layer), one is in the Python dialogue cleaner. All four are independent — no shared state, no ordering dependencies.

Current state of each bug:
- **Injury trigger**: `actor_on_hit_callback` passes `who` directly into event creation with no defensive checks. The engine can pass `nil` (fall damage), an anomaly object (overlaps with anomaly trigger), or the player themselves (self-damage from grenades).
- **Task trigger**: `server_entity:character_name()` and siblings called without pcall. Engine entities from modded NPCs, traders, or offline objects may not implement these methods.
- **Dialogue cleaner**: `clean_dialogue()` checks 4 refusal strings. Real-world LLM refusals use dozens of patterns we don't catch.
- **Callout dedup**: Anti-spam loop checks `event.description` — a field that no longer exists on typed events. The entire dedup block is dead code.

## Goals / Non-Goals

**Goals:**
- Eliminate crash paths in injury and task triggers
- Prevent anomaly-source hits from creating duplicate injury events (anomaly trigger already handles these)
- Catch LLM refusal text before it displays as NPC dialogue
- Restore callout anti-spam using typed event fields (`event.type`, `event.context.target.name`)

**Non-Goals:**
- Porting cross-cutting upstream features (weapon status, companion-only questions, junk reply flag, idle timer rewrite)
- Adding new MCM settings (configurable display time is a separate change)
- Changing the `max_tokens` cap on memory compression (separate concern)
- Modifying event templates or the Event model

## Decisions

### D1: Injury trigger — guard order and anomaly detection

**Decision**: Add three early-return guards at the top of `actor_on_hit_callback`, before any event creation:

1. `if not who then return end` — nil check (fall damage, environmental)
2. `if who == db.actor then return end` — self-damage (grenades)  
3. Anomaly check — if `who:section()` is a known anomaly section, return (anomaly trigger handles it)

**Anomaly detection approach**: Create a new `domain/data/anomaly_sections.lua` data table following the established `domain/data/` pattern (like `mutant_names.lua`, `unique_npcs.lua`). This table contains a Set of all ~75 known anomaly section names extracted from `talker_anomalies.xml`, plus an `is_anomaly(section)` predicate. Both `talker_trigger_injury.script` and `talker_trigger_anomalies.script` will migrate to use this table instead of the current `queries.load_xml()` approach — which is an antipattern (runtime XML lookup via the game engine for what is effectively a static set membership check).

The data table will also store the display-name mapping (section → description), so `talker_trigger_anomalies.script` can replace its `queries.load_xml(section)` call with a pure Lua lookup. Access from `gamedata/scripts/` goes through the engine facade.

**Also**: Guard `mcm.get("injury_threshold")` with `tonumber()` and a fallback default (0.4), since MCM can return a string.

**Alternative considered**: Simple prefix check (`section:find("^zone_")`) — all anomaly sections start with `zone_`. Rejected because it's fragile and doesn't follow the project's data-table convention.

**Alternative considered**: Wrapping the entire callback in pcall instead of individual guards. Rejected because it masks the root cause and produces unhelpful error messages.

### D2: Task trigger — safe entity property access + story_id

**Decision**: Use `server_entity:section_name()` as the stable `story_id` identifier. This is a base method on all `cse_alife_object` descendants and never crashes. The `story_id` (e.g. `"esc_m_trader"`) is the same identifier used by `important.py` on the Python side — Python can resolve it to `"Sidorovich"` via `get_character_by_id()` in the prompt builder.

For the `name` field, use `character_name()` with a type-checked fallback to `"Unknown"`:

```lua
local story_id = server_entity:section_name()
local name = (type(server_entity.character_name) == "function" and server_entity:character_name())
             or "Unknown"
```

Same safe-access pattern for `rank` (fallback to 0) and `community` (fallback to `"stalker"`). Also guard the `ranks.get_se_obj_rank_name()` call with a `type()` check.

**Also**: Fix `serialize_character()` in `infra/zmq/serializer.lua` to include `story_id` in the wire format — it's already on the `Character` entity but currently dropped during serialization. This enables Python to reliably identify story NPCs regardless of what `name` resolved to.

**Alternative considered**: Resolving story_id → display name entirely in Lua via `game.translate_string(section_name)`. Rejected because Python already has the authoritative `important.py` registry and is where the data gets consumed in prompt building — centralizing name resolution there is cleaner.

**Alternative considered**: Using `pcall` around the entire block. Rejected because a single pcall would abort the entire event on any one failure, whereas the fallback chain preserves as much information as possible.

### D3: Dialogue cleaner — expanded rejection list

**Decision**: Expand the `artifacts` list in `clean_dialogue()` from 4 entries to ~20+, drawn from the upstream source's battle-tested list. Group them logically:

- Apology patterns: "I apologize, but I", "I'm sorry, but I cannot"
- Inability patterns: "I cannot fulfill", "I cannot generate", "I cannot complete"
- Policy patterns: "safety guidelines", "content guidelines", "ethical guidelines", "usage policies", "use-case policy"
- Identity leak patterns: "AI assistant", "openAI", "not programmed", "against my programming"
- Content block patterns: "prohibited content", "inappropriate content", "Content is not allowed", "Unable to comply"
- Deflection patterns: "If you have any other inquiries"

The check remains case-insensitive substring matching (existing approach). No regex needed — simple string containment is fast and sufficient.

**Alternative considered**: Regex-based matching. Rejected — harder to maintain, no real benefit since we're matching fixed phrases not patterns.

### D4: Callout dedup — typed event field matching

**Decision**: Replace the description-string matching block with typed event field checks:

```lua
if event.type == EventType.CALLOUT then
    local target_name_in_event = event.context and event.context.target and event.context.target.name
    if target_name_in_event == target_name then
        -- same cooldown/pending logic as before
    end
end
```

This uses `event.type` (enum string) and `event.context.target.name` (Character field) — both guaranteed present on callout events created by the same script. The existing cooldown logic (dialogue_generated check, pending window) stays unchanged.

**Also**: Pass `target_name` in flags for cross-event reference: add `{ is_callout = true, target_name = enemy.name }` to the `trigger.talker_event()` call (currently only passes `{}`).

## Risks / Trade-offs

- **[Injury anomaly check completeness]** → The anomaly sections Set is derived from `talker_anomalies.xml` — any anomaly type not listed there won't be filtered. Mitigation: the same list is used by `talker_trigger_anomalies.script`, so if it doesn't handle an anomaly, neither script will fire for it (consistent behavior).
- **[Rejection list maintenance]** → New LLM models may produce novel refusal patterns not in the list. Mitigation: the list is easy to extend; we can add patterns as they're discovered in logs.
- **[No automated tests for Lua trigger fixes]** → `gamedata/scripts/` files can't be unit tested without the game engine. Mitigation: fixes are defensive guards (early returns), minimizing logic complexity. Python cleaner fix is fully testable.

# Proposal: Port Upstream Bugfixes

## Why

The TALKER-Expanded codebase was forked from TALKER-fork and migrated to a new architecture (typed events, Python service, clean architecture layers). Since that fork point, the upstream project (TALKER-Expanded-source) continued development and fixed several bugs. A systematic diff revealed 4 bugs that affect our codebase — ranging from game crashes to silent logic failures.

These bugs were identified by diffing TALKER-fork (our baseline) against TALKER-Expanded-source (latest upstream), then auditing each change against our current codebase to determine applicability.

## What Changes

Four independent bug fixes across Lua game scripts and the Python dialogue cleaner:

1. **Injury trigger crash + anomaly overlap** (`talker_trigger_injury.script`): The `actor_on_hit_callback` has no guard for `who` being nil (fall damage, environmental), no filter for anomaly-source damage (overlaps with `talker_trigger_anomalies.script`), and no self-damage handling (grenades). All three cause either crashes or nonsensical events.

2. **Task trigger crash on offline entities** (`talker_trigger_task.script`): Raw calls to `server_entity:character_name()`, `:rank()`, `:community()` with no pcall/fallback. Crashes when task givers are offline NPCs, traders, or modded entities that lack these methods.

3. **AI refusal text leaking as NPC dialogue** (`cleaner.py`): The Python dialogue cleaner only has 4 rejection-detection strings. Upstream's Lua equivalent had 25+. Many LLM refusal patterns ("I apologize, but I", "safety guidelines", "prohibited content", "AI assistant") pass through undetected and display as NPC speech.

4. **Callout anti-spam completely broken** (`talker_trigger_callout.script`): The dedup check matches `event.description` against format-string templates from the old event system. Since our migration to typed events, events no longer have a `.description` field — so the check never matches and anti-spam is silently disabled. Fix: match on `event.type == "CALLOUT"` and `event.context.target.name`.

## Capabilities

- **anomaly-data-table**: New `domain/data/anomaly_sections.lua` — static Set of known anomaly sections with display-name lookup, replacing runtime XML lookups
- **injury-trigger-guards**: Add nil/anomaly/self-damage guards to the injury trigger (uses anomaly data table)
- **task-trigger-safe-entity-access**: Add safe fallbacks for server entity method calls in task trigger, capture `story_id` via `section_name()`, and fix serializer to include `story_id` on the wire
- **dialogue-cleaner-rejections**: Expand rejection detection in Python dialogue cleaner
- **callout-dedup-typed-events**: Rewrite callout anti-spam to use typed event fields
- **anomaly-trigger-migration**: Migrate `talker_trigger_anomalies.script` from `queries.load_xml()` to the new anomaly data table

## Impact

- **Risk**: Low — all fixes are isolated with minimal cross-cutting. The new anomaly data table is shared by two trigger scripts but is a pure data module with no side effects.
- **Testing**: The new `anomaly_sections.lua` data table is fully unit-testable. Python cleaner fix is fully unit-testable. Trigger script fixes are in `gamedata/scripts/` (game adapter layer, not directly unit-testable).
- **Backward compatibility**: No API changes. No config changes. No wire protocol changes.

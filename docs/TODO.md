# TODO

## Investigate self-damage handling in injury trigger

Currently the `port-upstream-bugfixes` change adds a `who == db.actor` guard to `talker_trigger_injury.script` to suppress self-damage events (grenades). Before finalizing:

- **Check if self-damage reactions would be interesting** — NPCs reacting to the player blowing themselves up could be entertaining ("Watch where you throw those grenades, idiot!")
- **Identify all sources where `who == db.actor`** — is it only grenades, or are there other cases (environmental reflections, friendly fire mechanics, scripted self-damage)?
- **Check for false positives** — does `who == db.actor` ever fire in cases that aren't actually self-inflicted (e.g., engine quirks, reflected damage, certain anomaly interactions)?
- **Decision**: suppress unconditionally (current plan), allow with a flag, or remove the guard entirely and let the AI react to it

## Decide where to resolve important character names from story_id

With `story_id` now sent on the wire (via `section_name()`), we need to decide where display names for important characters get resolved:

- **Option A: Python-side via `important.py`** — `get_character_by_id(story_id)` already maps IDs like `"esc_m_trader"` → `"Sidorovich"`. Prompt builder could override `name` when `story_id` matches. Pro: centralized, already exists. Con: only covers ~40 characters.
- **Option B: Lua-side via engine query** — use `character_name()` consistently across all character construction paths (not just the task trigger). Could add a batch query that resolves names for all characters in a scene. Pro: covers all NPCs including generic ones. Con: requires engine to be available.
- **Option C: Hybrid** — Lua sends best-effort `name` from `character_name()`, Python overrides from `important.py` when `story_id` matches (adds role/description context too).
- **Check**: Is there a place in the batch state query builder where we already construct character info? Could we unify name resolution there instead of per-trigger?

## Check context.target dedup in CALLOUT trigger

The callout trigger currently puts `target_name` (a display string) in flags and the full `target` Character in context. In the new design, `target_name` in flags is eliminated — the target character lives in `context.target`. However, `context.target` currently carries the full Character object with `target.name` as a display name.

- **Should `context.target` use `game_id` instead of `name` for dedup?** — If two NPCs spot the same enemy, context matching (for e.g. memory dedup or event grouping) would need to compare targets. String names can collide; `game_id` is unique.
- **Candidate change**: ensure `context.target` always has `game_id` populated (it should already via `game.create_character`), and any downstream Python code that needs to identify the target uses `game_id`, not `name`.
- **Check serializer**: `serialize_context` already serializes `target` as a full Character (with `game_id`). Verify Python-side code doesn't rely on a bare `target_name` string anywhere.

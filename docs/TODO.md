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

## Investigate alternative TTS sound cache invalidation

Currently `snd_restart` is used every 100 slot allocations to flush the X-Ray engine's decoded PCM cache. This is a blunt instrument — it flushes **all** cached sounds and can cause a brief audio stutter.

- **Spike `getFS():rescan_path("$game_sounds$")`** — This unused engine FS API might allow targeted cache invalidation of just the `characters_voice\talker_tts\` subtree, without nuking the entire sound cache. Found in `lua_help.script` but never exercised by any shipping mod. Needs in-game testing to confirm: (a) it actually invalidates the PCM cache (not just the file index), and (b) it doesn't crash or stutter worse than `snd_restart`.
- **Test per-slot invalidation** — Can `rescan_path` be scoped to a single file, or only a directory? If directory-only, does rescanning 200 silent OGGs at once cause a hitch?
- **Measure `snd_restart` impact** — Profile the actual stutter duration. If it's <50ms, the whole investigation may not be worth the risk.

## Investigate `npc:add_sound()` / `npc:play_sound()` for TTS

The X-Ray engine exposes `game_object:add_sound(path, period, type, delay, ...)` and `game_object:play_sound(idx, ...)` which are used by `sound_theme.script` for vanilla NPC barks. This is a fundamentally different approach from `sound_object:play_at_pos()` — the engine itself manages the sound lifecycle and position tracking.

- **Potential advantages**: Engine-native position tracking (no Lua tick loop), proper occlusion/reverb integration, compatible with the NPC sound system (e.g. `active_sound_count()` checks).
- **Unknowns**: Can `add_sound` work with dynamically-overwritten OGG files (our slot system), or does it expect static paths indexed at startup? Does the sound type enum affect 3D spatialization? What happens if the NPC dies mid-playback?
- **Approach**: Spike a minimal test in a `talker_trigger_*.script` callback — call `npc:add_sound("characters_voice\\talker_tts\\slot_1", 0, snd_type.talk, 0, 0, 0)` and then `npc:play_sound(0)` to see if audio is audible, spatially positioned, and tracks movement.
- **Risk**: This is a much larger surface area change than `play_at_pos` + `set_position`. Only pursue if the tracking loop approach has issues in practice.

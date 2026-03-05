## 1. Build Inhabitants Context Function

- [x] 1.1 Add `build_inhabitants_context(alive_status, current_area, recent_events)` to `world_context.py` that returns a formatted "Notable Zone Inhabitants" text section
- [x] 1.2 Include all leaders unconditionally; filter important/notable by area match or recent event presence (reuse `_is_notable_relevant` logic)
- [x] 1.3 Format each entry as `- {name}, {description} ({alive|dead})` with faction-name fallback when description is missing
- [x] 1.4 Return empty string when the filtered list is empty

## 2. Integrate into build_world_context Pipeline

- [x] 2.1 Replace `build_dead_leaders_context()` and `build_dead_important_context()` calls in `build_world_context()` with a single `build_inhabitants_context()` call
- [x] 2.2 Keep `build_dead_leaders_context` and `build_dead_important_context` functions intact for backward compatibility — just stop calling them from the aggregate

## 3. System Prompt Injection

- [x] 3.1 Verify `build_world_context` output (which now includes inhabitants) flows into `_build_system_prompt` via the `world` parameter — no additional wiring needed if the section is part of the aggregated world context string

## 4. Tests

- [x] 4.1 Add unit tests for `build_inhabitants_context`: mixed alive/dead, area filtering, event-mention inclusion, no-description fallback, empty result
- [x] 4.2 Update existing `build_world_context` tests to expect inhabitants section instead of separate dead leaders/dead important sections
- [x] 4.3 Run full Python test suite and fix any regressions

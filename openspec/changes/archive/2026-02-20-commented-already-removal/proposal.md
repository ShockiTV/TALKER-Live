## Why

`commented_already` in `talker_trigger_map_transition.script` is dead code — never read by any logic. Additionally, a save bug on line 98 (`m_data.level_visit_count = commented_already`) overwrites the just-assigned `level_visit_count` with a boolean, meaning `level_visit_count` is also never persisted correctly. Despite this bug existing since the feature was written, map transitions have worked fine — proving the dedup guard was never needed (`has_map_changed()` already prevents duplicates).

## What Changes

1. Remove the `commented_already` variable entirely (declaration, save, load)
2. Fix the save bug so `level_visit_count` is correctly persisted across saves
3. Clean up the save/load functions to only persist what's needed: `level_visit_count` and `previous_map`

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- `gamedata/scripts/talker_trigger_map_transition.script` — remove dead code, fix save bug
- No behavioral change (the removed code was never active)
- `level_visit_count` will now correctly persist, so "for the first time" / "again" flavor text in map transition prompts will be accurate across saves

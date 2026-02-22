## 1. Lua: Fix task_giver faction (trigger)

- [x] 1.1 Remove the `faction_map` table declaration from `talker_trigger_task.script`
- [x] 1.2 Remove the `faction_map[...]` conversion line that overwrites `task_giver_character.faction`
- [x] 1.3 Verify `server_entity:community()` already returns a technical ID (e.g. `"dolg"`) — no replacement needed

## 2. Lua: Add task_giver to serializer character_keys

- [x] 2.1 Add `"task_giver"` to the `character_keys` list in `serialize_context()` in `bin/lua/infra/zmq/serializer.lua`
- [x] 2.2 Add a Lua test in `tests/infra/zmq/test_serializer.lua` verifying `task_giver` is serialized as a character (faction preserved as-is, nil fields absent)

## 3. Python: Render task_giver in TASK event description

- [x] 3.1 In `prompts/helpers.py`, extend the `"TASK"` branch of `describe_event()` to extract `task_giver` from context using `_get_character()`
- [x] 3.2 Append `" for {describe_character(task_giver)}"` to the description when `task_giver` is present
- [x] 3.3 Add `test_describe_task_event_with_giver` test in `tests/test_prompts.py` (task_giver with faction `"dolg"` should show "Duty" in output)
- [x] 3.4 Add `test_describe_task_event_without_giver` test to confirm graceful fallback

## 4. Python: Disguise awareness instructions in dialogue prompt

- [x] 4.1 In `prompts/builder.py`, after the events loop in `create_dialogue_request_prompt()`, accumulate event text strings and check for `[disguised as`
- [x] 4.2 If `has_disguise` is True and `is_companion` is True, append a `## DISGUISE CONTEXT` message with companion-aware instructions
- [x] 4.3 If `has_disguise` is True and `is_companion` is False, append a `## DISGUISE CONTEXT` message with non-companion instructions
- [x] 4.4 Add `test_dialogue_prompt_disguise_non_companion` test in `tests/test_prompts.py`: events with disguised character, non-companion — verify `## DISGUISE CONTEXT` present with non-companion text
- [x] 4.5 Add `test_dialogue_prompt_disguise_companion` test: same but `is_companion=True` — verify companion-aware wording
- [x] 4.6 Add `test_dialogue_prompt_no_disguise_no_section` test: events without disguise — verify no `## DISGUISE CONTEXT` section

## 5. E2E Test: TASK event with task_giver

- [x] 5.1 Create `talker_service/tests/e2e/scenarios/task_with_giver.json` — a TASK event with:
  - `context.actor` (the player)
  - `context.task_name` (a translated task title string)
  - `context.task_giver` with `faction: "dolg"` (technical ID)
  - At least one witness with `personality` set so speaker selection runs
- [x] 5.2 Verify the scenario asserts that the rendered event description contains the task giver's name and "Duty" (the resolved faction display name)
- [x] 5.3 Create `talker_service/tests/e2e/scenarios/task_with_disguised_actor.json` — a TASK event where `context.actor` has `visual_faction` set, to verify the `## DISGUISE CONTEXT` section appears in the captured prompt payload
- [x] 5.4 Run new e2e scenarios: `run_tests { path: "tests/e2e/", pattern: "task" }`

## 6. Verification

- [x] 6.1 Run Lua serializer tests: `lua5.1.exe tests/infra/zmq/test_serializer.lua`
- [x] 6.2 Run Python prompt tests: `run_tests { pattern: "test_prompts" }`
- [x] 6.3 Run full Python test suite to confirm no regressions: `run_tests {}`

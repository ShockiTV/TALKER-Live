## Why

The TASK trigger sends `task_giver` character data with a pre-converted display faction name (e.g. `"Duty"` instead of `"dolg"`), inconsistent with every other character in the system and bypassing Python's resolution layer. Additionally, `task_giver` is absent from the serializer's recognized character keys, so it is not normalized on the wire. The field is also silently ignored in Python prompt building, making the task giver invisible to the LLM. Separately, when the player is disguised, the `[disguised as X]` tag appears in event text but the Python prompt builder provides no contextual instructions to the LLM on how to interpret it — unlike the fork, which injects explicit DISGUISE AWARENESS and DISGUISE NOTATION guidance.

## What Changes

- **Remove `faction_map` conversion** from `talker_trigger_task.script` — send raw technical faction ID (e.g. `"dolg"`) so Python resolves it consistently via `resolve_faction_name()`
- **Add `"task_giver"` to `character_keys`** in `bin/lua/infra/zmq/serializer.lua` so `serialize_context()` normalizes it as a Character object on the wire
- **Wire `task_giver` into the Python TASK event description** in `prompts/helpers.py` so the LLM sees who gave the task and their faction
- **Add disguise awareness prompt injection** in the Python prompt builder: when any recent event contains `[disguised as`, inject DISGUISE AWARENESS and DISGUISE NOTATION instructions into the dialogue prompt

## Capabilities

### New Capabilities
- `task-giver-in-prompt`: `task_giver` character is correctly serialized and rendered in Python TASK event descriptions

### Modified Capabilities
- `python-prompt-builder`: Dialogue prompt now includes conditional disguise awareness instructions when disguise events are present

## Impact

- `gamedata/scripts/talker_trigger_task.script` — remove `faction_map` conversion block
- `bin/lua/infra/zmq/serializer.lua` — add `"task_giver"` to `character_keys`
- `talker_service/src/talker_service/prompts/helpers.py` — extend TASK branch to include task_giver; add disguise detection + instruction injection
- `talker_service/src/talker_service/prompts/builder.py` or `dialogue.py` — location of disguise instruction injection (where recent events are assembled)
- `talker_service/tests/test_prompts.py` — new test cases for task_giver rendering and disguise instructions
- `tests/infra/zmq/test_serializer.lua` — new test case for task_giver serialization

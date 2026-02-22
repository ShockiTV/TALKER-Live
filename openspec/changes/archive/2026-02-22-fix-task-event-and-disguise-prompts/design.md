## Context

The TASK event trigger in `talker_trigger_task.script` manually constructs a `task_giver_character` table using a `faction_map` lookup to convert technical faction IDs to display names before sending the event over ZMQ. This is the opposite of the convention used everywhere else: all other characters send technical faction IDs (e.g. `"dolg"`, `"killer"`) and Python resolves them to display names via `resolve_faction_name()`.

Additionally, `task_giver` is not recognized as a character key in `infra/zmq/serializer.lua`, so `serialize_context()` does not run it through `serialize_character()` normalization. And in Python, the TASK branch of `describe_event()` in `prompts/helpers.py` only uses `task_status` and `task_name` — `task_giver` is silently ignored.

Separately, when the player wears a disguise, `describe_character()` appends `[disguised as X]` to the character string, which then appears in event text. But the dialogue prompt provides no instructions to the LLM on what this means — whether the speaker knew, how to phrase it, etc. The fork handles this by scanning event text for `[disguised as` and conditionally injecting DISGUISE AWARENESS and DISGUISE NOTATION instructions.

## Goals

1. Fix `task_giver` faction to use technical ID (no Lua-side translation)
2. Ensure `task_giver` is properly serialized as a Character on the wire
3. Render `task_giver` in the Python TASK event description string
4. Inject disguise awareness instructions into the dialogue prompt when disguise events are detected

## Approach

### Fix 1: Remove faction_map conversion (Lua)

In `gamedata/scripts/talker_trigger_task.script`, delete the line that applies `faction_map`:

```lua
-- REMOVE THIS:
task_giver_character.faction = faction_map[task_giver_character.faction] or task_giver_character.faction
```

The `faction_map` table can also be removed — it's no longer needed. `server_entity:community()` already returns the technical ID.

### Fix 2: Add task_giver to serializer character_keys (Lua)

In `bin/lua/infra/zmq/serializer.lua`, add `"task_giver"` to the `character_keys` list in `serialize_context()`:

```lua
local character_keys = { "victim", "killer", "actor", "spotter", "target", "taunter", "speaker", "task_giver" }
```

This ensures `task_giver` is passed through `serialize_character()` before going over the wire, normalizing `game_id` to string and including all character fields.

**Note**: `task_giver` in the trigger is built as a plain table (not a `Character.new()` object), so it won't have `backstory`, `personality`, or `story_id`. `serialize_character()` handles nil fields gracefully — the nil fields simply become absent from the serialized result.

### Fix 3: Render task_giver in Python TASK description (Python)

In `talker_service/src/talker_service/prompts/helpers.py`, extend the `"TASK"` branch of `describe_event()`:

```python
elif event_type == "TASK":
    task_status = ctx.get("task_status", "updated")
    task_name = ctx.get("task_name", "a task")
    task_giver = _get_character(ctx, "task_giver")

    giver_part = f" for {describe_character(task_giver)}" if task_giver else ""

    if actor:
        return f"{describe_character(actor)} {task_status} task: {task_name}{giver_part}"
    return f"Task {task_status}: {task_name}{giver_part}"
```

The `_get_character()` helper already exists in helpers.py for extracting Character objects from context dicts.

### Fix 4: Disguise awareness instructions (Python)

In `talker_service/src/talker_service/prompts/builder.py`, in `create_dialogue_request_prompt()`, add a check after the events are assembled (after the `</EVENTS>` section is appended). Scan the rendered event strings for `[disguised as`:

```python
# Check if any events mention a disguise
event_texts = [describe_prompt_item(item) for item in new_events]
has_disguise = any("[disguised as" in t for t in event_texts)

if has_disguise:
    # Different instruction flavour for companions vs strangers
    if is_companion:
        disguise_note = (
            "### DISGUISE AWARENESS (COMPANION):\n"
            " - If an event mentions someone '[disguised as X]', you (as their companion) were aware of the disguise at the time.\n"
            "   You may refer to it explicitly (e.g., 'you were disguised as Duty when we spoke to the guards').\n"
            "### DISGUISE NOTATION:\n"
            " - If an event mentions someone '[disguised as X]', preserve this information but phrase it from your perspective as someone who knew it was a disguise."
        )
    else:
        disguise_note = (
            "### DISGUISE NOTATION:\n"
            " - If an event mentions someone '[disguised as X]', you did NOT know it was a disguise at the time.\n"
            "   Treat the person by their apparent (disguised) faction, not their true faction."
        )
    messages.append(Message.system(f"## DISGUISE CONTEXT\n\n{disguise_note}"))
```

The injection point is **after `</EVENTS>` and before the context guidelines** so it appears after the LLM has read all event context.

**Implementation note**: The event texts are already being built element-by-element in the loop above. To avoid computing them twice, the loop can accumulate the rendered strings and the `has_disguise` check can run after the loop.

## Tradeoffs

- **Scanning event strings for `[disguised as`** is a simple approach that avoids adding a `has_disguise` flag to the Event model. The fork does the same thing. Downside: fragile against text changes to `describe_character()`. Alternative: check `event.context` for any character with `visual_faction != None`. The string scan approach is preferred for simplicity.
- **task_giver as plain table**: Since `task_giver` is not constructed with `Character.new()`, it won't have personality/backstory. This is acceptable — the task giver description is purely informational (who gave the task, their faction). If personality is needed later, `Character.new()` can be used in the trigger.

## Files Changed

| File | Change |
|------|--------|
| `gamedata/scripts/talker_trigger_task.script` | Remove `faction_map` table and conversion line |
| `bin/lua/infra/zmq/serializer.lua` | Add `"task_giver"` to `character_keys` |
| `talker_service/src/talker_service/prompts/helpers.py` | Extend TASK branch with `task_giver` rendering |
| `talker_service/src/talker_service/prompts/builder.py` | Add disguise awareness injection after events section |
| `talker_service/tests/test_prompts.py` | Tests for task_giver describe and disguise injection |
| `tests/infra/zmq/test_serializer.lua` | Test for task_giver serialization |

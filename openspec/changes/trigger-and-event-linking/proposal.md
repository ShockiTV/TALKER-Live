## Why

The `pointer-based-dialogue-messages` spec (from the deduplicated-prompt-architecture change) specifies that picker and dialogue user messages should reference events by `ts` timestamp instead of inlining full descriptions. The current implementation diverges: the triggering event is inlined as a multi-line text block with no identifier, witness events use a different one-liner format, and neither carries `ts`. The LLM has no way to cross-reference the triggering event with the event list. Additionally, witness events are only fetched for the chosen speaker after the picker step — the picker sees zero event history.

## What Changes

- **Serialize `ts` in `serialize_event()`** — include the unique timestamp in the wire-format event payload so Python receives it on the `game.event` topic
- **Fetch witness events for ALL candidates before the picker step** — single batch query with one `query.memory.events` per candidate, moved from after picker to before
- **Deduplicate events across candidates by `ts`** — build a unified event list from all candidates' memories, dedup by `ts`, annotate each with which candidates witnessed it
- **Unified event list format with `ts` identifiers** — all events (including the triggering event) rendered in a single consistent format with `[ts]` prefix and witness names
- **Picker references event by `ts`** — picker instruction becomes `"React to event [{ts}]. Pick from candidates: ..."` with the full event list injected as ephemeral context
- **Dialogue references event by `ts`** — dialogue instruction references `EVT:{ts}`, with the chosen speaker's witness events injected ephemerally (removed after LLM call, only the assistant response persists)
- **Remove inline `build_event_description()` from dialogue step** — the triggering event is already in the witness event list (Lua fans out to all witnesses before publishing)

## Capabilities

### New Capabilities
- `event-list-assembly`: Fetching, deduplicating, and formatting a unified per-candidate event list with `ts` identifiers and witness annotations

### Modified Capabilities
- `pointer-based-dialogue-messages`: Picker and dialogue user messages now actually use `EVT:{ts}` pointers as originally specc'd (currently broken — inlines full descriptions)
- `witness-event-injection`: Event serialization now includes `ts`; witness events fetched for all candidates before picker (not just chosen speaker after picker)
- `lua-event-publisher`: `serialize_event()` includes `ts` field in wire payload

## Impact

- **Lua**: `bin/lua/infra/ws/serializer.lua` — one field added to `serialize_event()`
- **Python**: `talker_service/src/talker_service/dialogue/conversation.py` — event fetch moved earlier, new dedup/format logic, picker and dialogue prompt assembly rewritten
- **Python**: `talker_service/src/talker_service/prompts/picker.py` — `build_event_description()` replaced with `ts`-pointer format
- **Python**: `talker_service/src/talker_service/prompts/dialogue.py` — `build_dialogue_user_message()` updated for `ts`-pointer format
- **Python tests**: `test_conversation.py`, `test_witness_injection.py`, picker tests — updated for new format/flow
- **Token impact**: Neutral to slightly lower — event list is shared between steps instead of duplicated in different formats; ephemeral injection keeps the uncacheable tail minimal

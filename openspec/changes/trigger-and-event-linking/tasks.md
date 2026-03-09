## 1. Lua Wire Serialization

- [ ] 1.1 Add `ts = event.ts` to `serialize_event()` in `bin/lua/infra/ws/serializer.lua`
- [ ] 1.2 Add test for `ts` field in serialized event output (`tests/infra/ws/test_serializer.lua`)

## 2. Event List Assembly (New Module)

- [ ] 2.1 Create `talker_service/src/talker_service/dialogue/events.py` with `assemble_event_list()` — dedup events by `ts`, build witness map
- [ ] 2.2 Add `format_event_line(ts, event, witness_names)` — single-line `[ts] TYPE — description (witnesses: ...)` format
- [ ] 2.3 Add `build_event_list_text(unique_events, witness_map)` — multi-line sorted output
- [ ] 2.4 Add `filter_events_for_speaker(unique_events, witness_map, speaker_id)` — filter to speaker's witnessed events
- [ ] 2.5 Add unit tests for all assembly/formatting functions (`talker_service/tests/test_event_assembly.py`)

## 3. Pre-Picker Event Fetch

- [ ] 3.1 In `conversation.py` `handle_event()`, add batch state query for `query.memory.events` for all candidates BEFORE picker step
- [ ] 3.2 Parse batch result into `events_by_candidate: dict[str, list[dict]]` mapping
- [ ] 3.3 Call `assemble_event_list()` with the mapping to produce `unique_events` + `witness_map`
- [ ] 3.4 Remove the post-picker event fetch (currently in `_run_dialogue_generation` or after picker)

## 4. Picker Prompt Update

- [ ] 4.1 Update `_run_speaker_picker()` to accept unified event list text and triggering event `ts`
- [ ] 4.2 Build picker user message with `**Recent events in area:**` section + `React to event [{ts}].` pointer
- [ ] 4.3 Remove or replace `build_event_description()` usage in picker path
- [ ] 4.4 Update picker prompt tests

## 5. Dialogue Prompt Update

- [ ] 5.1 Update `_run_dialogue_generation()` to accept speaker-filtered event list text and triggering event `ts`
- [ ] 5.2 Build dialogue user message with `**Recent events witnessed by {name}:**` section + `React to event [{ts}]` pointer
- [ ] 5.3 Make dialogue user message ephemeral — inject before LLM call, pop after, keep only assistant response
- [ ] 5.4 Remove inline `build_event_description()` from dialogue path
- [ ] 5.5 Update dialogue prompt tests

## 6. Integration & E2E Tests

- [ ] 6.1 Update `test_conversation.py` for new event fetch flow and prompt format
- [ ] 6.2 Verify E2E scenarios pass with updated wire format (ts present in game.event payloads)
- [ ] 6.3 Run full Lua test suite to confirm serializer change doesn't break existing tests

## 1. ContextBlock Foundation

- [x] 1.1 Create `dialogue/context_block.py` with `ContextItem`, `BackgroundItem`, `MemoryItem` dataclasses
- [x] 1.2 Implement `ContextBlock` class: `_items`, `_bg_ids`, `_mem_keys`, `add_background()`, `add_memory()`
- [x] 1.3 Implement `has_background()`, `has_memory()`, `missing()` query methods
- [x] 1.4 Implement `render_markdown()` with insertion-order iteration and BG/MEM format
- [x] 1.5 Write unit tests for ContextBlock: add, dedup, missing, render_markdown, empty block

## 2. Static System Prompt

- [x] 2.1 Extract static dialogue rules from `_build_system_prompt()` into a constant or factory with zero dynamic content
- [x] 2.2 Remove weather, time, location, inhabitants from system prompt builder
- [x] 2.3 Write test asserting system prompt has no dynamic content (no weather/time/location keywords)

## 3. World Context Split

- [x] 3.1 Refactor `build_world_context()` to return structured result separating static items (inhabitants, factions, info portions) from dynamic items (weather, time, location)
- [x] 3.2 Create helper to add inhabitants as background entries in ContextBlock
- [x] 3.3 Create helper to add faction standings / info portions as static context block entries
- [x] 3.4 Update tests for world_context split return type

## 4. Four-Layer Message Layout

- [x] 4.1 Refactor `ConversationManager.__init__()` to initialise 3-message base: static system, empty context user, assistant "Ready."
- [x] 4.2 Add `ContextBlock` as instance field on ConversationManager, replacing DeduplicationTracker
- [x] 4.3 Implement context block update before each event: add candidate BGs + MEMs, update `_messages[1]`
- [x] 4.4 Implement compaction handler: rebuild ContextBlock from scratch, replace `_messages[1]`
- [x] 4.5 Write test asserting `_messages[0:3]` structure matches the 4-layer spec (system, user context, assistant ack)

## 5. Event Filtering

- [x] 5.1 Create `filter_events_for_speaker(events, speaker_id)` helper function
- [x] 5.2 Modify picker step to include only triggering event description (no witness events)
- [x] 5.3 Modify dialogue step to include only events where speaker is a witness
- [x] 5.4 Add weather/time/location to picker and dialogue per-turn user messages
- [x] 5.5 Write tests for event filtering: picker gets zero witness events, dialogue gets speaker-only events

## 6. Picker Ephemeral Messages

- [x] 6.1 Ensure picker instruction + response are removed from `_messages` after picker step completes
- [x] 6.2 Ensure dialogue instruction is appended at the correct index after picker cleanup
- [x] 6.3 Write test asserting picker messages are not present after dialogue step

## 7. Remove DeduplicationTracker

- [x] 7.1 Remove all imports and usages of `DeduplicationTracker` from ConversationManager
- [x] 7.2 Delete `dialogue/dedup_tracker.py`
- [x] 7.3 Update or remove tests that directly test DeduplicationTracker

## 8. Integration Tests

- [x] 8.1 Write integration test: multi-event sequence verifies `_messages[0]` is byte-identical across events
- [x] 8.2 Write integration test: context block grows append-only across events (prefix stability)
- [x] 8.3 Update existing e2e test scenarios to work with new message layout

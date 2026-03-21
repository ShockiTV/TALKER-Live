## 1. Remove Tool Infrastructure

- [x] 1.1 Remove tool schema definitions (`GET_MEMORIES_TOOL`, `BACKGROUND_TOOL`, `GET_CHARACTER_INFO_TOOL`, `TOOLS` list) from `conversation.py`
- [x] 1.2 Remove `_tool_handlers` registry and `_execute_tool_call()` method from `ConversationManager`
- [x] 1.3 Remove `complete_with_tool_loop()` call site in `handle_event()` — replace with placeholder for the 2-step flow
- [x] 1.4 Remove tool-usage instructions from `_build_system_prompt()`

## 2. Background Generation Thread

- [x] 2.1 Create `dialogue/background_generator.py` with `BackgroundGenerator` class — accepts `LLMClient` and `StateQueryClient`
- [x] 2.2 Implement `ensure_backgrounds(candidates)` — batch-reads `memory.background` for all candidates, returns early if all present
- [x] 2.3 Implement `_fetch_character_info(missing_ids)` — batch query for gender, squad, metadata of characters needing generation
- [x] 2.4 Build JSON input payload: all candidates (existing backgrounds as reference, nulls marked for generation), squad membership
- [x] 2.5 Build system prompt for background generation (GM-style, STALKER context, JSON output instruction)
- [x] 2.6 Implement one-shot LLM call (main model, `complete()`) and JSON response parser with error fallback
- [x] 2.7 Persist generated backgrounds via `state.mutate.batch` with `set` on `memory.background`
- [x] 2.8 Write unit tests for `BackgroundGenerator` — all-present skip, partial generation, malformed JSON fallback, mutation failure non-fatal

## 3. Memory Diff Injection

- [x] 3.1 Add `_memory_timestamps: dict[str, int]` to `ConversationManager.__init__()` — empty on session start
- [x] 3.2 Implement `_fetch_full_memory(character_id)` — retrieves all memory tiers + background, returns formatted text and latest timestamp
- [x] 3.3 Implement `_fetch_diff_memory(character_id, since_ts)` — retrieves only events newer than `since_ts`, returns formatted text and latest timestamp
- [x] 3.4 Implement `_inject_speaker_memory(speaker)` — dispatches to full or diff based on tracking dict, updates timestamp after injection
- [x] 3.5 Write unit tests for diff tracking — first-time full injection, returning speaker diff injection, no-new-memories case, timestamp update

## 4. Speaker Picker (Ephemeral)

- [x] 4.1 Implement `_run_speaker_picker(candidates, event_description)` — injects 3 user messages (candidate JSON, event, pick instruction) into conversation
- [x] 4.2 Call `llm_client.complete()` (no tools, fast model) and parse response as character ID
- [x] 4.3 Validate parsed ID against candidate list — fallback to first candidate on mismatch with warning log
- [x] 4.4 Remove all 4 ephemeral messages (3 user + 1 assistant) from conversation history after parsing
- [x] 4.5 Add single-candidate bypass — skip picker when only 1 NPC candidate
- [x] 4.6 Create `prompts/picker.py` with prompt builder for candidate JSON format and pick instruction
- [x] 4.7 Write unit tests for speaker picker — valid pick, invalid pick fallback, single-candidate skip, ephemeral message cleanup

## 5. Dialogue Generation (Persistent)

- [x] 5.1 Implement `_run_dialogue_generation(speaker, event_description)` — calls `_inject_speaker_memory()`, builds combined user message (background + memory + event + persona instruction)
- [x] 5.2 Call `llm_client.complete()` (no tools, main model) — keep both user message and assistant response in history
- [x] 5.3 Extract dialogue text from response (strip whitespace, no `[SPEAKER:]` parsing needed)
- [x] 5.4 Update `prompts/dialogue.py` — new prompt builder for per-turn user message (memory context + event + react-as instruction)
- [x] 5.5 Write unit tests for dialogue generation — message persistence across events, memory+event combined format

## 6. Refactor handle_event() and System Prompt

- [x] 6.1 Rewrite `handle_event()` — orchestrate: background check → picker → dialogue → return `(speaker_id, dialogue_text)`
- [x] 6.2 Refactor `_build_system_prompt()` — remove per-character persona/faction, keep world context + notable inhabitants + dialogue guidelines
- [x] 6.3 Preserve `_inject_witness_events()` and `CompactionScheduler.schedule()` calls post-dialogue
- [x] 6.4 Wire `BackgroundGenerator` into `ConversationManager` (injected via constructor or created internally)

## 7. Integration and E2E Tests

- [x] 7.1 Update existing tool-based conversation tests to match 2-step flow (remove tool-loop mocking, add picker+dialogue mocking)
- [x] 7.2 Update E2E test scenarios — wire payloads should show 2 `complete()` calls per event (picker + dialogue), no tool calls
- [x] 7.3 Test accumulated conversation history — verify second event sees first event's dialogue in context
- [x] 7.4 Test background generation integration — event with null-background candidates triggers generation before picker

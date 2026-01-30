## 1. Lua Memory Store

- [x] 1.1 Restructure memory_store.lua from array-based to narrative-based storage
- [x] 1.2 Add COMPRESSION_THRESHOLD constant (12 events)
- [x] 1.3 Implement get_memory_context() returning narrative, last_update_time_ms, new_events
- [x] 1.4 Implement update_narrative() for setting character narrative
- [x] 1.5 Implement update_last_update_time() for timestamp-only updates
- [x] 1.6 Implement get_new_events() to retrieve events since last compression
- [x] 1.7 Add legacy format migration in load_save_data()

## 2. Python Compression Orchestration

- [x] 2.1 Add COMPRESSION_THRESHOLD constant to dialogue/generator.py
- [x] 2.2 Implement _maybe_compress_memory() with threshold check
- [x] 2.3 Implement _compress_memory() with prompt selection logic
- [x] 2.4 Add per-character asyncio.Lock for concurrency control
- [x] 2.5 Spawn compression as background task in _generate_dialogue_for_speaker()
- [x] 2.6 Publish memory.update command after successful compression

## 3. Compression Prompts

- [x] 3.1 Create create_compress_memories_prompt() for bootstrap compression
- [x] 3.2 Create create_update_narrative_prompt() for incremental updates
- [x] 3.3 Add junk event filtering (is_junk_event check)
- [x] 3.4 Add chronological sorting before prompt building
- [x] 3.5 Enforce 900 char limit in compress prompt, 6400 char limit in update prompt

## 4. Time Gap Injection

- [x] 4.1 Add DEFAULT_TIME_GAP_HOURS constant (12) and MS_PER_HOUR
- [x] 4.2 Implement inject_time_gaps() function in helpers.py
- [x] 4.3 Implement _create_gap_event() helper for GAP event creation
- [x] 4.4 Add GAP event handling in _format_typed_event()
- [x] 4.5 Integrate inject_time_gaps() into create_dialogue_request_prompt()
- [x] 4.6 Integrate inject_time_gaps() into create_compress_memories_prompt()
- [x] 4.7 Integrate inject_time_gaps() into create_update_narrative_prompt()
- [x] 4.8 Export inject_time_gaps from prompts __init__.py

## 5. ZMQ Integration

- [x] 5.1 Add memory.update command handler in talker_zmq_command_handlers.script
- [x] 5.2 Implement state query handler for memories in Lua
- [x] 5.3 Add query_memories() to Python StateQueryClient

## 6. Testing

- [x] 6.1 Add unit tests for inject_time_gaps() (10 tests)
- [x] 6.2 Verify all 142 Python tests pass
- [x] 6.3 Test legacy save migration paths

## 7. Documentation

- [x] 7.1 Create docs/Memory_Compression.md with full system documentation

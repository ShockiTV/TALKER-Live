## Why

NPCs need persistent, scalable long-term memory to maintain narrative continuity across gameplay sessions. Without compression, the memory context would overflow LLM token limits as events accumulate, causing either memory loss or degraded dialogue quality.

## What Changes

- Three-tier memory architecture: recent events → mid-term summary → long-term narrative
- Automatic compression triggered when unprocessed events exceed threshold (12 events)
- Time gap injection to help LLMs understand temporal transitions between events
- ZMQ command (`memory.update`) for Python service to update Lua memory store
- State query for Python to request memory context from Lua
- Legacy save format migration to new narrative-based structure

## Capabilities

### New Capabilities

- `memory-compression`: Core compression system with three-tier architecture, threshold-based triggers, and LLM-powered summarization
- `time-gap-injection`: Automatic detection and injection of GAP events when time between events exceeds configurable threshold

### Modified Capabilities

- `python-zmq-router`: Added `memory.update` command handler and state query support for memories
- `python-prompt-builder`: Added `create_compress_memories_prompt()` and `create_update_narrative_prompt()` functions
- `lua-zmq-subscriber`: Added `memory.update` command handler in `talker_zmq_command_handlers.script`

## Impact

- **Lua**: `memory_store.lua` restructured from array-based to narrative-based storage
- **Python**: `DialogueGenerator` orchestrates compression with per-character locks
- **Prompts**: Two new prompt templates for bootstrap and incremental compression
- **Persistence**: Save format changed; migration logic handles legacy saves
- **Configuration**: `COMPRESSION_THRESHOLD` (12) and `time_gap` (12 hours) settings

## Why

The current tool-based dialogue system requires LLM tool-calling support, adds 2-6 unpredictable round-trips per event, and couples speaker selection with dialogue generation in a single turn. Models frequently misuse tools (fetching backgrounds before selecting a speaker, re-fetching already-present memories, or forgetting to call tools entirely). Splitting into two deterministic steps — speaker selection then dialogue generation — makes the flow predictable, removes the tool-calling requirement, and lets Python control exactly what context the LLM sees at each stage.

Additionally, generic NPCs currently lack backgrounds entirely, making them invisible to sound speaker selection. A separate background generation step ensures every candidate has a background before the picker runs.

## What Changes

- **Replace tool-calling loop with 2-step deterministic flow**: Step 1 picks the speaker (backgrounds + event → speaker ID), Step 2 generates dialogue (full memory for chosen speaker + event → dialogue text). Both steps run in the same persistent conversation but step 1 messages are ephemeral — injected then removed after the speaker is chosen.
- **Add background generation thread**: Before speaker selection, batch-read all candidate backgrounds. If any are null, run a separate LLM call (own conversation, main model) to generate backgrounds for all missing characters — informed by existing squad backgrounds, squad membership, and character info. Persist generated backgrounds, then proceed.
- **Remove LLM tool definitions and tool loop**: No more `get_memories`, `background`, or `get_character_info` tools exposed to the LLM. Python fetches all needed data deterministically and injects it as message content.
- **Add memory diff tracking**: Per-session tracking of what memory state each character has had injected into the conversation. Repeated speakers get only new events since the last injection, not full re-dumps.
- **Conversation history is persistent across events**: The main conversation accumulates `[event context + memory, dialogue]` pairs across events within a session. Speaker selection scaffolding is never persisted.

## Capabilities

### New Capabilities
- `two-step-dialogue-flow`: The 2-step deterministic dialogue pipeline — speaker picker (ephemeral) then dialogue generation (persistent) — replacing the tool-calling loop
- `background-generation-thread`: Separate LLM conversation for generating missing character backgrounds before speaker selection, triggered by Python when null backgrounds are detected
- `memory-diff-injection`: Per-session tracking of injected memory timestamps, enabling diff-only memory injection for returning speakers

### Modified Capabilities
- `tool-based-dialogue`: **BREAKING** — tool-calling loop removed, ConversationManager refactored from tool-based to 2-step deterministic flow. Tools no longer exposed to LLM.

## Impact

- **`talker_service/src/talker_service/dialogue/conversation.py`**: Major rewrite — remove tool definitions, tool handlers, tool loop. Replace with 2-step flow (picker + dialogue). Add ephemeral message injection/removal. Add memory diff tracking.
- **`talker_service/src/talker_service/llm/`**: `complete_with_tool_loop()` no longer required for dialogue generation. Plain `complete()` sufficient for both steps.
- **`talker_service/src/talker_service/handlers/events.py`**: Minor — background generation step inserted before calling ConversationManager.
- **`talker_service/src/talker_service/prompts/`**: New prompt builders for speaker picker and background generator. Existing dialogue prompt logic largely replaced.
- **LLM provider compatibility**: Broader — any model that can follow instructions works, tool-calling support no longer required.
- **Test suite**: Significant test updates — tool-based tests replaced with deterministic 2-step tests. E2E scenarios change shape.

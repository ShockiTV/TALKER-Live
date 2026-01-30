## Why

Phase 1 established ZeroMQ communication from Lua → Python (event publishing, config sync). However, AI dialogue generation still runs entirely in Lua, which limits access to Python's superior ML ecosystem, makes debugging difficult, and prevents hot-reloading prompts without game restarts. Phase 2 moves the core AI logic (LLM calls, prompt building, speaker selection) to Python while Lua retains state persistence and game integration.

## What Changes

- Add Python → Lua communication channel (second ZMQ PUB/SUB pair in reverse direction)
- Move LLM API calls from Lua to Python (`infra/AI/GPT.lua`, `OpenRouterAI.lua`, `local_ollama.lua`, `proxy.lua`)
- Move prompt building from Lua to Python (`infra/AI/prompt_builder.lua`)
- Move speaker selection logic from Lua to Python (`infra/AI/requests.lua:pick_speaker`)
- Move memory compression logic from Lua to Python (`infra/AI/requests.lua:update_narrative`)
- Add Python request handlers that query Lua for state (memories, events, characters)
- Add Lua command handlers that receive dialogue display commands from Python
- **BREAKING**: Remove Lua AI modules (`infra/AI/GPT.lua`, `OpenRouterAI.lua`, `local_ollama.lua`, `proxy.lua`, `requests.lua`, `prompt_builder.lua`) - Python service required for AI functionality

## Capabilities

### New Capabilities

- `python-llm-client`: Python module for making LLM API calls (GPT, OpenRouter, Ollama, proxy)
- `python-prompt-builder`: Python port of prompt building logic for dialogue, compression, speaker selection
- `python-dialogue-generator`: Orchestration of speaker selection → memory fetch → prompt build → LLM call → response
- `lua-zmq-subscriber`: Lua SUB socket to receive commands from Python (display dialogue, update state)
- `lua-state-query-handler`: Lua handlers responding to Python queries for memories, events, characters
- `python-state-query-client`: Python client for requesting state from Lua stores

### Modified Capabilities

- `python-zmq-router`: Add PUB socket for sending commands to Lua, add request-response correlation
- `lua-zmq-bridge`: Add SUB socket for receiving commands from Python
- `lua-event-publisher`: Add response handlers for query results

## Impact

- **bin/lua/infra/AI/**: Modules removed (`GPT.lua`, `OpenRouterAI.lua`, `local_ollama.lua`, `proxy.lua`, `requests.lua`, `prompt_builder.lua`)
- **bin/lua/app/talker.lua**: Modified to route all dialogue generation through Python
- **talker_service/**: Major additions - LLM clients, prompt builder, dialogue generator
- **Dependencies**: Python service gains `openai`, `httpx` for API calls
- **Breaking Change**: Python service must be running for AI dialogue to work

## 1. Python LLM Client Infrastructure

- [x] 1.1 Create `talker_service/src/talker_service/llm/` module directory
- [x] 1.2 Define `LLMClient` protocol with `async complete(messages, opts)` method in `base.py`
- [x] 1.3 Define `Message` and `LLMOptions` dataclasses in `models.py`
- [x] 1.4 Implement `OpenAIClient` with API key loading and rate limit handling
- [x] 1.5 Implement `OpenRouterClient` with endpoint and model configuration
- [x] 1.6 Implement `OllamaClient` with local endpoint and streaming support
- [x] 1.7 Implement `ProxyClient` for custom proxy endpoints
- [x] 1.8 Implement `get_llm_client(provider)` factory function
- [x] 1.9 Add MCM timeout setting for LLM calls (default 60s)
- [x] 1.10 Write unit tests for each client with mocked HTTP responses

## 2. Python Prompt Builder

- [x] 2.1 Create `talker_service/src/talker_service/prompts/` module directory
- [x] 2.2 Port `describe_character()` and `describe_event()` helper functions
- [x] 2.3 Port faction descriptions and relations helpers
- [x] 2.4 Implement `create_dialogue_request_prompt(speaker, memory_context)`
- [x] 2.5 Implement `create_pick_speaker_prompt(events, witnesses, mid_term_memory)`
- [x] 2.6 Implement `create_compress_memories_prompt(events, speaker)`
- [x] 2.7 Implement `create_update_narrative_prompt(speaker, narrative, events)`
- [x] 2.8 Add junk event filtering (artifacts, anomalies, reloads)
- [x] 2.9 Write unit tests comparing output structure to Lua version

## 3. Lua ZMQ Subscriber (Receive Commands)

- [x] 3.1 Add SUB socket initialization to `bridge.lua` connecting to port 5556
- [x] 3.2 Implement `poll_commands()` function with non-blocking receive
- [x] 3.3 Implement topic parsing and handler dispatch logic
- [x] 3.4 Add `register_handler(topic, func)` for command handlers
- [x] 3.5 Update `shutdown()` to close SUB socket
- [x] 3.6 Add game loop integration via time events for polling

## 4. Lua State Query Handlers

- [x] 4.1 Create `talker_zmq_query_handlers.script` for query handling
- [x] 4.2 Implement `memories.get` handler calling `memory_store:get_memory_context()`
- [x] 4.3 Implement `events.recent` handler calling `event_store:get_events_since()`
- [x] 4.4 Implement `character.get` handler calling `game_adapter.get_character_by_id()`
- [x] 4.5 Implement `characters.nearby` handler calling `game.get_characters_near()`
- [x] 4.6 Register all handlers on game start
- [x] 4.7 Add state.response publishing with request_id correlation

## 5. Lua Command Handlers

- [x] 5.1 Implement `dialogue.display` handler calling `game_adapter.display_dialogue()`
- [x] 5.2 Implement `memory.update` handler calling `memory_store:update_narrative()`
- [x] 5.3 Create dialogue event after display and store in event_store
- [x] 5.4 Register command handlers on game start

## 6. Extend Lua Event Publisher

- [x] 6.1 Add `send_state_response(request_id, type, data)` function to `publisher.lua`
- [x] 6.2 Add `send_error_response(request_id, type, error)` function
- [x] 6.3 Add `STATE_RESPONSE` topic constant
- [x] 6.4 Extend serialization for memory context and event lists

## 7. Python ZMQ Router Extensions

- [x] 7.1 Add PUB socket binding to port 5556 in `ZMQRouter`
- [x] 7.2 Implement `publish(topic, payload)` method
- [x] 7.3 Register internal handler for `state.response` topic routing
- [x] 7.4 Update shutdown to close PUB socket with linger timeout
- [x] 7.5 Write tests for bidirectional communication

## 8. Python State Query Client

- [x] 8.1 Create `talker_service/src/talker_service/state/` module directory
- [x] 8.2 Define `MemoryContext`, `Character`, `Event` response dataclasses
- [x] 8.3 Implement `StateQueryClient` class with request_id tracking
- [x] 8.4 Implement `query_memories(character_id)` method
- [x] 8.5 Implement `query_events_recent(since_ms, limit)` method
- [x] 8.6 Implement `query_character(character_id)` method
- [x] 8.7 Implement `query_characters_nearby(position, radius)` method
- [x] 8.8 Add timeout handling (default 30s from MCM)
- [x] 8.9 Write tests with mocked ZMQ responses

## 9. Python Dialogue Generator

- [x] 9.1 Create `talker_service/src/talker_service/dialogue/` module directory
- [x] 9.2 Implement `DialogueGenerator` class with dependency injection
- [x] 9.3 Implement speaker selection flow with cooldown tracking
- [x] 9.4 Implement memory context fetching via state query client
- [x] 9.5 Implement memory compression trigger (threshold check, lock, LLM call)
- [x] 9.6 Implement dialogue request flow (prompt build → LLM → clean response)
- [x] 9.7 Implement `dialogue.display` command publishing
- [x] 9.8 Implement `memory.update` command publishing
- [x] 9.9 Add request_id correlation throughout flow
- [x] 9.10 Add error handling and graceful degradation
- [x] 9.11 Write integration tests with mocked LLM and state

## 10. Wire Up Event-Driven Dialogue

- [x] 10.1 Add handler in Python for `game.event` that triggers dialogue generation
- [x] 10.2 Implement `is_important` and `should_someone_speak` logic in Python
- [x] 10.3 Modify `talker.lua` to NOT call Lua AI (remove AI_request calls)
- [x] 10.4 Ensure event publishing includes necessary context for Python
- [x] 10.5 Test full flow: trigger → event → Python → dialogue display

## 11. Remove Lua AI Modules (BREAKING)

- [x] 11.1 Remove `bin/lua/infra/AI/GPT.lua`
- [x] 11.2 Remove `bin/lua/infra/AI/OpenRouterAI.lua`
- [x] 11.3 Remove `bin/lua/infra/AI/local_ollama.lua`
- [x] 11.4 Remove `bin/lua/infra/AI/proxy.lua`
- [x] 11.5 Remove `bin/lua/infra/AI/requests.lua`
- [x] 11.6 Remove `bin/lua/infra/AI/prompt_builder.lua`
- [x] 11.7 Update `talker.lua` to remove unused AI requires
- [x] 11.8 Clean up any orphaned AI-related test files

## 12. Documentation and Testing

- [x] 12.1 Update README to mark Python service as required
- [x] 12.2 Update `copilot-instructions.md` with new architecture
- [x] 12.3 Update `Python_Service_Setup.md` with Phase 2 information
- [x] 12.4 Add MCM entries for new timeout settings (LLM 60s, queries 30s)
- [x] 12.5 Run full test suite (Python and Lua)
- [x] 12.6 Manual end-to-end testing in game
- [x] 12.7 Mark tasks.md complete

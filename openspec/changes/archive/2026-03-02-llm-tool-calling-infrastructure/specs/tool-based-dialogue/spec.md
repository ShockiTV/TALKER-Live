# tool-based-dialogue (delta)

## MODIFIED Requirements

### Requirement: Tool loop execution

The ConversationManager SHALL execute a tool loop: call `complete_with_tools(messages, tools=TOOLS)` on the LLM client, if the response contains tool calls execute them via `_execute_tool_call()` and append results as `Message.tool_result()` messages, repeat until the LLM returns a text response (the dialogue). A maximum iteration limit (default: 5) SHALL prevent infinite loops. The current stub comment in `handle_event()` SHALL be replaced with this real implementation.

#### Scenario: Standard dialogue flow with tools
- **WHEN** `complete_with_tools()` returns an `LLMToolResponse` with `tool_calls` containing a `get_memories` call
- **THEN** the ConversationManager SHALL execute `_execute_tool_call("get_memories", arguments)`
- **AND** SHALL append the assistant message (with tool_calls) to the message history
- **AND** SHALL append a `Message.tool_result()` with the JSON-serialized handler result
- **AND** SHALL call `complete_with_tools()` again with the updated message history

#### Scenario: LLM returns dialogue text directly
- **WHEN** `complete_with_tools()` returns an `LLMToolResponse` with `text` set and empty `tool_calls`
- **THEN** the text SHALL be extracted as the dialogue response
- **AND** the tool loop SHALL terminate

#### Scenario: Tool loop iteration limit reached
- **WHEN** the LLM makes more than 5 consecutive tool call rounds without generating text
- **THEN** the loop SHALL terminate with an error log
- **AND** no dialogue SHALL be displayed

#### Scenario: Multiple tool calls in single response
- **WHEN** the LLM returns multiple tool calls in a single `LLMToolResponse`
- **THEN** all tool calls SHALL be executed (in order)
- **AND** all results SHALL be appended before the next LLM call

### Requirement: Tool definitions

The ConversationManager SHALL provide two tools to the LLM (with `get_character_info` deferred to a future change):

1. **`get_memories`**: Required param `character_id` (string). Optional param `from_timestamp` (number). Returns structured memory tiers for the NPC. Python fetches from Lua via `state.query.batch`, translates technical fields to human-readable, and returns formatted result.

2. **`background`**: Required params `character_id` (string), `action` ("read"|"write"|"update"). For "write": requires `content` (traits, backstory, connections). For "update": requires field + operators. Reads/writes via `state.query.batch`/`state.mutate.batch`.

The existing `GET_BACKGROUND_TOOL` (read-only) SHALL be replaced by this full `BACKGROUND_TOOL`.

#### Scenario: get_memories tool called for speaker
- **WHEN** LLM calls `get_memories(character_id="12467")`
- **THEN** Python SHALL query `memory.events`, `memory.summaries`, `memory.digests`, `memory.cores` for character 12467
- **AND** SHALL translate technical fields (faction IDs, location IDs) to human-readable
- **AND** SHALL return structured tiers object

#### Scenario: get_memories with from_timestamp for diff read
- **WHEN** LLM calls `get_memories(character_id="12467", from_timestamp=340)`
- **THEN** only items with timestamp/end_ts >= 340 SHALL be returned

#### Scenario: background write tool creates new background
- **WHEN** LLM calls `background(character_id="12467", action="write", content={traits: [...], backstory: "...", connections: [...]})`
- **THEN** Python SHALL send `state.mutate.batch` with `set` operation on `memory.background`

#### Scenario: background read tool returns existing background
- **WHEN** LLM calls `background(character_id="12467", action="read")`
- **THEN** Python SHALL query `memory.background` and return the result (or null)

#### Scenario: background update tool modifies fields
- **WHEN** LLM calls `background(character_id="12467", action="update", field="connections", value=[...])`
- **THEN** Python SHALL send `state.mutate.batch` with an `update` operation on `memory.background`

### Requirement: LLM client must support tool calling

The `LLMClient` protocol SHALL provide a `complete_with_tools(messages, tools, opts)` method returning `LLMToolResponse`. All four providers (OpenAI, OpenRouter, Ollama, Proxy) SHALL implement this method. The existing `complete()` method SHALL remain unchanged for non-tool callers.

#### Scenario: LLM client receives tool definitions
- **WHEN** `complete_with_tools(messages, tools=[...])` is called
- **THEN** the LLM client SHALL include tool definitions in the API request

#### Scenario: LLM response contains tool calls
- **WHEN** the LLM decides to call a tool
- **THEN** the `LLMToolResponse` SHALL contain `ToolCall` objects with name, arguments, and call ID

#### Scenario: LLM response is text only
- **WHEN** the LLM generates dialogue without calling tools
- **THEN** the `LLMToolResponse` SHALL contain `text` with the dialogue and empty `tool_calls`

## ADDED Requirements

### Requirement: Background tool handler with write/update support

The ConversationManager SHALL register a `_handle_background()` handler that dispatches based on the `action` parameter: "read" queries via `state_client.execute_batch()`, "write" and "update" mutate via `state_client.mutate_batch()`. The handler replaces `_handle_get_background()`.

#### Scenario: Background read dispatched to state query
- **WHEN** `_handle_background(character_id="12467", action="read")` is called
- **THEN** it SHALL send a `state.query.batch` with resource `memory.background`
- **AND** SHALL return the background data (or empty dict)

#### Scenario: Background write dispatched to state mutation
- **WHEN** `_handle_background(character_id="12467", action="write", content={...})` is called
- **THEN** it SHALL send a `state.mutate.batch` with `set` operation on `memory.background`
- **AND** SHALL return a success confirmation

#### Scenario: Background update dispatched to state mutation
- **WHEN** `_handle_background(character_id="12467", action="update", field="connections", value=[...])` is called
- **THEN** it SHALL send a `state.mutate.batch` with `update` operation on `memory.background`
- **AND** SHALL return a success confirmation

### Requirement: Tool result formatting for memories

When returning memory data from `_handle_get_memories()`, the handler SHALL format the results as human-readable text suitable for LLM consumption. Each tier's entries SHALL include timestamps, event descriptions, and character names rather than raw IDs.

#### Scenario: Events tier formatted as readable text
- **WHEN** `get_memories` returns events tier data with raw event objects
- **THEN** each event SHALL be formatted with its timestamp, type, and human-readable description
- **AND** character IDs SHALL be resolved to names where available

#### Scenario: Empty tier returns informative message
- **WHEN** `get_memories` returns an empty tier (e.g., no digests yet)
- **THEN** the tool result SHALL include a message like "No digests available for this character"

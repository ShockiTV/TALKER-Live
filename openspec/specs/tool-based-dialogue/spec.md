# tool-based-dialogue

## Purpose

Python ConversationManager that handles speaker selection and dialogue generation in a single LLM tool-calling turn, replacing the 2-call SpeakerSelector + DialogueGenerator flow.

## Requirements

### Requirement: ConversationManager class

The system SHALL provide a `ConversationManager` class that maintains a conversation (system prompt + messages list) per session. It SHALL be the sole dialogue generation path, replacing `DialogueGenerator` and `SpeakerSelector`. After dialogue generation completes, it SHALL trigger witness event injection for all alive candidates and delegate compaction scheduling to `CompactionScheduler` instead of directly spawning per-character compaction tasks.

#### Scenario: ConversationManager replaces DialogueGenerator
- **WHEN** a game event triggers dialogue generation
- **THEN** `ConversationManager` SHALL handle the full flow: event formatting, LLM call with tools, response extraction

#### Scenario: ConversationManager created per session
- **WHEN** a new session connects
- **THEN** a `ConversationManager` SHALL be created with the session's config
- **AND** it SHALL maintain its own message history

#### Scenario: Post-dialogue witness injection
- **WHEN** `handle_event()` returns a speaker_id and dialogue_text
- **THEN** witness events SHALL be injected for all alive candidates via `_inject_witness_events()`
- **AND** `CompactionScheduler.schedule()` SHALL be called with all candidate character IDs

#### Scenario: _characters_touched set removed
- **WHEN** the tool loop executes tool calls
- **THEN** individual character IDs SHALL NOT be tracked in a `_characters_touched` set
- **AND** compaction scheduling SHALL use the full candidates list instead

### Requirement: System prompt construction

The system prompt SHALL contain Zone rules, dialogue guidelines, memory read instructions, and tool definitions. It SHALL include a Notable Zone Inhabitants section between world context and tool instructions. The prompt order SHALL be: faction → personality → world context → **notable inhabitants** → tool instructions → response format. The system prompt is stable across turns within a session except for the world/inhabitants sections which vary per-event.

#### Scenario: System prompt includes tool usage instructions
- **WHEN** ConversationManager is initialized
- **THEN** the system prompt SHALL instruct the LLM to pick a speaker, call `get_memories` for that speaker, optionally call `background`, then generate dialogue

#### Scenario: System prompt includes notable inhabitants section
- **WHEN** the system prompt is built with a world context containing a Notable Zone Inhabitants section
- **THEN** the inhabitants section SHALL appear after world context and before tool instructions
- **AND** SHALL list relevant NPCs with names, descriptions, factions, and alive/dead status

#### Scenario: System prompt is stable across turns
- **WHEN** multiple events are processed within the same area
- **THEN** the system prompt SHALL NOT change between turns

### Requirement: Event message formatting

Each game event SHALL be formatted as a user message containing: event description, game time with timestamp, candidate list with traits, and world context. This single message provides all information for speaker selection and dialogue generation.

#### Scenario: Event message includes candidates with traits
- **WHEN** a DEATH event occurs with witnesses Wolf (traits: "gruff, protective") and Fanatic (traits: none)
- **THEN** the event message SHALL include a `Candidates:` section listing each witness with their ID, faction, rank, and traits (or "none")

#### Scenario: Event message includes world context
- **WHEN** an event occurs
- **THEN** the event message SHALL include location, weather, and time of day from the pre-fetch batch

#### Scenario: Event message includes game timestamp
- **WHEN** an event occurs at game time 380
- **THEN** the event message SHALL include `[timestamp: 380]` for diff-read tracking

### Requirement: Pre-fetch state batch

Before appending the event message, the system SHALL send a single `state.query.batch` to fetch: `query.world` (location, time, weather), `query.characters_alive` (dead story NPCs), and `memory.background` per candidate witness (for traits).

#### Scenario: Pre-fetch retrieves world and traits
- **WHEN** an event has 3 witness candidates
- **THEN** a single `state.query.batch` SHALL be sent with `query.world`, `query.characters_alive`, and 3 `memory.background` sub-queries

#### Scenario: Missing background returns null traits
- **WHEN** a candidate NPC has no background yet
- **THEN** the pre-fetch SHALL return null for that NPC's background
- **AND** the event message SHALL show "Traits: none" for that candidate

### Requirement: Tool definitions

The ConversationManager SHALL provide three tools to the LLM:

1. **`get_memories`**: Required param `character_id` (string). Optional param `tiers` (array of strings). Returns structured memory tiers for the NPC. Python fetches from Lua via `state.query.batch`, translates technical fields to human-readable, and returns formatted result.

2. **`background`**: Required params `character_id` (string), `action` ("read"|"write"|"update"). For "write": requires `content` (traits, backstory, connections). For "update": requires field + operators. Reads/writes via `state.query.batch`/`state.mutate.batch`.

3. **`get_character_info`**: Required param `character_id` (string). Returns character info (name, faction, rank, gender, background) plus squad members with the same fields. Side-effect: creates memory entries for new squad members. Used when the LLM needs squad composition or background context for a character.

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

#### Scenario: get_character_info tool returns character with squad
- **WHEN** LLM calls `get_character_info(character_id="12467")`
- **THEN** Python SHALL query `query.character_info` via `state.query.batch`
- **AND** SHALL return `{character: {..., gender, background}, squad_members: [...]}`

### Requirement: get_character_info tool in tool set

The ConversationManager SHALL include `get_character_info` as a third tool in the TOOLS list, alongside `get_memories` and `background`.

#### Scenario: Three tools available to LLM
- **WHEN** the ConversationManager starts a tool-calling conversation
- **THEN** the LLM SHALL receive three tool definitions: `get_memories`, `background`, and `get_character_info`

#### Scenario: get_character_info dispatched in tool loop
- **WHEN** the LLM returns a tool call for `get_character_info` during the tool loop
- **THEN** the ConversationManager SHALL dispatch it to `_handle_get_character_info` via the `_tool_handlers` registry
- **AND** SHALL append the result as a `Message.tool_result()` before the next LLM call

### Requirement: Tool loop execution

The ConversationManager SHALL execute a tool loop: call `complete_with_tools(messages, tools=TOOLS)` on the LLM client, if the response contains tool calls execute them via `_execute_tool_call()` and append results as `Message.tool_result()` messages, repeat until the LLM returns a text response (the dialogue). A maximum iteration limit (default: 5) SHALL prevent infinite loops.

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

### Requirement: Response extraction

After the LLM generates dialogue text, the ConversationManager SHALL extract the speaker ID (from the LLM's tool call pattern or explicit mention) and the dialogue text, then publish `dialogue.display` to Lua.

#### Scenario: Dialogue published to Lua
- **WHEN** the LLM generates dialogue as speaker Wolf (id: 12467)
- **THEN** `dialogue.display` SHALL be sent with `speaker_id=12467` and the dialogue text

#### Scenario: Speaker ID extracted from tool calls
- **WHEN** the LLM called `get_memories("12467")` before generating dialogue
- **THEN** speaker_id SHALL be inferred as 12467

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

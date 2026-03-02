# tool-based-dialogue

## Purpose

Python ConversationManager that handles speaker selection and dialogue generation in a single LLM tool-calling turn, replacing the 2-call SpeakerSelector + DialogueGenerator flow.

## Requirements

### Requirement: ConversationManager class

The system SHALL provide a `ConversationManager` class that maintains a conversation (system prompt + messages list) per session. It SHALL be the sole dialogue generation path, replacing `DialogueGenerator` and `SpeakerSelector`.

#### Scenario: ConversationManager replaces DialogueGenerator
- **WHEN** a game event triggers dialogue generation
- **THEN** `ConversationManager` SHALL handle the full flow: event formatting, LLM call with tools, response extraction

#### Scenario: ConversationManager created per session
- **WHEN** a new session connects
- **THEN** a `ConversationManager` SHALL be created with the session's config
- **AND** it SHALL maintain its own message history

### Requirement: System prompt construction

The system prompt SHALL contain Zone rules, dialogue guidelines, memory read instructions, and tool definitions. It SHALL be stable across turns (cacheable prefix).

#### Scenario: System prompt includes tool usage instructions
- **WHEN** ConversationManager is initialized
- **THEN** the system prompt SHALL instruct the LLM to pick a speaker, call `get_memories` for that speaker, optionally call `background`, then generate dialogue

#### Scenario: System prompt is stable across turns
- **WHEN** multiple events are processed
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

The ConversationManager SHALL provide two tools to the LLM (with `get_character_info` deferred to a future change):

1. **`get_memories`**: Required param `character_id` (string). Optional param `from_timestamp` (number). Returns structured memory tiers for the NPC. Python fetches from Lua via `state.query.batch`, translates technical fields to human-readable, and returns formatted result.

2. **`background`**: Required params `character_id` (string), `action` ("read"|"write"|"update"). For "write": requires `content` (traits, backstory, connections). For "update": requires field + operators. Reads/writes via `state.query.batch`/`state.mutate.batch`.

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

### Requirement: Tool loop execution

The ConversationManager SHALL execute a tool loop: send messages to LLM, if LLM returns tool calls execute them and append results, repeat until LLM returns a text response (the dialogue). A maximum iteration limit (default: 5) SHALL prevent infinite loops.

#### Scenario: Standard dialogue flow with tools
- **WHEN** LLM responds with `get_memories` tool call
- **THEN** Python SHALL execute the tool, append the result as a tool message
- **AND** send the updated messages back to the LLM

#### Scenario: LLM returns dialogue text directly
- **WHEN** LLM responds with text content (no tool calls)
- **THEN** the text SHALL be extracted as the dialogue response

#### Scenario: Tool loop iteration limit reached
- **WHEN** LLM makes more than 5 consecutive tool calls without generating text
- **THEN** the loop SHALL terminate with an error
- **AND** no dialogue SHALL be displayed

### Requirement: Response extraction

After the LLM generates dialogue text, the ConversationManager SHALL extract the speaker ID (from the LLM's tool call pattern or explicit mention) and the dialogue text, then publish `dialogue.display` to Lua.

#### Scenario: Dialogue published to Lua
- **WHEN** the LLM generates dialogue as speaker Wolf (id: 12467)
- **THEN** `dialogue.display` SHALL be sent with `speaker_id=12467` and the dialogue text

#### Scenario: Speaker ID extracted from tool calls
- **WHEN** the LLM called `get_memories("12467")` before generating dialogue
- **THEN** speaker_id SHALL be inferred as 12467

### Requirement: LLM client must support tool calling

The `complete()` method on LLM clients SHALL accept optional `tools` and `tool_choice` parameters. The return type SHALL be extended to support structured responses with tool calls.

#### Scenario: LLM client receives tool definitions
- **WHEN** `complete(messages, tools=[...])` is called
- **THEN** the LLM client SHALL include tool definitions in the API request

#### Scenario: LLM response contains tool calls
- **WHEN** the LLM decides to call a tool
- **THEN** the response SHALL contain tool call objects with name, arguments, and call ID

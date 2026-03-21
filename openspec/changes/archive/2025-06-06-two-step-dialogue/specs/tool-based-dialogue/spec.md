## MODIFIED Requirements

### Requirement: ConversationManager class

The system SHALL provide a `ConversationManager` class that maintains a persistent conversation (system prompt + messages list) per session. It SHALL be the sole dialogue generation path. It SHALL execute a 2-step deterministic flow (ephemeral speaker selection, then persistent dialogue generation) instead of a tool-calling loop. After dialogue generation completes, it SHALL trigger witness event injection for all alive candidates and delegate compaction scheduling to `CompactionScheduler`.

#### Scenario: ConversationManager uses 2-step flow
- **WHEN** a game event triggers dialogue generation
- **THEN** `ConversationManager` SHALL handle the full flow: background check → speaker pick → memory injection → dialogue generation → response extraction

#### Scenario: ConversationManager created per session
- **WHEN** a new session connects
- **THEN** a `ConversationManager` SHALL be created with the session's config
- **AND** it SHALL maintain its own message history and memory tracking dict

#### Scenario: Post-dialogue witness injection
- **WHEN** `handle_event()` returns a speaker_id and dialogue_text
- **THEN** witness events SHALL be injected for all alive candidates via `_inject_witness_events()`
- **AND** `CompactionScheduler.schedule()` SHALL be called with all candidate character IDs

### Requirement: Tool definitions

The ConversationManager SHALL NOT expose any tools to the LLM. The `TOOLS` list, `GET_MEMORIES_TOOL`, `BACKGROUND_TOOL`, and `GET_CHARACTER_INFO_TOOL` schema definitions SHALL be removed. The `_tool_handlers` registry SHALL be removed. All data fetching SHALL be performed deterministically by Python code, not by LLM tool calls.

#### Scenario: No tools passed to LLM
- **WHEN** `ConversationManager` calls `complete()` for any step
- **THEN** no tool definitions SHALL be included in the call
- **AND** the LLM SHALL respond with plain text only

#### Scenario: Tool handler methods retained as internal helpers
- **WHEN** Python needs to fetch memories or backgrounds
- **THEN** it SHALL call `_fetch_memories()` / `_fetch_full_memory()` / `_fetch_diff_memory()` and `BackgroundGenerator.ensure_backgrounds()` directly as internal methods
- **AND** these methods SHALL NOT be registered as LLM-callable tools

### Requirement: Tool loop execution

**This requirement is removed.**

#### Scenario: No tool loop
- **WHEN** `handle_event()` processes an event
- **THEN** there SHALL be no iterative tool-calling loop
- **AND** `complete_with_tool_loop()` SHALL NOT be called

### Requirement: System prompt construction

The system prompt SHALL contain Zone setting context, world state, notable inhabitants section, and dialogue style guidelines. It SHALL NOT contain per-character faction persona, personality text, or tool usage instructions. The prompt order SHALL be: world context → notable inhabitants → dialogue guidelines.

#### Scenario: System prompt excludes per-character persona
- **WHEN** the system prompt is constructed
- **THEN** it SHALL NOT include faction description for any specific character
- **AND** it SHALL NOT include personality text
- **AND** it SHALL NOT include tool definitions or tool usage instructions

#### Scenario: System prompt includes world and dialogue guidance
- **WHEN** the system prompt is constructed
- **THEN** it SHALL include current world context (location, time, weather)
- **AND** it SHALL include the Notable Zone Inhabitants section
- **AND** it SHALL include dialogue style guidelines (authentic, concise, in-character)

### Requirement: Event message formatting

Each game event SHALL be formatted as a structured description containing event type, actor, victim (if applicable), location, and timestamp. For the speaker picker, candidates SHALL be presented as JSON with full backgrounds. For dialogue generation, the event SHALL be combined with the speaker's memory context and persona instructions.

#### Scenario: Picker event message
- **WHEN** the speaker picker step builds the event message
- **THEN** it SHALL describe the event type, actor, victim, and location concisely

#### Scenario: Dialogue event message includes memory and persona
- **WHEN** the dialogue generation step builds the user message
- **THEN** it SHALL include the speaker's background (traits, backstory, connections)
- **AND** it SHALL include the speaker's memory context (full or diff)
- **AND** it SHALL include the event description
- **AND** it SHALL instruct the LLM to react as that specific character

### Requirement: Response extraction

After the dialogue generation step, the ConversationManager SHALL extract the dialogue text directly from the assistant response. No `[SPEAKER: id]` parsing is needed since the speaker was already determined in the picker step.

#### Scenario: Dialogue text extracted directly
- **WHEN** the LLM generates a dialogue response
- **THEN** the full response text SHALL be used as the dialogue (after stripping whitespace)
- **AND** the speaker_id SHALL be the one selected by the picker step

## REMOVED Requirements

### Requirement: Tool loop execution
**Reason**: Replaced by deterministic 2-step flow. The LLM no longer calls tools — Python fetches all data and injects it as message content.
**Migration**: `complete_with_tool_loop()` calls replaced by two sequential `complete()` calls. Tool handler methods retained as internal Python helpers.

### Requirement: Pre-fetch state batch
**Reason**: The pre-fetch concept is subsumed by the new 2-step flow. Background batch-reading is now part of the background completeness check, and memory fetching is part of the dialogue generation step. World context enrichment remains but is not a separate "pre-fetch" — it's part of system prompt construction.
**Migration**: World context fetching moves to system prompt build. Background fetching moves to background completeness check. Memory fetching moves to dialogue step.

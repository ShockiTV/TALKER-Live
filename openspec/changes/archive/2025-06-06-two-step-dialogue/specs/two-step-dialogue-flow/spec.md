## ADDED Requirements

### Requirement: Two-step handle_event flow

The `ConversationManager.handle_event()` method SHALL execute dialogue generation in two sequential LLM calls against a single persistent conversation: (1) an ephemeral speaker picker step, and (2) a persistent dialogue generation step. No LLM tools SHALL be exposed — both steps use plain `complete()`.

#### Scenario: Standard event processing
- **WHEN** `handle_event()` is called with an event, candidates, world, and traits
- **THEN** it SHALL first run the speaker picker step to choose a speaker
- **AND** then run the dialogue generation step to produce dialogue for the chosen speaker
- **AND** return `(speaker_id, dialogue_text)`

#### Scenario: Single candidate skips picker
- **WHEN** `handle_event()` is called with exactly one NPC candidate
- **THEN** the speaker picker step SHALL be skipped
- **AND** that candidate SHALL be used as the speaker directly

### Requirement: Ephemeral speaker picker messages

The speaker picker step SHALL inject temporary messages into the conversation, call `complete()`, extract the speaker ID, and then remove all injected messages (including the assistant response) from the conversation history.

#### Scenario: Picker messages injected and removed
- **WHEN** the speaker picker step runs with 3 candidates
- **THEN** it SHALL append: (1) a user message with candidate backgrounds as JSON, (2) a user message with the event description, (3) a user message instructing "pick the speaker, respond with only their character ID"
- **AND** after receiving the assistant response, all 4 messages (3 user + 1 assistant) SHALL be removed from the conversation history

#### Scenario: Picker response parsed as character ID
- **WHEN** the LLM responds with a character ID (e.g., "12467")
- **THEN** the response SHALL be parsed and validated against the candidate list
- **AND** if the ID matches a candidate, that candidate SHALL be selected as speaker

#### Scenario: Picker response does not match any candidate
- **WHEN** the LLM responds with an ID not in the candidate list
- **THEN** the system SHALL fall back to the first candidate
- **AND** log a warning about the invalid picker response

### Requirement: Persistent dialogue generation messages

The dialogue generation step SHALL inject a user message containing the speaker's memory context and event description, call `complete()`, and keep both the user message and assistant response in the conversation history permanently.

#### Scenario: Dialogue turn persisted in history
- **WHEN** the dialogue generation step completes for speaker "Wolf"
- **THEN** the conversation history SHALL contain the user message (memory + event + instruction) and the assistant response (dialogue text)
- **AND** these messages SHALL remain for subsequent events in the same session

#### Scenario: Accumulated history visible to future turns
- **WHEN** a second event triggers dialogue generation in the same session
- **THEN** the LLM SHALL see the prior event's user message and dialogue response in its context
- **AND** the speaker picker for the second event SHALL also see this history

### Requirement: Candidate backgrounds as JSON in picker

The speaker picker's candidate message SHALL present all candidates as a JSON array, with each entry containing the character's ID, name, faction, rank, and full background (traits, backstory, connections).

#### Scenario: Candidate JSON format
- **WHEN** the picker step builds the candidate message
- **THEN** each candidate entry SHALL include `id`, `name`, `faction`, `rank`, and `background` fields
- **AND** the `background` field SHALL contain the full background object (traits array, backstory string, connections array)

#### Scenario: Event message format in picker
- **WHEN** the picker step builds the event message
- **THEN** it SHALL describe the event type, actor, victim (if applicable), and location
- **AND** it SHALL be concise — no narrative framing, just structured event description

### Requirement: System prompt without per-character persona

The system prompt SHALL contain Zone-setting context, world state, notable inhabitants, and dialogue guidelines. It SHALL NOT include any per-character personality or faction persona — that context comes from the memory/background injection in each turn's user message.

#### Scenario: System prompt content
- **WHEN** the system prompt is built
- **THEN** it SHALL include world context (location, time, weather)
- **AND** it SHALL include notable inhabitants section
- **AND** it SHALL include dialogue style guidelines (tone, length, authenticity)
- **AND** it SHALL NOT include faction description or personality text for any specific character

#### Scenario: System prompt stability across events
- **WHEN** two events occur in the same area
- **THEN** the system prompt SHALL remain unchanged between them

### Requirement: No LLM tools exposed

The ConversationManager SHALL NOT pass any tool definitions to `complete()` calls. Both the speaker picker and dialogue generation steps SHALL use plain text completion without tool-calling capability.

#### Scenario: complete() called without tools
- **WHEN** the ConversationManager calls `llm_client.complete()` for speaker selection
- **THEN** no `tools` parameter SHALL be passed
- **AND** the LLM SHALL respond with plain text only

#### Scenario: complete() called without tools for dialogue
- **WHEN** the ConversationManager calls `llm_client.complete()` for dialogue generation
- **THEN** no `tools` parameter SHALL be passed

### Requirement: Post-dialogue witness injection and compaction preserved

After dialogue generation completes, the system SHALL continue to inject witness events for all alive candidates and schedule compaction, identical to the current behavior.

#### Scenario: Witness injection after dialogue
- **WHEN** `handle_event()` returns a speaker_id and dialogue_text
- **THEN** `_inject_witness_events()` SHALL be called for all alive candidates
- **AND** `CompactionScheduler.schedule()` SHALL be called with all candidate character IDs

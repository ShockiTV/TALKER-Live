# two-step-dialogue-flow

## Purpose

Defines the two-step deterministic dialogue flow in `ConversationManager.handle_event()`: an ephemeral speaker picker step followed by a persistent dialogue generation step, both using plain `complete()` without LLM tools.

## Requirements

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

The speaker picker step SHALL inject a single temporary user message into the conversation referencing the event by timestamp and listing candidate IDs. It SHALL call `complete()`, extract the speaker ID, and then remove the injected user message and assistant response from the conversation history. All factual context (event details, candidate backgrounds) SHALL already be present as system messages.

#### Scenario: Picker messages injected and removed
- **WHEN** the speaker picker step runs with 3 candidates
- **THEN** it SHALL append a single user message: `"Pick speaker for EVT:{ts}. Candidates: {id1}, {id2}, {id3}"`
- **AND** after receiving the assistant response, both messages (1 user + 1 assistant) SHALL be removed from the conversation history

#### Scenario: Picker response parsed as character ID
- **WHEN** the LLM responds with a character ID (e.g., "12467")
- **THEN** the response SHALL be parsed and validated against the candidate list
- **AND** if the ID matches a candidate, that candidate SHALL be selected as speaker

#### Scenario: Picker response does not match any candidate
- **WHEN** the LLM responds with an ID not in the candidate list
- **THEN** the system SHALL fall back to the first candidate
- **AND** log a warning about the invalid picker response

### Requirement: Persistent dialogue generation messages

The dialogue generation step SHALL inject a user message containing a pointer to the triggering event, the character ID, and optionally the speaker's personal narrative memories (summaries/digests/cores text). It SHALL call `complete()` and keep both the user message and assistant response in the conversation history permanently. Event details and character backgrounds SHALL NOT be inlined — they are already present as system messages.

#### Scenario: Dialogue turn persisted in history
- **WHEN** the dialogue generation step completes for speaker "Wolf" reacting to EVT:{ts}
- **THEN** the user message SHALL reference the event by `EVT:{ts}` and character by ID
- **AND** the user message SHALL include personal narrative memories if available
- **AND** the user message SHALL NOT inline the event description or background
- **AND** both user message and assistant response SHALL remain in history for subsequent events

#### Scenario: Accumulated history visible to future turns
- **WHEN** a second event triggers dialogue generation in the same session
- **THEN** the LLM SHALL see the prior event's user message and dialogue response in its context
- **AND** the speaker picker for the second event SHALL also see this history

### Requirement: Candidate backgrounds as system messages (not inline in picker)

Candidate backgrounds are NO LONGER inlined in the picker user message. They are injected as `BG:{char_id}` system messages before the picker step runs. The picker user message only lists candidate IDs.

#### Scenario: Candidate backgrounds as system messages
- **WHEN** the picker step is about to run
- **THEN** all candidate backgrounds SHALL already exist as `BG:{char_id}` system messages
- **AND** the picker user message SHALL reference candidates by ID only
- **AND** no JSON candidate array SHALL be constructed for the picker

#### Scenario: Event context as system message
- **WHEN** the picker step is about to run
- **THEN** the triggering event SHALL already exist as an `EVT:{ts}` system message
- **AND** the picker user message SHALL reference it by timestamp only

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

### Requirement: System messages injected before picker step

Before the speaker picker runs, the system SHALL ensure all required system messages are present: the triggering event (`EVT:{ts}`), all candidate backgrounds (`BG:{char_id}`), and any previously unseen compacted memories for candidates.

#### Scenario: System messages for event and backgrounds
- **WHEN** `handle_event()` is called with an event and 3 candidates
- **THEN** the event SHALL be injected as `EVT:{ts}` if not already present
- **AND** each candidate's background SHALL be injected as `BG:{char_id}` if not already present
- **AND** all injection SHALL occur before the picker user message is created

## ADDED Requirements

### Requirement: Background completeness check before speaker selection

Before running the speaker picker, the system SHALL batch-read `memory.background` for all candidates. If any candidate has a null/empty background, background generation SHALL be triggered.

#### Scenario: All candidates have backgrounds
- **WHEN** all candidates return non-null backgrounds from the batch read
- **THEN** background generation SHALL be skipped
- **AND** the speaker picker SHALL proceed immediately

#### Scenario: Some candidates lack backgrounds
- **WHEN** 2 out of 5 candidates return null backgrounds
- **THEN** background generation SHALL be triggered for those 2 characters
- **AND** the speaker picker SHALL NOT run until generation completes

### Requirement: Separate LLM conversation for background generation

Background generation SHALL run in a dedicated one-shot LLM conversation, separate from the main dialogue conversation. It SHALL use the main model (not fast model) since background creation is creative work.

#### Scenario: Background conversation isolation
- **WHEN** background generation runs for missing characters
- **THEN** it SHALL create a new temporary message list (system + user)
- **AND** it SHALL NOT share message history with the main dialogue conversation
- **AND** it SHALL call `llm_client.complete()` once and discard the conversation afterward

#### Scenario: System prompt for background generation
- **WHEN** the background generation conversation is built
- **THEN** the system prompt SHALL instruct the LLM to act as a GM creating character backgrounds for STALKER NPCs
- **AND** SHALL instruct it to generate traits (3-6 adjectives), backstory (GM briefing style), and connections (referencing other known characters)
- **AND** SHALL instruct it to return valid JSON output

### Requirement: JSON input format for background generation

The background generator SHALL receive a JSON payload containing all relevant characters — those with existing backgrounds (as reference) and those needing generation (with null backgrounds).

#### Scenario: Input includes existing backgrounds as reference
- **WHEN** 3 characters have backgrounds and 2 need generation
- **THEN** the input JSON SHALL include all 5 characters
- **AND** characters with backgrounds SHALL have their full `background` field populated
- **AND** characters needing generation SHALL have `"background": null`

#### Scenario: Input includes squad membership
- **WHEN** characters belong to squads
- **THEN** the input JSON SHALL include squad information (squad name or leader reference)
- **AND** the LLM SHALL use this to generate appropriate connections between squad members

#### Scenario: Input includes character metadata
- **WHEN** the input JSON is built for each character
- **THEN** each entry SHALL include `id`, `name`, `faction`, `rank`, and `gender`

### Requirement: JSON output parsing for generated backgrounds

The background generator's LLM response SHALL be parsed as a JSON array of background objects, one per character that needed generation.

#### Scenario: Successful JSON parse
- **WHEN** the LLM returns a valid JSON array of background objects
- **THEN** each object SHALL be parsed and validated to contain `id`, and `background` with `traits` (array), `backstory` (string), and `connections` (array)

#### Scenario: Malformed JSON response
- **WHEN** the LLM returns invalid JSON
- **THEN** the system SHALL log an error
- **AND** SHALL proceed to speaker selection with the candidates as-is (some with null backgrounds)
- **AND** the event SHALL NOT be dropped

### Requirement: Persist generated backgrounds via state mutations

After successfully parsing generated backgrounds, the system SHALL persist each one via `state.mutate.batch` with `set` operation on `memory.background`.

#### Scenario: Backgrounds persisted for generated characters
- **WHEN** 2 backgrounds are generated successfully
- **THEN** a `state.mutate.batch` SHALL be sent with 2 `set` mutations on `memory.background`
- **AND** a successful mutation result SHALL mean the background is available for future reads

#### Scenario: Mutation failure is non-fatal
- **WHEN** the mutation batch fails
- **THEN** the system SHALL log a warning
- **AND** SHALL proceed with speaker selection using the generated (but unpersisted) backgrounds in memory

### Requirement: Character info fetching for generation context

When background generation is needed, the system SHALL fetch `query.character_info` for missing characters to get gender, squad members, and any other metadata not in the candidate payload.

#### Scenario: Character info batch for missing backgrounds
- **WHEN** 2 characters need background generation
- **THEN** a `state.query.batch` SHALL be sent with `query.character_info` for those 2 characters
- **AND** the response (gender, squad members, etc.) SHALL be included in the background generation input JSON

### Requirement: Blocking execution before speaker selection

Background generation SHALL block the event processing pipeline — the speaker picker SHALL NOT run until all missing backgrounds have been generated (or generation has failed).

#### Scenario: Speaker picker waits for background generation
- **WHEN** background generation is triggered for 2 characters
- **THEN** the speaker picker SHALL NOT execute until background generation returns
- **AND** the total event processing time SHALL include background generation latency

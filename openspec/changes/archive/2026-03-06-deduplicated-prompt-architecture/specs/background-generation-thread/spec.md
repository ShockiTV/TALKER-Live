# background-generation-thread

**Status:** delta  
**Change:** deduplicated-prompt-architecture

## MODIFIED Requirements

### Requirement: Separate LLM conversation for background generation

Background generation SHALL run in a dedicated one-shot LLM conversation, separate from the main dialogue conversation. It SHALL use the fast model (`fast_llm_client`) since background creation is structured JSON generation that does not require creative capability.

#### Scenario: Background conversation isolation
- **WHEN** background generation runs for missing characters
- **THEN** it SHALL create a new temporary message list (system + user)
- **AND** it SHALL NOT share message history with the main dialogue conversation
- **AND** it SHALL call `fast_llm_client.complete()` once and discard the conversation afterward

#### Scenario: System prompt for background generation
- **WHEN** the background generation conversation is built
- **THEN** the system prompt SHALL instruct the LLM to act as a GM creating character backgrounds for STALKER NPCs
- **AND** SHALL instruct it to generate traits (3-6 adjectives), backstory (GM briefing style), and connections (referencing other known characters)
- **AND** SHALL instruct it to return valid JSON output

#### Scenario: Fast model client injected at construction
- **WHEN** `BackgroundGenerator` is constructed
- **THEN** it SHALL accept a `fast_llm_client` parameter
- **AND** SHALL use that client for all `complete()` calls

## ADDED Requirements

### Requirement: Generated backgrounds injected as system messages

After background generation completes, the generated backgrounds SHALL be injected into the main conversation as `BG:{char_id}` system messages via the deduplication tracker, in addition to being persisted via state mutations.

#### Scenario: Background available as system message before picker
- **WHEN** background generation produces a background for character "12467"
- **THEN** a system message `BG:12467 — Wolf (Freedom)\n{background_text}` SHALL be appended to the main conversation
- **AND** the deduplication tracker SHALL mark "12467" as injected
- **AND** the speaker picker SHALL see this background in its context

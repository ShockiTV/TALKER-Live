# python-prompt-builder

## Purpose

Python module that constructs prompts for dialogue generation, speaker selection, and memory compression.

## Requirements

### Dialogue Prompt Builder

The system MUST provide `create_dialogue_request_prompt(speaker, memory_context)` for dialogue generation.

#### Scenario: Build dialogue prompt with full context
- **WHEN** create_dialogue_request_prompt is called with speaker and memory_context
- **THEN** the result contains CHARACTER ANCHOR section with speaker details
- **AND** contains LONG-TERM MEMORIES section if narrative exists
- **AND** contains CURRENT EVENTS section with recent events

### Speaker Selection Prompt Builder

The system MUST provide `create_pick_speaker_prompt(events, witnesses, mid_term_memory)` for speaker selection.

#### Scenario: Build speaker selection prompt
- **WHEN** create_pick_speaker_prompt is called with events and witnesses
- **THEN** the result contains CANDIDATES section with witness IDs
- **AND** contains EVENTS section with up to 8 events
- **AND** instructs JSON output format with id field

### Memory Compression Prompt Builder

The system MUST provide `create_compress_memories_prompt(events, speaker)` for memory compression.

#### Scenario: Build compression prompt filtering junk
- **WHEN** create_compress_memories_prompt is called with events including artifacts
- **THEN** artifact events are excluded from the prompt
- **AND** non-junk events appear in chronological order

### Narrative Update Prompt Builder

The system MUST provide `create_update_narrative_prompt(speaker, narrative, events)` for updating narratives.

#### Scenario: Handle empty narrative (bootstrap)
- **WHEN** create_update_narrative_prompt is called with empty narrative
- **THEN** the prompt uses bootstrapping instructions

### Message Model

The system MUST define `Message` dataclass with role and content fields.

#### Scenario: Message serialization
- **WHEN** Message is created with role and content
- **THEN** it can be serialized to dict format for LLM APIs

### Character Context Helpers

The system MUST provide helper functions for formatting characters and events.

#### Scenario: Describe character
- **WHEN** describe_character(char) is called
- **THEN** formatted string with name, faction, rank is returned

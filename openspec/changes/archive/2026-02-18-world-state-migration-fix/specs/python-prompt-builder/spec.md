# python-prompt-builder (delta)

## ADDED Requirements

### Requirement: Query Current Scene JIT

The system SHALL query current scene context during prompt building instead of reading from event.

#### Scenario: Dialogue prompt queries scene
- **WHEN** create_dialogue_request_prompt is called
- **THEN** system sends world.context ZMQ query
- **AND** uses response data for CURRENT LOCATION section
- **AND** does NOT read world_context from events

#### Scenario: Scene query returns structured data
- **WHEN** scene query response is received
- **THEN** prompt builder extracts loc, poi, time, weather
- **AND** formats CURRENT LOCATION section from these fields

### Requirement: Include World Context Section

The system SHALL include a DYNAMIC WORLD STATE / NEWS section in dialogue prompts when relevant world context exists.

#### Scenario: Dead leaders included in prompt
- **WHEN** build_world_context returns dead leaders text
- **THEN** dialogue prompt includes "## DYNAMIC WORLD STATE / NEWS" section
- **AND** section contains dead leaders information

#### Scenario: Info portions included
- **WHEN** Brain Scorcher is disabled
- **THEN** dialogue prompt world state section mentions this

#### Scenario: Regional politics included when relevant
- **WHEN** player is in Cordon
- **AND** build_regional_context returns truce information
- **THEN** dialogue prompt includes this in world state section

#### Scenario: No world state section when nothing notable
- **WHEN** all leaders alive, no info portions, no regional context
- **THEN** dialogue prompt omits DYNAMIC WORLD STATE / NEWS section
- **OR** section contains only "Normal."

## MODIFIED Requirements

### Requirement: Dialogue Prompt Builder

The system MUST provide `create_dialogue_request_prompt(speaker, memory_context)` for dialogue generation.

The prompt builder SHALL:
1. Query current scene via world.context ZMQ query
2. Build world context via python-world-context module
3. Include CURRENT LOCATION section from scene query
4. Include DYNAMIC WORLD STATE / NEWS section if world context is non-empty

#### Scenario: Build dialogue prompt with full context
- **WHEN** create_dialogue_request_prompt is called with speaker and memory_context
- **THEN** the result contains CHARACTER ANCHOR section with speaker details
- **AND** contains LONG-TERM MEMORIES section if narrative exists
- **AND** contains CURRENT EVENTS section with recent events
- **AND** queries current scene for CURRENT LOCATION (not from event.world_context)
- **AND** includes DYNAMIC WORLD STATE / NEWS if world context exists


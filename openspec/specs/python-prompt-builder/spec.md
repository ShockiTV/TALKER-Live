# python-prompt-builder

## Purpose

Python module that constructs prompts for dialogue generation, speaker selection, and memory compression.

## Requirements

### Text Lookup

The system MUST provide `resolve_personality(id)`, `resolve_backstory(id)`, and `resolve_faction_name(faction_id)` for ID→text lookup.

#### Storage Format
- Personality and backstory texts are stored as Python dict constants in `.py` modules
- Located at `talker_service/texts/personality/` and `talker_service/texts/backstory/`
- Each faction has its own module (e.g., `bandit.py`, `unique.py`)
- Each module exports a `TEXTS` dict mapping string keys to string values
- Faction names and descriptions are stored in `talker_service/src/talker_service/prompts/factions.py`
- Faction descriptions are keyed by technical faction ID (e.g., "dolg", "killer", "csky")

#### Scenario: Resolve personality ID
- **WHEN** resolve_personality("bandit.3") is called
- **THEN** returns the personality text from bandit.TEXTS["3"]

#### Scenario: Resolve backstory ID  
- **WHEN** resolve_backstory("unique.wolf") is called
- **THEN** returns the backstory text from unique.TEXTS["wolf"]

#### Scenario: Resolve unique character backstory ID
- **GIVEN** a character with `backstory_id = "unique.esc_2_12_stalker_wolf"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_backstory("unique.esc_2_12_stalker_wolf")` is called
- **AND** returns the backstory text from texts/backstory/unique.py TEXTS["esc_2_12_stalker_wolf"]

#### Scenario: Resolve faction backstory ID
- **GIVEN** a character with `backstory_id = "loner.3"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_backstory("loner.3")` is called
- **AND** returns the backstory text from texts/backstory/loner.py TEXTS["3"]

#### Scenario: Invalid format returns empty string
- **WHEN** resolve_personality is called with text not matching "{faction}.{key}" format
- **THEN** returns empty string

#### Scenario: Resolve faction ID to display name
- **WHEN** resolve_faction_name("dolg") is called
- **THEN** returns "Duty"

#### Scenario: Resolve faction ID mercenary
- **WHEN** resolve_faction_name("killer") is called
- **THEN** returns "Mercenary"

#### Scenario: Resolve faction ID Clear Sky
- **WHEN** resolve_faction_name("csky") is called
- **THEN** returns "Clear Sky"

#### Scenario: Unknown faction ID returns ID itself
- **WHEN** resolve_faction_name("unknown_faction") is called
- **THEN** returns "unknown_faction"

#### Scenario: Resolve visual_faction (disguise) to display name
- **WHEN** character has visual_faction="dolg"
- **THEN** prompt displays "[disguised as Duty]"

#### Scenario: Reputation passed as integer to prompts
- **WHEN** reputation value 1500 is received from Lua
- **THEN** Character.reputation is stored as integer 1500
- **AND** prompt displays numeric value "Reputation: 1500"

#### Scenario: Negative reputation displayed numerically
- **WHEN** reputation value -2000 is received from Lua
- **THEN** prompt displays numeric value "Reputation: -2000"

### Dialogue Prompt Builder

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

### Query Current Scene JIT

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

### Include World Context Section

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

### Requirement: Disguise awareness instructions in dialogue prompt

The dialogue prompt builder SHALL detect when any recent event contains a disguised character (indicated by `[disguised as` in the rendered event text) and conditionally inject DISGUISE AWARENESS and DISGUISE NOTATION instructions into the prompt.

The injected instructions SHALL differentiate between companions (who knew about the disguise) and non-companions (who did not).

The injection SHALL appear after the `</EVENTS>` section and before the context use guidelines.

#### Scenario: Disguise instructions injected when disguise present (non-companion)
- **WHEN** `create_dialogue_request_prompt()` is called with events containing a character with `visual_faction` set
- **AND** the speaker is NOT a companion
- **THEN** the prompt SHALL include a `## DISGUISE CONTEXT` section
- **AND** the section SHALL instruct the LLM that the speaker did NOT know it was a disguise
- **AND** the section SHALL tell the LLM to treat the person by their apparent (disguised) faction

#### Scenario: Disguise instructions injected when disguise present (companion)
- **WHEN** `create_dialogue_request_prompt()` is called with events containing a disguised character
- **AND** `is_companion=True`
- **THEN** the prompt SHALL include a `## DISGUISE CONTEXT` section
- **AND** the section SHALL state the companion was aware of the disguise
- **AND** the section SHALL allow explicit references to the disguise in past tense

#### Scenario: No disguise instructions when no disguise present
- **WHEN** `create_dialogue_request_prompt()` is called with events that have no characters with `visual_faction`
- **THEN** the prompt SHALL NOT include a `## DISGUISE CONTEXT` section

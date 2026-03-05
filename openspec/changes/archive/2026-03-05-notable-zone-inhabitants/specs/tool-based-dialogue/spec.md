## MODIFIED Requirements

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

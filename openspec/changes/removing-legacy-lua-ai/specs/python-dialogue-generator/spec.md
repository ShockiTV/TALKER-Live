## REMOVED Requirements

### Requirement: Fallback considerations for Lua AI mode
**Reason**: Lua AI mode no longer exists - Python service is the only dialogue generation path
**Migration**: Remove any code or documentation that references fallback behavior

## MODIFIED Requirements

### Requirement: Dialogue Generator Service
The system MUST provide `DialogueGenerator` class as the sole dialogue generation path. There SHALL be no alternative or fallback dialogue generation mechanism.

The `DialogueGenerator` class MUST provide:
- `async generate(event, is_important)` method as main entry point
- Access to state query client for fetching Lua state
- Access to LLM client for AI completions
- Access to prompt builder for prompt construction
- Publisher for sending display commands

#### Scenario: All dialogue flows through Python service
- **WHEN** any dialogue-triggering event occurs
- **THEN** dialogue generation SHALL be handled exclusively by the Python DialogueGenerator
- **AND** no Lua-side AI processing SHALL occur

#### Scenario: Service unavailable during dialogue request
- **WHEN** a dialogue request cannot be fulfilled due to service issues
- **THEN** the request SHALL fail gracefully (no dialogue displayed)
- **AND** there SHALL be no fallback to Lua-based generation

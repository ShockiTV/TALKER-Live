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

### Requirement: Heartbeat Acknowledgement
The Python service SHALL acknowledge heartbeat messages from Lua to enable connection status tracking.

#### Scenario: Heartbeat received from Lua
- **WHEN** Python receives a `system.heartbeat` message
- **THEN** Python SHALL publish `service.heartbeat.ack` back to Lua
- **AND** the ack payload SHALL include `status: "alive"` and `timestamp`

### Requirement: LOG_HEARTBEAT Configuration
The Python service SHALL support a `LOG_HEARTBEAT` environment variable to control heartbeat logging verbosity.

#### Scenario: LOG_HEARTBEAT not set or false
- **WHEN** `LOG_HEARTBEAT` is not set or set to `false`
- **THEN** heartbeat messages SHALL NOT be logged (reduces log noise)
- **AND** this applies to router receive/publish logs and event handler logs

#### Scenario: LOG_HEARTBEAT set to true
- **WHEN** `LOG_HEARTBEAT=true` is set in `.env`
- **THEN** all heartbeat messages SHALL be logged at DEBUG level
- **AND** this enables debugging of connection issues

## ADDED Requirements

### Requirement: Python service is mandatory for AI dialogue
The system SHALL require the Python service to be running for AI dialogue generation. There SHALL be no fallback to Lua-based AI processing.

#### Scenario: Game loads without Python service
- **WHEN** the game loads and the Python service is not reachable
- **THEN** the system SHALL log a warning
- **AND** events SHALL continue to be stored locally
- **AND** no AI dialogue SHALL be generated

#### Scenario: First event with unavailable service
- **WHEN** the first dialogue-triggering event occurs with Python service unavailable
- **THEN** the system SHALL display a one-time HUD notification to the user
- **AND** subsequent events SHALL NOT display additional notifications

#### Scenario: Service becomes available after being unavailable
- **WHEN** the Python service becomes reachable after being unavailable
- **THEN** the system SHALL display a recovery HUD notification to the user
- **AND** dialogue generation SHALL resume for new events

#### Scenario: User attempts to trigger dialogue while offline
- **WHEN** the user triggers an event that would generate dialogue but service is offline
- **THEN** the system SHALL display an "offline" HUD notification (throttled to once per 10 seconds)
- **AND** the notification SHALL inform the user to start the Python service

### Requirement: Heartbeat acknowledgement for connection recovery
The Python service SHALL acknowledge heartbeats from Lua to enable connection recovery after game pause.

#### Scenario: Game unpauses after extended pause
- **WHEN** the game was paused (e.g., in menu) for longer than the timeout period
- **AND** the game resumes and sends a heartbeat
- **THEN** Python service SHALL respond with `service.heartbeat.ack`
- **AND** Lua SHALL restore connection status to connected
- **AND** connection recovery SHALL occur within one heartbeat cycle (5 seconds)

### Requirement: No legacy Lua AI code exists
The system SHALL NOT contain any Lua-based LLM client implementations or HTTP-based AI request code.

#### Scenario: AI directory is empty or removed
- **WHEN** the mod is installed
- **THEN** the `bin/lua/infra/AI/` directory SHALL NOT exist or SHALL be empty
- **AND** no references to legacy AI modules SHALL exist in load checks

### Requirement: MCM does not expose AI toggle options
The system SHALL NOT expose MCM options for enabling/disabling Python AI or ZMQ functionality. The mod is always fully enabled when installed.

#### Scenario: User opens MCM settings
- **WHEN** the user opens TALKER Expanded MCM settings
- **THEN** there SHALL be no "Enable Python AI" toggle
- **AND** there SHALL be no "Enable ZMQ" toggle

### Requirement: Config getters removed or hardcoded
The configuration layer SHALL NOT provide dynamic getters for `python_ai_enabled` or `zmq_enabled` that return user-configurable values.

#### Scenario: Code checks if Python AI is enabled
- **WHEN** any code path checks if Python AI is enabled
- **THEN** the check SHALL always return true (or the check SHALL be removed)

#### Scenario: Code checks if ZMQ is enabled  
- **WHEN** any code path checks if ZMQ is enabled
- **THEN** the check SHALL always return true (or the check SHALL be removed)

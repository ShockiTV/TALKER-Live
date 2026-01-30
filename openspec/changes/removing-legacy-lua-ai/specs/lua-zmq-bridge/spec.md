## REMOVED Requirements

### Requirement: Optional initialization based on config
**Reason**: ZMQ is now always required - there is no fallback path
**Migration**: Remove all conditional checks for `config.zmq_enabled()` - ZMQ always initializes

### Requirement: Graceful fallback when ZMQ disabled
**Reason**: No fallback behavior exists anymore - Python service is mandatory
**Migration**: Remove fallback code paths, ZMQ failure is now a hard error (with user notification)

## MODIFIED Requirements

### Requirement: Bridge Module
The bridge module MUST initialize unconditionally when the mod loads. There SHALL be no configuration toggle to disable ZMQ communication.

The existing bridge module MUST be extended with:
- SUB socket connecting to Python PUB on port 5556
- `poll_commands()` function for non-blocking receive
- Command handler registration
- Dual-socket lifecycle management
- Connection status tracking for user notifications

#### Scenario: Bridge initializes on mod load
- **WHEN** the mod loads
- **THEN** ZMQ bridge SHALL initialize automatically
- **AND** initialization SHALL NOT depend on any MCM toggle

#### Scenario: Bridge tracks connection status
- **WHEN** the bridge detects Python service is unreachable
- **THEN** the connection status SHALL be set to disconnected
- **AND** the status SHALL be queryable by other modules

#### Scenario: Bridge detects service recovery
- **WHEN** the bridge successfully communicates after being disconnected
- **THEN** the connection status SHALL be set to connected
- **AND** recovery notification logic SHALL be triggered

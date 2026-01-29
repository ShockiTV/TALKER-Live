## ADDED Requirements

### Requirement: ZMQ context initialization
The bridge SHALL initialize a ZeroMQ context and PUB socket on first use (lazy initialization).

#### Scenario: First publish triggers initialization
- **WHEN** `bridge.publish()` is called for the first time
- **THEN** the bridge initializes ZMQ context and binds PUB socket to configured endpoint

#### Scenario: Subsequent publishes reuse connection
- **WHEN** `bridge.publish()` is called after initialization
- **THEN** the bridge reuses the existing ZMQ context and socket

### Requirement: PUB socket binding
The bridge SHALL bind a PUB socket to `tcp://*:5555` by default, with port configurable via MCM.

#### Scenario: Default port binding
- **WHEN** bridge initializes without custom configuration
- **THEN** PUB socket binds to `tcp://*:5555`

#### Scenario: Custom port binding
- **WHEN** MCM setting `zmq_port` is set to 5560
- **THEN** PUB socket binds to `tcp://*:5560`

### Requirement: Message publishing
The bridge SHALL provide a `publish(topic, payload)` function that sends messages in ZMQ PUB format.

#### Scenario: Publish message with topic
- **WHEN** `bridge.publish("game.event", {type="DEATH"})` is called
- **THEN** the bridge sends `game.event {"type":"DEATH"}` on the PUB socket

#### Scenario: Payload JSON encoding
- **WHEN** payload contains nested tables
- **THEN** the bridge JSON-encodes the payload before sending

### Requirement: Graceful error handling
The bridge SHALL handle initialization failures gracefully without crashing the game.

#### Scenario: ZMQ library unavailable
- **WHEN** lzmq FFI binding fails to load
- **THEN** the bridge logs a warning and sets `is_available = false`
- **THEN** subsequent publish calls return `false` without error

#### Scenario: Port already in use
- **WHEN** socket bind fails due to port conflict
- **THEN** the bridge logs an error and sets `is_available = false`
- **THEN** subsequent publish calls return `false` without error

#### Scenario: Publish when unavailable
- **WHEN** `bridge.publish()` is called and `is_available = false`
- **THEN** the function returns `false` immediately without attempting to send

### Requirement: Connection status check
The bridge SHALL provide an `is_connected()` function to check ZMQ availability.

#### Scenario: Check when connected
- **WHEN** `bridge.is_connected()` is called after successful initialization
- **THEN** the function returns `true`

#### Scenario: Check when unavailable
- **WHEN** `bridge.is_connected()` is called after initialization failure
- **THEN** the function returns `false`

### Requirement: Shutdown cleanup
The bridge SHALL provide a `shutdown()` function to close ZMQ resources.

#### Scenario: Clean shutdown
- **WHEN** `bridge.shutdown()` is called
- **THEN** the PUB socket is closed
- **THEN** the ZMQ context is terminated
- **THEN** `is_available` is set to `false`

# ws-client

## Purpose

Thin pollnet WebSocket connection wrapper providing `open`, `send`, `poll`, `status`, and `close` operations. Injectable socket abstraction for testability.

## Requirements

### Requirement: Open a WebSocket connection

`ws_client.open(url)` SHALL initiate a WebSocket connection to `url` using `pollnet_open_ws` and return a connection handle. The client SHALL NOT block waiting for the handshake to complete.

#### Scenario: Open returns a handle immediately

- **WHEN** `ws_client.open("ws://localhost:5557/ws?token=abc")` is called
- **THEN** a non-nil connection handle is returned
- **AND** the connection state is `CONNECTING` until the handshake completes

#### Scenario: Open with invalid URL

- **WHEN** `ws_client.open("")` is called with an empty URL
- **THEN** the function returns nil
- **AND** logs an error

### Requirement: Send a message

`ws_client.send(handle, message)` SHALL write `message` (string) to the WS connection identified by `handle`. It SHALL return `true` on success and `false` if the handle is invalid or the socket is not connected.

#### Scenario: Send succeeds on open connection

- **WHEN** `ws_client.send(handle, '{"t":"game.event","p":{}}')` is called on a connected handle
- **THEN** the function returns `true`

#### Scenario: Send fails on closed handle

- **WHEN** `ws_client.send(nil, "msg")` is called
- **THEN** the function returns `false` without error

### Requirement: Poll for incoming message

`ws_client.poll(handle)` SHALL call `pollnet_update(handle)` and return the next available message string, or `nil` if no message is ready. Each call returns at most one message.

#### Scenario: Poll returns message when available

- **WHEN** the server sends a JSON message
- **AND** `ws_client.poll(handle)` is called
- **THEN** the raw message string is returned

#### Scenario: Poll returns nil when no message available

- **WHEN** no message is pending
- **AND** `ws_client.poll(handle)` is called
- **THEN** `nil` is returned

### Requirement: Query connection status

`ws_client.status(handle)` SHALL return one of the string values `"connected"`, `"connecting"`, `"closed"`, or `"error"` reflecting the current state of the connection.

#### Scenario: Status is connected after handshake

- **WHEN** the WebSocket handshake completes
- **AND** `ws_client.status(handle)` is called
- **THEN** `"connected"` is returned

#### Scenario: Status after close

- **WHEN** the remote side closes the connection
- **AND** `ws_client.status(handle)` is called
- **THEN** `"closed"` is returned

### Requirement: Close the connection

`ws_client.close(handle)` SHALL close the WebSocket connection gracefully and free the handle. Subsequent calls on the same handle SHALL be no-ops.

#### Scenario: Close terminates the connection

- **WHEN** `ws_client.close(handle)` is called
- **THEN** the underlying pollnet socket is closed
- **AND** `ws_client.status(handle)` returns `"closed"`

### Requirement: Mockable socket interface

`ws_client` SHALL accept an optional socket factory injection point so tests can substitute a mock socket without pollnet. When the factory is not provided, `pollnet_open_ws` is used.

#### Scenario: Injected mock socket used in tests

- **WHEN** a test injects `ws_client.set_socket_factory(mock_factory)`
- **THEN** subsequent `ws_client.open()` calls use `mock_factory` instead of `pollnet_open_ws`
- **AND** no pollnet FFI calls are made

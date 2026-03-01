# bridge-remote-config

## Purpose

The bridge reads its upstream talker_service URL from MCM configuration (received via `config.sync`) instead of a hardcoded constant, enabling remote VPS connections with `wss://` and token auth. Falls back to an environment variable for standalone operation.

## Requirements

### Requirement: Bridge extracts service_url from config.sync

When the bridge receives a `config.sync` message from the game, it SHALL read the `service_url` field from the payload. If `service_url` is present and differs from the current upstream URL, the bridge SHALL close the current service connection and reconnect to the new URL. The `ws_token` field, if non-empty, SHALL be appended as `?token=<value>` to the URL (unless a `?token=` is already present in the URL).

#### Scenario: config.sync provides remote URL with token

- **WHEN** `config.sync` payload contains `{"service_url": "wss://talker.example.com/ws", "ws_token": "abc123"}`
- **THEN** the bridge connects to `wss://talker.example.com/ws?token=abc123`

#### Scenario: config.sync provides URL without token

- **WHEN** `config.sync` payload contains `{"service_url": "ws://192.168.1.50:5557/ws"}` and `ws_token` is empty
- **THEN** the bridge connects to `ws://192.168.1.50:5557/ws`

#### Scenario: config.sync with same URL does not trigger reconnect

- **WHEN** `config.sync` arrives with `service_url` matching the current upstream URL
- **THEN** the bridge does NOT close or reconnect

#### Scenario: config.sync still proxied to service

- **WHEN** `config.sync` arrives
- **THEN** the message is forwarded to the upstream service (unchanged) in addition to being inspected by the bridge

### Requirement: Bridge handles config.update for service_url and ws_token

When the bridge receives a `config.update` message with `key` set to `service_url` or `ws_token`, it SHALL update the upstream URL and reconnect if the resolved URL has changed.

#### Scenario: config.update changes service_url mid-session

- **WHEN** `config.update` payload is `{"key": "service_url", "value": "wss://new-host.com/ws"}`
- **THEN** the bridge reconnects to the new URL (with current token appended if non-empty)

#### Scenario: config.update changes ws_token mid-session

- **WHEN** `config.update` payload is `{"key": "ws_token", "value": "newtoken"}`
- **THEN** the bridge reconnects to the current service_url with `?token=newtoken`

### Requirement: Environment variable fallback at startup

On startup (before any `config.sync`), the bridge SHALL read `SERVICE_WS_URL` from `os.environ`, defaulting to `wss://talker-live.duckdns.org/ws`. A subsequent `config.sync` from the game SHALL override this value.

#### Scenario: Env var overrides default at startup

- **WHEN** `SERVICE_WS_URL=wss://talker.example.com/ws?token=abc` is set
- **AND** no `config.sync` has been received
- **THEN** the bridge connects to `wss://talker.example.com/ws?token=abc`

#### Scenario: Default when no env var and no config.sync

- **WHEN** `SERVICE_WS_URL` is not set and no `config.sync` has arrived
- **THEN** the bridge connects to `wss://talker-live.duckdns.org/ws`

### Requirement: Log the resolved upstream URL at startup and on change

The bridge SHALL log the resolved upstream URL at INFO level when starting and when reconnecting due to a URL change. Token values SHALL be masked in the log (`token=***`).

#### Scenario: URL with token logged safely

- **WHEN** upstream URL is `wss://talker.example.com/ws?token=secret123`
- **THEN** the log shows `wss://talker.example.com/ws?token=***`

#### Scenario: URL without token logged as-is

- **WHEN** upstream URL is `ws://127.0.0.1:5557/ws`
- **THEN** the log shows `ws://127.0.0.1:5557/ws`

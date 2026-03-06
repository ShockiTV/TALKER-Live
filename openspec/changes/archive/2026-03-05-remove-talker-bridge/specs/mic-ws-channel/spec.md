# mic-ws-channel

## MODIFIED Requirements

### Requirement: Initialize and connect to mic service

`bridge_channel.init(url)` SHALL initialize with the service WS URL (not a bridge URL). `bridge_channel.tick()` drives the state machine identically to before. The default URL SHALL be `ws://127.0.0.1:5557/ws` (the `talker_service` endpoint).

#### Scenario: Init and tick connects to service
- **WHEN** `bridge_channel.init("ws://127.0.0.1:5557/ws")` is called
- **AND** `bridge_channel.tick()` is called
- **THEN** a WS connection to the service URL is opened

### Requirement: Publish to mic service

`bridge_channel.publish(topic, payload)` SHALL send a message directly to `talker_service` using the same envelope format. There is no intermediate bridge.

#### Scenario: Event published directly to service
- **WHEN** `bridge_channel.publish("game.event", {...})` is called in `CONNECTED` state
- **THEN** a properly encoded envelope is sent directly to `talker_service`

## REMOVED Requirements

### Requirement: Independent lifecycle from service channel

**Reason**: There is only one connection now (to `talker_service`). The separate mic channel / service channel distinction is obsolete — a single `bridge_channel` handles all traffic.
**Migration**: All code uses `bridge_channel` as the single connection to `talker_service`.

### Requirement: mic.stopped downstream topic

**Reason**: `mic.stopped` was sent by the bridge's AudioStreamer when VAD auto-stopped recording. With native DLL capture, VAD is handled in-process by the DLL — no WS topic needed. Lua detects VAD stop via `ta_poll()` returning the stop sentinel.
**Migration**: Remove `mic.stopped` topic handler registration. VAD stop is detected locally by the DLL polling loop.

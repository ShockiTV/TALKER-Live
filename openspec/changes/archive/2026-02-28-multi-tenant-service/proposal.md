## Why

The TALKER Python service currently assumes a single player with a single WebSocket connection on localhost. To host the service on a VPS for multiple players (reducing client-side compute, centralizing API keys, and sharing CPU-bound services like STT/TTS), the service must become session-aware — routing messages, config, state queries, and responses to the correct player while maintaining isolation.

## What Changes

- `WSRouter` gains session identity: each WebSocket connection maps to a `session_id` derived from the auth token. Handler signatures change from `(payload)` to `(payload, session_id)`.
- `publish()` gains a `session=` keyword argument for targeted sends (to one player's Bridge, not all connections).
- `ConfigMirror` becomes per-session, so each player can have independent MCM settings and LLM provider configuration.
- `StateQueryClient` routes queries to the correct player's game via session-scoped publish.
- `DialogueGenerator`, `SpeakerSelector`, and all event handlers thread `session_id` through the call chain.
- Invite-code auth extends the existing `TALKER_TOKENS` mechanism: token value maps to a stable `session_id` (the token name), enabling reconnection identity.
- A per-session player outbox buffers outbound messages when the player's Bridge is disconnected or suspended, draining on reconnect.

## Capabilities

### New Capabilities
- `session-aware-routing`: WSRouter tracks session identity per connection, dispatches messages with session context, and publishes to targeted sessions.
- `per-session-config`: ConfigMirror keyed by session_id so each player has independent settings and LLM client configuration.
- `player-outbox`: Per-session message buffer that holds outbound messages during disconnection/suspension and drains on reconnect with configurable TTL.

### Modified Capabilities
- `service-token-auth`: Token name becomes the session identity. Auth validation maps token → session_id on connect. Session lifecycle (connect/disconnect/reconnect) tracked.
- `python-state-query-client`: State queries route to the specific player's connection using session_id, not broadcast.
- `ws-api-contract`: Handler dispatch includes session context. No wire format changes — session identity comes from the connection, not the envelope.

## Impact

- **Python service (`talker_service/`)**: Major refactor of `WSRouter`, `ConfigMirror`, handler signatures, `DialogueGenerator`, `SpeakerSelector`, `StateQueryClient`, and event handlers. All existing ~156 tests will need updates to pass session_id.
- **No Lua/Bridge changes**: Session identity is established at WS connection time via the existing token query parameter. The Bridge (being built separately) simply connects with its token.
- **No wire protocol changes**: The JSON envelope `{t, p, r, ts}` remains unchanged. Session routing uses connection-level identity, not message-level fields.
- **Backward compatibility**: When `TALKER_TOKENS` is not configured (local dev mode), the service falls back to single-session behavior with a default session_id, preserving the current localhost workflow.

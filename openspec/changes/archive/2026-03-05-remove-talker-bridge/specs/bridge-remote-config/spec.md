# bridge-remote-config

## REMOVED Requirements

### Requirement: Bridge extracts service_url from config.sync

**Reason**: The bridge no longer exists. There is no intermediate process that needs to peek at `config.sync` to determine its upstream URL. Lua connects directly to `talker_service` using the MCM `service_url` value.
**Migration**: URL construction moved to `talker_ws_integration.script`'s `get_service_url()` function, which reads MCM values directly.

### Requirement: Bridge handles config.update for service_url and ws_token

**Reason**: No bridge to handle config updates. `config.update` messages for `service_url` and `ws_token` are sent to `talker_service` for its config mirror, but URL changes require Lua to reconnect (handled by Lua-side logic, not a bridge).
**Migration**: Lua-side reconnection logic in `talker_ws_integration.script` handles URL changes from MCM.

### Requirement: Environment variable fallback at startup

**Reason**: The bridge's `SERVICE_WS_URL` environment variable was for the bridge's own upstream connection. With no bridge, `talker_service` has its own env-based config via pydantic-settings, and Lua reads MCM directly.
**Migration**: No replacement needed. `talker_service` already has its own configuration via `config.py`.

### Requirement: Log the resolved upstream URL at startup and on change

**Reason**: This was bridge-specific logging. `talker_service` already logs its own bind address/port at startup. Lua-side connection logging is handled by `talker_ws_integration.script`.
**Migration**: No replacement needed.

## Why

The STT provider is never initialized because the lazy-init callback is registered on the global `ConfigMirror` singleton, but `config.sync` messages are routed to per-session mirrors created by `SessionRegistry`. Per-session mirrors have no callbacks, so the `_init_stt_on_config` callback never fires and `_stt_provider` stays `None` — causing every mic input to fail with "No STT provider available".

The same bug affects the TTS volume-boost callback (and any future global callback registered on `config_mirror`).

## What Changes

- Add a `on_any_config_change(callback)` method to `SessionRegistry` that registers "global" callbacks — callbacks that fire when *any* session's `ConfigMirror` is synced or updated
- When `SessionRegistry.get_config()` creates a new per-session mirror, automatically wire all registered global callbacks into that mirror's `on_change` list
- Change `__main__.py` to register the STT-init and TTS-volume callbacks on `session_registry.on_any_config_change()` instead of `config_mirror.on_change()`
- Add tests verifying that global callbacks fire on per-session config sync

## Capabilities

### New Capabilities
- `session-global-callbacks`: SessionRegistry propagation of shared-resource callbacks (STT init, TTS volume) to per-session ConfigMirror instances

### Modified Capabilities
- `per-session-config`: SessionRegistry gains `on_any_config_change()` method; new mirrors inherit global callbacks at creation time

## Impact

- `talker_service/src/talker_service/transport/session_registry.py` — new method + wiring in `get_config()`
- `talker_service/src/talker_service/__main__.py` — callback registration changes (2 lines)
- `talker_service/tests/` — new tests for callback propagation
- Fixes STT (mic input) for all users; fixes TTS volume sync; prevents same class of bug for future callbacks

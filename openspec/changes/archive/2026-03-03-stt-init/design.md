## Context

`SessionRegistry` provides per-session `ConfigMirror` instances so each connected player gets independent config. However, `__main__.py` registers "global" callbacks (STT provider initialization, TTS volume sync) on the module-level `config_mirror` singleton. When `config.sync` arrives, it routes through `_get_mirror(session_id)` which creates a *separate* per-session mirror with no callbacks — so the global callbacks never fire.

Current code paths:

```
__main__.py lifespan:
  config_mirror.on_change(_init_stt_on_config)    ← global singleton
  config_mirror.on_change(_on_tts_volume_change)  ← global singleton
  session_registry = SessionRegistry()
  config_handlers.set_session_registry(session_registry)

config.sync arrives (session="__default__"):
  _get_mirror("__default__")
    → session_registry.get_config("__default__")
    → NEW ConfigMirror()                           ← no callbacks!
    → .sync() fires on_change                      ← empty list
```

## Goals / Non-Goals

**Goals:**
- Ensure shared-resource callbacks (STT init, TTS volume) fire when any session's config is synced or updated
- Preserve per-session config isolation (each session still gets its own `ConfigMirror`)
- Make the pattern explicit and discoverable for future callbacks
- Zero changes to existing handlers, config routing, or wire protocol

**Non-Goals:**
- Per-session STT providers (one global provider is sufficient)
- Removing or replacing `SessionRegistry` or `ConfigMirror`
- Changing the lazy-init pattern for STT (callback-based is fine, just needs to fire)

## Decisions

### Decision 1: `on_any_config_change()` on SessionRegistry

**Choice**: Add `SessionRegistry.on_any_config_change(callback)` to store "global" callbacks. When `get_config()` creates a new per-session mirror, wire all stored callbacks into that mirror's `on_change` list.

**Why not register on each mirror manually?**: The registry creates mirrors lazily on first access. `__main__.py` registers callbacks during lifespan startup (before any WS client connects), so it doesn't know which session IDs will exist. The registry is the right place because it's the factory for mirrors.

**Why not use the global `config_mirror` as `__default__`?**: That would fix single-player but wouldn't extend to multi-session. Global callbacks need to fire from *any* session's config sync — the first player to connect should trigger STT init regardless of their session ID.

### Decision 2: Guard against duplicate callback firing

The existing `_stt_initialised` flag in `__main__.py` already prevents the STT provider from being created more than once. No additional guard needed — the pattern is already correct, it just needs to actually fire.

### Decision 3: Registration moves from `config_mirror` to `session_registry`

`__main__.py` will call `session_registry.on_any_config_change(cb)` instead of `config_mirror.on_change(cb)`. The global `config_mirror` singleton's `on_change` list will no longer be used for these callbacks. If no session registry is set (future edge case), the fallback to global mirror still has its own independent callbacks available.

## Risks / Trade-offs

- **[Risk] Callback fires multiple times from different sessions** → Mitigated: existing `_stt_initialised` flag guards STT init; TTS volume callback is idempotent (sets a float)
- **[Risk] Late callback registration after mirrors already created** → Not a concern: lifespan registers callbacks before any WS client connects, and `get_config()` hasn't been called yet
- **[Risk] Memory leak from callback references** → Negligible: 2-3 callbacks stored once at startup, mirrors created once per session

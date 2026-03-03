## 1. SessionRegistry: Add global callback support

- [x] 1.1 Add `_global_callbacks: list[Callable]` field and `on_any_config_change(callback)` method to `SessionRegistry`
- [x] 1.2 Update `get_config()` to wire all `_global_callbacks` into newly created `ConfigMirror` via `mirror.on_change(cb)`
- [x] 1.3 Add unit test: global callback fires when per-session mirror is synced
- [x] 1.4 Add unit test: global callback fires from multiple different sessions
- [x] 1.5 Add unit test: late session inherits global callbacks registered at startup

## 2. __main__.py: Switch callback registration

- [x] 2.1 Change `_init_stt_on_config` registration from `config_mirror.on_change()` to `session_registry.on_any_config_change()`
- [x] 2.2 Change TTS volume-boost callback registration from `config_mirror.on_change()` to `session_registry.on_any_config_change()`
- [x] 2.3 Verify `_stt_initialised` guard still prevents duplicate STT provider creation (existing, no code change expected)

## 3. Integration & E2E validation

- [x] 3.1 Run existing Python test suite to confirm no regressions
- [x] 3.2 Add integration test: config.sync triggers STT provider initialization via session registry

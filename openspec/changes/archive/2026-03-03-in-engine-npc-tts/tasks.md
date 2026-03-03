## 1. TTS engine injection

- [x] 1.1 Add `_tts_engine` global and `set_tts_engine(engine)` setter to `handlers/events.py`
- [x] 1.2 Call `event_handlers.set_tts_engine(tts_engine)` in `__main__.py` lifespan after TTS init

## 2. Dialogue dispatch with TTS

- [x] 2.1 Add `_dialogue_id` monotonic counter to `handlers/events.py`
- [x] 2.2 Extract voice_id from chosen speaker's `sound_prefix` in candidates list
- [x] 2.3 Implement conditional TTS-or-text dispatch: call `generate_audio()`, base64-encode OGG, publish `tts.audio` or fall back to `dialogue.display`
- [x] 2.4 Include `dialogue_id` in both `tts.audio` and `dialogue.display` payloads

## 3. Tests

- [x] 3.1 Unit test: `set_tts_engine()` injection and None default
- [x] 3.2 Unit test: voice_id resolved from candidates' sound_prefix (exact match, missing prefix, LLM-changed speaker)
- [x] 3.3 Unit test: TTS dispatch publishes `tts.audio` with correct payload when engine succeeds
- [x] 3.4 Unit test: fallback to `dialogue.display` when engine returns None or raises
- [x] 3.5 Unit test: fallback to `dialogue.display` when no TTS engine injected
- [x] 3.6 Unit test: monotonic dialogue_id increments across dispatches
- [x] 3.7 Run full Python test suite to confirm no regressions

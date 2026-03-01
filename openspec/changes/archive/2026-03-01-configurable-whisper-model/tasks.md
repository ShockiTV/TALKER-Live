## 1. Configuration

- [x] 1.1 Add `whisper_model: str = "base.en"` and `whisper_beam_size: int = 1` fields to `Settings` in `talker_service/src/talker_service/config.py`
- [x] 1.2 Add commented-out `WHISPER_MODEL` and `WHISPER_BEAM_SIZE` entries to `talker_service/.env`

## 2. Provider Integration

- [x] 2.1 Update `WhisperLocalProvider.__init__()` to accept optional `model_name` and `beam_size` params, defaulting to `settings.whisper_model` and `settings.whisper_beam_size`
- [x] 2.2 Store `beam_size` on the instance and pass it to `self._model.transcribe()` in the `transcribe()` method
- [x] 2.3 Update startup log messages to include model name and beam size

## 3. Verification

- [x] 3.1 Run existing Python tests to confirm no regressions

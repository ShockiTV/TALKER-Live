## Why

The local Whisper STT model is hardcoded to `base.en`. Deploying on a VPS with 4 cores / 16 GB RAM can benefit from `small.en` (better accuracy, acceptable latency), while other deployments may prefer `tiny.en` (fast, low RAM) or `distil-large-v3` (near-large accuracy). The model choice should be configurable via `.env`, following the same pattern used for `FORCE_PROXY_LLM` and other server-side overrides.

## What Changes

- Add `WHISPER_MODEL` env var to configure the faster-whisper model name (default: `base.en`)
- Add `WHISPER_BEAM_SIZE` env var to configure beam size for CPU speed tuning (default: `1` for faster greedy decoding)
- Read these settings in `config.py` via pydantic-settings
- Pass the configured model name into `WhisperLocalProvider` instead of the hardcoded `_DEFAULT_MODEL`
- Pass beam size into the `transcribe()` call
- Document the new vars in `.env` with commented-out examples

## Capabilities

### New Capabilities
- `configurable-whisper-model`: Env-var configuration for Whisper model name and beam size used by the local STT provider

### Modified Capabilities
- `service-whisper-transcription`: The local provider now reads model name and beam size from service config instead of hardcoded defaults

## Impact

- **Files**: `talker_service/.env`, `talker_service/src/talker_service/config.py`, `talker_service/src/talker_service/stt/whisper_local.py`, `talker_service/src/talker_service/stt/factory.py`
- **Behaviour**: Default behaviour unchanged (`base.en`, beam_size `1`). Only changes when user sets env vars.
- **Dependencies**: No new dependencies.

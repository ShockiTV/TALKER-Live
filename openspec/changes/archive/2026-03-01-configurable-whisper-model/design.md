## Context

The local Whisper STT provider (`WhisperLocalProvider`) currently hardcodes `base.en` as the model and uses the default `beam_size=5`. When deploying on a CPU-only VPS (e.g., 4 cores / 16 GB RAM), operators need the ability to select a model that balances accuracy vs latency for their hardware, and to tune beam size for CPU speed.

The service already has a `.env`-based config pattern via pydantic-settings (`Settings` in `config.py`). STT provider initialization happens in `__main__.py` via `_init_stt_on_config()`, which calls `get_stt_provider(stt_method)` and passes the result to the audio handler.

## Goals / Non-Goals

**Goals:**
- Make Whisper model name configurable via `WHISPER_MODEL` env var
- Make beam size configurable via `WHISPER_BEAM_SIZE` env var
- Preserve existing defaults so behaviour is unchanged without explicit config
- Log the chosen model and beam size at startup for diagnostics

**Non-Goals:**
- MCM configuration (this is a server-side deployment knob, not a per-player setting)
- Changing the default model from `base.en` (users opt-in to alternatives)
- Supporting non-faster-whisper engines (whisper.cpp, Vosk, etc.)
- GPU/CUDA compute type selection (always `int8` CPU for now)

## Decisions

### 1. Config via pydantic-settings, not constructor defaults

**Decision**: Add `whisper_model` and `whisper_beam_size` fields to `Settings` in `config.py`.

**Rationale**: Follows the existing pattern (see `force_proxy_llm`, `proxy_model`, etc.). pydantic-settings reads env vars automatically. No new machinery needed.

**Alternative considered**: Pass as kwargs through factory. Rejected because it would require threading config through `_init_stt_on_config` → factory → provider manually, when pydantic-settings already does this.

### 2. Read settings inside the provider, not the factory

**Decision**: `WhisperLocalProvider.__init__()` reads `settings.whisper_model` and `settings.whisper_beam_size` as defaults for its constructor params. Explicit constructor args still override.

**Rationale**: Keeps the factory thin (it already just does `WhisperLocalProvider(**kwargs)`). The provider is the only consumer of these settings. Tests can still inject values via constructor args.

### 3. Default beam_size=1 (greedy decoding)

**Decision**: Default `WHISPER_BEAM_SIZE=1` instead of faster-whisper's default of 5.

**Rationale**: ~30% faster on CPU with minimal quality loss for short utterances (player speech is typically 2-10 seconds). VPS operators who want higher accuracy can set `WHISPER_BEAM_SIZE=5`.

### 4. No validation of model name

**Decision**: Accept any string for `WHISPER_MODEL`. If it's invalid, faster-whisper will raise on load and the error will be logged by the existing exception handler in `_init_stt_on_config`.

**Rationale**: faster-whisper supports a wide range of model identifiers including HuggingFace repo IDs. Enumerating valid options would be fragile and quickly outdated.

## Risks / Trade-offs

- **Model download on first run**: faster-whisper auto-downloads models from HuggingFace. On a VPS, the first startup with `small.en` will download ~500MB. → Users should be aware; document in `.env` comments.
- **beam_size=1 default differs from upstream**: Users upgrading from manual configs expecting beam_size=5 might notice a slight quality change. → Mitigated by documenting the setting and the tradeoff.

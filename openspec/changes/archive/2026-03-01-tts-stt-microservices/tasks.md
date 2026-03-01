## Tasks

### 1. Create TTS HTTP service

**Files:** `tts_service/app.py`, `tts_service/Dockerfile`, `tts_service/requirements.txt`

- [x] Create `tts_service/app.py` — FastAPI app with:
  - `POST /generate` endpoint accepting `{text, voice_id, volume_boost}`, returning OGG bytes
  - `GET /health` endpoint returning model/voice status
  - Startup: load pocket_tts model + voice cache from `VOICES_DIR` env var (default `./voices`)
  - Extract audio generation logic from `TTSEngine._generate_audio_sync()` and `_pcm_to_ogg()`
  - Volume boost from request body (default 8.0)
  - Unknown voice_id → random fallback from cache
  - Empty text → 400
- [x] Create `tts_service/Dockerfile` — `FROM ghcr.io/kyutai-labs/pocket-tts:latest`, add fastapi + uvicorn + imageio-ffmpeg + numpy, expose 8100
- [x] Create `tts_service/requirements.txt` — fastapi, uvicorn, numpy, imageio-ffmpeg

### 2. Add remote TTS client to talker_service

**Files:** `talker_service/src/talker_service/tts/remote.py`, modify `talker_service/src/talker_service/tts/__init__.py`, modify `__main__.py`

- [x] Create `tts/remote.py` — `TTSRemoteClient` class with `async generate_audio(text, voice_id, volume_boost) -> tuple[bytes, int] | None`
  - Uses `httpx.AsyncClient` to POST to `TTS_SERVICE_URL/generate`
  - Timeout: 30s (matching `TTS_TIMEOUT_S`)
  - Error handling: log and return None (text-only fallback)
- [x] Modify `tts/__init__.py` to export `TTSRemoteClient`
- [x] Modify `__main__.py` TTS initialization: if `settings.tts_service_url` → use `TTSRemoteClient`, else use `TTSEngine` as today

### 3. Extend WhisperAPIProvider with base_url support

**Files:** `talker_service/src/talker_service/stt/whisper_api.py`

- [x] Add `endpoint` parameter to `WhisperAPIProvider.__init__()` (defaults to None → OpenAI cloud)
- [x] When `endpoint` is set, create `openai.OpenAI(base_url=endpoint, api_key="unused")` client
- [x] Use the client instance for `audio.transcriptions.create()` instead of the global `openai` module
- [x] Pass `stt_endpoint` from settings when constructing the provider in `__main__.py`

### 4. Add config settings

**Files:** `talker_service/src/talker_service/config.py`

- [x] Add `tts_service_url: str = ""` to `Settings`
- [x] Add `stt_endpoint: str = ""` to `Settings`

### 5. Add httpx dependency

**Files:** `talker_service/requirements.txt` (or `pyproject.toml`)

- [x] Add `httpx` to talker_service dependencies (used by remote TTS client)

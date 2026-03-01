## Context

TTS (pocket_tts) and STT (faster-whisper) are currently compiled into `talker_service` as Python imports. `TTSEngine` loads a ~500 MB model + N voice `.safetensors` files at startup. `WhisperLocalProvider` loads a faster-whisper model on first use. Both are CPU-heavy, single-threaded, and consume significant RAM.

The VPS deployment needs multiple `talker_service` instances (one per git branch). Duplicating these models per instance wastes RAM and prevents sharing.

TTS requires a custom wrapper (pocket_tts has no off-the-shelf Docker image). STT can use `fedirz/faster-whisper-server`, which exposes an OpenAI-compatible `/v1/audio/transcriptions` endpoint — and `talker_service` already has a `WhisperAPIProvider` that speaks this protocol.

## Goals / Non-Goals

**Goals:**
- TTS runs as a custom HTTP service, shareable across N talker_service instances
- STT uses the official `fedirz/faster-whisper-server` Docker image (no custom code)
- `talker_service` gains a remote TTS client gated by `TTS_SERVICE_URL` env var
- Existing `WhisperAPIProvider` is extended with `base_url` support to talk to local whisper server
- Local dev (Windows, no Docker) continues using embedded mode with zero config changes
- Voice files are loaded from a single mounted directory, shared across all callers

**Non-Goals:**
- GPU acceleration (staying CPU-only for now)
- Streaming TTS (current model is concat-then-encode; keeping that)
- Load balancing or horizontal scaling of TTS/STT (single instance each)
- Docker compose / Caddy / deployment config (that's `multi-branch-deploy`)

## Decisions

### 1. HTTP REST over internal gRPC or WS

TTS and STT are request/response calls — send input, get output. HTTP POST is the simplest protocol with the best tooling (curl, httpx, health checks). gRPC adds complexity for no benefit at this scale.

**Alternatives considered:**
- gRPC: Better for streaming, but we don't stream TTS. Adds protobuf tooling.
- WebSocket: Already used for game comms, but TTS/STT are stateless request/response. WS adds connection management overhead.

### 2. Official Docker image for STT, custom wrapper for TTS only

`fedirz/faster-whisper-server` provides an OpenAI-compatible `/v1/audio/transcriptions` endpoint out of the box. The existing `WhisperAPIProvider` already uses the `openai` Python client to call this endpoint format. Only a `base_url` parameter is needed.

**Alternatives considered:**
- Custom STT wrapper (original plan): ~100 lines of FastAPI wrapping `WhisperLocalProvider`. Unnecessary — the official image does the same thing with better maintenance.
- `onerahmet/openai-whisper-asr-webservice`: Another option but `fedirz/faster-whisper-server` is more actively maintained and specifically wraps faster-whisper.

TTS still needs a custom FastAPI wrapper (pocket_tts exposes a Python API, not an HTTP server), but the official `ghcr.io/kyutai-labs/pocket-tts` Docker image is used as the base — handling all native dependencies.

### 3. Binary response for TTS

`POST /generate` returns raw OGG bytes (`Content-Type: audio/ogg`). Avoids base64 overhead on potentially large audio payloads. The caller (`talker_service`) already handles OGG bytes internally.

### 4. Selection via env var, not config mirror

`TTS_SERVICE_URL` env var for TTS. When set, `TTSRemoteClient` is used. When unset (local dev), embedded `TTSEngine`. This is simpler than threading it through ConfigMirror, and it doesn't change at runtime.

For STT: set `STT_METHOD=api` + `STT_ENDPOINT=http://whisper:8200/v1` in the branch `.env`. The existing server-authority pin system ensures MCM can't override it.

### 5. Extend WhisperAPIProvider with base_url

The existing `WhisperAPIProvider` uses `openai.audio.transcriptions.create()` which calls `/v1/audio/transcriptions`. Currently it relies on the global `openai.api_key` config. The tweak: pass a custom `base_url` to the `openai.OpenAI()` client constructor when `stt_endpoint` is set, pointing it at the local faster-whisper-server.

### 6. Health endpoint on TTS service

`GET /health` returns `{"status": "ok", "model_loaded": true, "voices": 12}`. Used by Docker health checks. The faster-whisper-server image has its own health endpoint.

## Risks / Trade-offs

- **[Latency]** HTTP hop adds ~5-15ms per call → Negligible. TTS takes 2-10s, STT takes 1-5s. The hop is noise.
- **[Single point of failure]** If TTS/STT service crashes, all branches lose audio → Docker `restart: unless-stopped` + existing text-only fallback in talker_service.
- **[Memory isolation loss]** Previously each talker_service could configure different whisper models → Acceptable. All branches share one whisper model. If a branch needs a different model, it can use the cloud API provider instead.
- **[Port management]** Two more internal ports (8100, 8200) → Docker internal networking handles this. Not exposed externally.
- **[Third-party image]** `fedirz/faster-whisper-server` could break on update → Pin the image tag in docker-compose.

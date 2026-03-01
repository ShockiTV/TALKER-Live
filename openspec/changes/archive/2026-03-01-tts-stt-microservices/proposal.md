# Proposal: TTS & STT as Shared Microservices

## Problem

TTS (pocket_tts) and STT (faster-whisper) are currently embedded inside `talker_service`. Each service instance loads these heavy models (~1.5 GB TTS, ~0.5 GB STT). When running multiple branch instances on a VPS, duplicating these models per instance wastes RAM and prevents resource sharing.

## Solution

TTS becomes a custom shared HTTP microservice (pocket_tts has no off-the-shelf image). STT uses the official `fedirz/faster-whisper-server` Docker image, which exposes an OpenAI-compatible `/v1/audio/transcriptions` endpoint — the existing `WhisperAPIProvider` already speaks this protocol, needing only a `base_url` tweak.

### TTS Service (`tts-service`) — thin wrapper on official image

- Uses official `ghcr.io/kyutai-labs/pocket-tts` Docker image as base (handles all native deps)
- Thin FastAPI app wrapping the existing `TTSEngine` logic (~100 lines)
- Loads pocket_tts model + voice cache at startup from a mounted `voices/` directory
- Single endpoint: `POST /generate` — accepts `{text, voice_id, volume_boost}`, returns OGG audio bytes
- Runs as a single shared container on port 8100

### STT Service — official Docker image

- Uses `fedirz/faster-whisper-server` (OpenAI-compatible Whisper API)
- Exposes `POST /v1/audio/transcriptions` — same format as OpenAI Whisper API
- Runs as a single shared container on port 8200
- **No custom code needed** — talker_service's existing `WhisperAPIProvider` calls this endpoint

### Changes to `talker_service`

- Add `TTSRemoteClient` — HTTP client that calls `POST tts-service:8100/generate`
- Tweak `WhisperAPIProvider` — accept custom `base_url` parameter so it can point at the local faster-whisper-server instead of OpenAI's cloud API
- Add `stt_endpoint` config setting for the local whisper server URL
- Selection logic: if `TTS_SERVICE_URL` env var is set → use remote client, else use embedded `TTSEngine` (backward-compatible for local dev)
- STT: set `STT_METHOD=api` + `STT_ENDPOINT=http://whisper:8200/v1` in branch `.env` — no new provider needed

## Scope

- New: `tts_service/` directory with Dockerfile + FastAPI app
- Modified: `talker_service` TTS integration — add remote client option
- Modified: `WhisperAPIProvider` — accept custom `base_url` for local whisper server
- Modified: `talker_service/config.py` — add `tts_service_url` and `stt_endpoint` settings
- NOT in scope: Docker compose, Caddyfile, deployment — that's `multi-branch-deploy`

## Risks

- **Latency**: HTTP hop adds ~5-15ms per call. Negligible for TTS (seconds) and STT (seconds).
- **Availability**: If TTS/STT service crashes, all branches lose audio. Mitigated by Docker restart policy + existing text-only fallback in talker_service.
- **Backward compat**: Local dev on Windows still uses embedded mode (no Docker). The env vars are opt-in.
- **STT image updates**: `fedirz/faster-whisper-server` is third-party. Pin the image tag in compose to avoid surprise breaking changes.

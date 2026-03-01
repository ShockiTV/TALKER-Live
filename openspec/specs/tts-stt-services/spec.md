## Purpose

Standalone TTS and STT microservices: a TTS HTTP service wrapping pocket_tts for voice synthesis, and an STT service using faster-whisper-server for speech-to-text transcription.

## Requirements

### Requirement: TTS HTTP service
The system SHALL provide a standalone TTS HTTP service that loads pocket_tts and voice files, accepting text + voice_id and returning OGG audio.

#### Scenario: Generate audio for dialogue line
- **WHEN** a POST request is sent to `/generate` with `{"text": "Get out of here, stalker", "voice_id": "dolg_1", "volume_boost": 8.0}`
- **THEN** the service SHALL return OGG Vorbis audio bytes with `Content-Type: audio/ogg` and HTTP 200

#### Scenario: Unknown voice_id falls back to random voice
- **WHEN** a POST request is sent with a `voice_id` not in the voice cache
- **THEN** the service SHALL select a random loaded voice and return audio with a warning header

#### Scenario: Empty text returns 400
- **WHEN** a POST request is sent with empty or whitespace-only `text`
- **THEN** the service SHALL return HTTP 400 with `{"error": "text is required"}`

#### Scenario: Health check
- **WHEN** a GET request is sent to `/health`
- **THEN** the service SHALL return `{"status": "ok", "model_loaded": true, "voices": <count>}` with HTTP 200

### Requirement: STT via official faster-whisper-server Docker image
The system SHALL use the official `fedirz/faster-whisper-server` Docker image for shared STT, reusing the existing `WhisperAPIProvider` with a custom `base_url`.

#### Scenario: WhisperAPIProvider with custom base_url
- **WHEN** `stt_endpoint` is set to `http://whisper:8200/v1`
- **THEN** `WhisperAPIProvider` SHALL use that URL as the `base_url` for the openai client instead of the default OpenAI API

#### Scenario: STT_METHOD=api with local endpoint
- **WHEN** `STT_METHOD=api` and `STT_ENDPOINT=http://whisper:8200/v1` are set in `.env`
- **THEN** talker_service SHALL transcribe audio through the local faster-whisper-server container

#### Scenario: No stt_endpoint falls back to OpenAI cloud
- **WHEN** `stt_endpoint` is not set and `STT_METHOD=api`
- **THEN** `WhisperAPIProvider` SHALL call the default OpenAI Whisper API (backward-compatible)

### Requirement: Remote TTS client in talker_service
The system SHALL provide a `TTSRemoteClient` that calls the TTS HTTP service, used when `TTS_SERVICE_URL` is configured.

#### Scenario: TTS_SERVICE_URL set activates remote client
- **WHEN** `TTS_SERVICE_URL` env var is set (e.g., `http://tts-service:8100`)
- **THEN** talker_service SHALL use `TTSRemoteClient` instead of embedded `TTSEngine`

#### Scenario: TTS_SERVICE_URL unset uses embedded engine
- **WHEN** `TTS_SERVICE_URL` env var is not set
- **THEN** talker_service SHALL use the local `TTSEngine` (backward-compatible)

#### Scenario: Remote TTS failure falls back to text-only
- **WHEN** the TTS HTTP service returns an error or times out
- **THEN** talker_service SHALL log the error and publish dialogue without audio (text-only fallback)

### Requirement: Config settings for remote services
The system SHALL add `tts_service_url` and `stt_endpoint` to `Settings` in `config.py`.

#### Scenario: TTS URL read from environment
- **WHEN** `TTS_SERVICE_URL=http://tts-service:8100` is in the environment
- **THEN** `settings.tts_service_url` SHALL equal `"http://tts-service:8100"`

#### Scenario: STT endpoint read from environment
- **WHEN** `STT_ENDPOINT=http://whisper:8200/v1` is in the environment
- **THEN** `settings.stt_endpoint` SHALL equal `"http://whisper:8200/v1"`

#### Scenario: Settings default to empty
- **WHEN** no `TTS_SERVICE_URL` or `STT_ENDPOINT` is in the environment
- **THEN** both SHALL default to `""` (empty string, meaning embedded/cloud mode)

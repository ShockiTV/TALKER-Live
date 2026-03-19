# service-api-gateway

## Purpose

Caddy reverse proxy routes that expose VPS-hosted TTS, STT, and embedding services as JWT-authenticated HTTP APIs for remote consumption by local talker_service instances.

## Requirements

### Requirement: TTS API route with JWT gate

Caddy SHALL expose a route at `/api/tts/*` that requires a valid JWT with `player` role and proxies to the internal `tts-service:8100` container. The `/api/tts` prefix SHALL be stripped before proxying so that `/api/tts/generate` reaches `tts-service:8100/generate`.

#### Scenario: Authenticated TTS request proxied

- **WHEN** a POST request is sent to `/api/tts/generate` with a valid JWT Bearer token containing role `player`
- **THEN** Caddy SHALL strip the `/api/tts` prefix and proxy to `tts-service:8100/generate`
- **AND** the response from `tts-service` SHALL be returned to the client unchanged

#### Scenario: Unauthenticated TTS request rejected

- **WHEN** a POST request is sent to `/api/tts/generate` without a valid JWT
- **THEN** Caddy SHALL return HTTP 401
- **AND** the request SHALL NOT reach `tts-service`

#### Scenario: TTS health check accessible

- **WHEN** a GET request is sent to `/api/tts/health` with a valid JWT
- **THEN** Caddy SHALL proxy to `tts-service:8100/health` and return the response

### Requirement: STT API route with JWT gate

Caddy SHALL expose a route at `/api/stt/*` that requires a valid JWT with `player` role and proxies to the internal `stt-service:8200` container. The `/api/stt` prefix SHALL be stripped before proxying so that `/api/stt/v1/audio/transcriptions` reaches `stt-service:8200/v1/audio/transcriptions`.

#### Scenario: Authenticated STT transcription request proxied

- **WHEN** a POST request is sent to `/api/stt/v1/audio/transcriptions` with a valid JWT and multipart audio data
- **THEN** Caddy SHALL strip the `/api/stt` prefix and proxy to `stt-service:8200/v1/audio/transcriptions`
- **AND** the transcription response SHALL be returned to the client

#### Scenario: Unauthenticated STT request rejected

- **WHEN** a POST request is sent to `/api/stt/v1/audio/transcriptions` without a valid JWT
- **THEN** Caddy SHALL return HTTP 401

### Requirement: Embedding API route with endpoint whitelist

Caddy SHALL expose a route at `/api/embed/*` that requires a valid JWT with `player` role and proxies to the internal `ollama:11434` container. Only whitelisted Ollama endpoints SHALL be accessible; all others SHALL return HTTP 403.

The whitelisted paths (after prefix strip) SHALL be:
- `/api/embeddings` (POST — generate embeddings)
- `/api/tags` (GET — list available models)

#### Scenario: Authenticated embedding request proxied

- **WHEN** a POST request is sent to `/api/embed/api/embeddings` with a valid JWT
- **THEN** Caddy SHALL strip the `/api/embed` prefix and proxy to `ollama:11434/api/embeddings`
- **AND** the embedding response SHALL be returned to the client

#### Scenario: Authenticated tags request proxied

- **WHEN** a GET request is sent to `/api/embed/api/tags` with a valid JWT
- **THEN** Caddy SHALL strip the `/api/embed` prefix and proxy to `ollama:11434/api/tags`

#### Scenario: Non-whitelisted Ollama endpoint blocked

- **WHEN** a POST request is sent to `/api/embed/api/pull` with a valid JWT
- **THEN** Caddy SHALL return HTTP 403
- **AND** the request SHALL NOT reach `ollama`

#### Scenario: Non-whitelisted arbitrary path blocked

- **WHEN** a GET request is sent to `/api/embed/api/delete` with a valid JWT
- **THEN** Caddy SHALL return HTTP 403

### Requirement: Player identity header injection

For all API routes (`/api/tts/*`, `/api/stt/*`, `/api/embed/*`), Caddy SHALL extract the `sub` claim from the validated JWT and inject it as an `X-Player-ID` request header before proxying to the upstream service.

#### Scenario: X-Player-ID injected on TTS request

- **WHEN** a valid JWT with `sub: "player1"` is used to call `/api/tts/generate`
- **THEN** the proxied request to `tts-service` SHALL include header `X-Player-ID: player1`

#### Scenario: X-Player-ID injected on embed request

- **WHEN** a valid JWT with `sub: "player2"` is used to call `/api/embed/api/embeddings`
- **THEN** the proxied request to `ollama` SHALL include header `X-Player-ID: player2`

### Requirement: API request logging for future rate limiting

Caddy SHALL log all API route requests at INFO level, including the `X-Player-ID` (from JWT `sub` claim), the request path, and HTTP status code. This enables future per-user rate limiting and usage analytics.

#### Scenario: API request logged with player identity

- **WHEN** player "player1" sends a POST to `/api/tts/generate`
- **THEN** the Caddy access log SHALL include the player ID, path `/api/tts/generate`, and response status code

#### Scenario: Rejected request logged

- **WHEN** an unauthenticated request is sent to `/api/stt/v1/audio/transcriptions`
- **THEN** the Caddy access log SHALL include the path and 401 status code

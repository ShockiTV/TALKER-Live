## MODIFIED Requirements

### Requirement: Whisper transcription integration
The `talker_service` SHALL integrate a Speech-to-Text (STT) provider (e.g., Whisper local model or API) to transcribe the received audio buffer into text. The local Whisper provider SHALL use the model name and beam size from service configuration rather than hardcoded defaults.

#### Scenario: Successful transcription
- **WHEN** a complete audio buffer is finalized and processed by the STT provider
- **THEN** the service generates a text transcript of the audio

#### Scenario: Transcription uses configured model
- **WHEN** `WHISPER_MODEL` is set in the environment
- **THEN** the local STT provider uses the configured model for transcription

#### Scenario: Transcription uses configured beam size
- **WHEN** `WHISPER_BEAM_SIZE` is set in the environment
- **THEN** the local STT provider uses the configured beam size during decoding

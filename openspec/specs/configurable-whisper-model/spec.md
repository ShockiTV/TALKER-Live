# configurable-whisper-model

## Purpose

Defines the env-var configuration for Whisper model name, beam size, and force-local override used by the local STT provider in `talker_service`.

## Requirements

### Requirement: Configurable Whisper model name
The service SHALL read the `WHISPER_MODEL` environment variable to determine which faster-whisper model to load for local STT. If not set, it SHALL default to `base.en`.

#### Scenario: Custom model via env var
- **WHEN** `WHISPER_MODEL=small.en` is set in the `.env` file
- **THEN** `WhisperLocalProvider` loads the `small.en` faster-whisper model at startup

#### Scenario: Default model when unset
- **WHEN** `WHISPER_MODEL` is not set
- **THEN** `WhisperLocalProvider` loads `base.en`

#### Scenario: Invalid model name
- **WHEN** `WHISPER_MODEL` is set to an unrecognized value
- **THEN** faster-whisper raises an error during model load
- **AND** the error is logged by the STT initialization handler

### Requirement: Configurable beam size
The service SHALL read the `WHISPER_BEAM_SIZE` environment variable to set the beam search width used during transcription. If not set, it SHALL default to `1` (greedy decoding).

#### Scenario: Custom beam size
- **WHEN** `WHISPER_BEAM_SIZE=5` is set in the `.env` file
- **THEN** `WhisperLocalProvider.transcribe()` uses `beam_size=5`

#### Scenario: Default beam size
- **WHEN** `WHISPER_BEAM_SIZE` is not set
- **THEN** `WhisperLocalProvider.transcribe()` uses `beam_size=1`

### Requirement: Force local Whisper override
The service SHALL read the `FORCE_LOCAL_WHISPER` environment variable. When set to `true`, the service SHALL always use the local Whisper provider regardless of the `stt_method` received from MCM configuration.

#### Scenario: Force override active
- **WHEN** `FORCE_LOCAL_WHISPER=true` is set in the `.env` file
- **AND** MCM sends `stt_method=api`
- **THEN** the service ignores the MCM value and uses the local Whisper provider

#### Scenario: Force override inactive
- **WHEN** `FORCE_LOCAL_WHISPER` is not set or is `false`
- **THEN** the service uses whichever `stt_method` MCM provides (defaulting to `local`)

### Requirement: Startup logging
The service SHALL log the chosen Whisper model name and beam size when the local STT provider is initialized.

#### Scenario: Log on initialization
- **WHEN** `WhisperLocalProvider` is constructed
- **THEN** the log output includes the model name and beam size values

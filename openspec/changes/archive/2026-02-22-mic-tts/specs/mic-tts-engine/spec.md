## ADDED Requirements

### Requirement: TTS flag enables model loading
When mic_python is launched with `--tts`, the Pocket TTS model SHALL be loaded at startup and a voice cache SHALL be populated from all `.safetensors` files found in `mic_python/voices/`. Without `--tts`, no TTS model is loaded and startup behaviour is unchanged.

#### Scenario: Startup with --tts loads voice cache
- **WHEN** mic_python starts with `--tts` and `voices/dolg_1.safetensors` exists
- **THEN** mic_python logs "Loaded voice: dolg_1" and voice_cache contains key `"dolg_1"`

#### Scenario: Startup without --tts skips model
- **WHEN** mic_python starts without `--tts`
- **THEN** no TTSModel is instantiated and `tts.speak` messages are ignored

### Requirement: tts.speak triggers streamed audio playback
On receiving `tts.speak`, mic_python SHALL extract `voice_id` and `text` from the payload, look up the voice state in cache, open a sounddevice OutputStream at 24000 Hz, publish `tts.started`, stream audio chunks via `generate_audio_stream`, then publish `tts.done` after the last chunk.

#### Scenario: Known voice_id plays audio
- **WHEN** mic_python receives `tts.speak { "voice_id": "dolg_1", "text": "Stay sharp.", "speaker_id": "npc_wolf" }`
- **THEN** mic_python publishes `tts.started { "speaker_id": "npc_wolf" }`, plays audio to default output, then publishes `tts.done { "speaker_id": "npc_wolf" }`

#### Scenario: Unknown voice_id falls back to first available voice
- **WHEN** mic_python receives `tts.speak` with a `voice_id` not present in cache
- **THEN** mic_python logs a warning, uses the first available voice in cache, and proceeds with playback

#### Scenario: Empty voice cache falls back gracefully
- **WHEN** `--tts` is active but `voices/` has no `.safetensors` files
- **THEN** mic_python logs an error and publishes `tts.done` immediately without playback

### Requirement: Shared task queue serialises STT and TTS
mic_python SHALL maintain a single FIFO task queue. While a task (STT or TTS) is active, incoming `mic.start` and `tts.speak` messages SHALL be enqueued rather than processed immediately. Tasks are processed one at a time in arrival order.

#### Scenario: tts.speak during active STT is queued
- **WHEN** mic_python is in STT_ACTIVE state and receives `tts.speak`
- **THEN** the TTS task is appended to the queue and processed after the current STT task completes

#### Scenario: mic.start during active TTS is queued
- **WHEN** mic_python is in TTS_ACTIVE state and receives `mic.start`
- **THEN** the STT task is appended to the queue and processed after the current TTS task completes

#### Scenario: IDLE state processes next queued task immediately
- **WHEN** a task completes and the queue is non-empty
- **THEN** the next task is dequeued and started within one event loop iteration

### Requirement: Voice export script bakes reference audio to .safetensors
`export_voices.py` SHALL iterate voice theme directories in `mic_python/voices/`, locate the best reference audio file (supports Anomaly subfolder layout `<theme>/Anomaly/talk/...` and manual root overrides), skip themes whose `.safetensors` already exists, export each to `<stem>.safetensors` using `export_model_state`, and log each result. Optionally applies DeepFilterNet denoising via `--denoise` flag.

#### Scenario: New theme is exported
- **WHEN** `stalker_1/` contains reference audio and `stalker_1.safetensors` does not exist in the theme root
- **THEN** `export_voices.py` creates `stalker_1.safetensors` and logs the result

#### Scenario: Existing safetensors is skipped
- **WHEN** both reference audio and `stalker_1.safetensors` exist
- **THEN** `export_voices.py` logs "Skip (exists)" and does not overwrite it

#### Scenario: Manual root override
- **WHEN** a user places `stalker_1.ogg` directly in the `stalker_1/` theme root
- **THEN** `export_voices.py` uses that file as the reference audio instead of scanning subfolders

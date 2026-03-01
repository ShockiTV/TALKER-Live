## MODIFIED Requirements

### Requirement: Generate OGG Vorbis from dialogue text
When TTS is enabled and a voice is available for the speaker, the TTS module SHALL generate audio from the dialogue text using pocket_tts, peak-normalize the raw float32 24 kHz PCM to ±1.0 (skipping normalization if peak amplitude is below 1e-6), then pipe it through ffmpeg which resamples to 44100 Hz, applies volume boost (configurable via MCM `tts_volume_boost`, default 8.0), and encodes to OGG Vorbis in a single pass. Returns the OGG bytes.

#### Scenario: PCM is peak-normalized before encoding
- **WHEN** pocket_tts produces chunks with a peak amplitude of 0.05
- **THEN** the concatenated PCM buffer is divided by 0.05, resulting in a peak of 1.0
- **AND** the normalized buffer is then passed to ffmpeg with the configured volume boost

#### Scenario: Near-silent audio skips normalization
- **WHEN** pocket_tts produces chunks with a peak amplitude below 1e-6
- **THEN** normalization is skipped (no divide-by-zero)
- **AND** the raw buffer is passed to ffmpeg as-is

#### Scenario: Successful OGG generation
- **WHEN** `generate_audio("Stay sharp.", "dolg_1")` is called with a cached voice
- **THEN** the returned bytes are a valid OGG Vorbis file at 44100 Hz containing synthesized speech

#### Scenario: Unknown voice_id falls back
- **WHEN** `generate_audio("text", "unknown_voice")` is called
- **THEN** the first available voice in cache is used
- **AND** a warning is logged

#### Scenario: Empty text returns None
- **WHEN** `generate_audio("", "dolg_1")` is called
- **THEN** None is returned and no audio is generated

### Requirement: Volume boost configurable via MCM
The TTS volume boost SHALL be configurable via the MCM setting `tts_volume_boost` (range 1.0–15.0, default 8.0). The value is applied as an ffmpeg `-af volume=N` filter during OGG encoding after peak normalization. Changes are propagated at runtime via `config.sync` / `config.update` messages.

#### Scenario: Volume boost updated at runtime
- **WHEN** `config.update` with `key=tts_volume_boost, value=3.0` is received
- **THEN** subsequent TTS audio is encoded with `-af volume=3.0`

#### Scenario: MCM slider range
- **WHEN** the user opens the MCM settings for TALKER
- **THEN** the TTS volume boost slider has a minimum of 1.0, maximum of 15.0, step of 0.5, and default of 8.0

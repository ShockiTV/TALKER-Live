# voice-export-pipeline

## Purpose

Defines the tooling pipeline that bakes triaged source audio into `.safetensors` voice cache files for the talker_service TTS engine. Covers the phase3 export script and the phase1 modifications needed to support additional voice source directories.

## Requirements

### Requirement: phase3_export.py bakes safetensors from triaged audio
`tools/voice_triage/phase3_export.py` SHALL read one `.ogg` source file per theme from `voice_staging/raw/<theme>/` and produce `talker_service/voices/<theme>.safetensors` using pocket_tts. Themes with no source file are skipped with a warning.

#### Scenario: Bake all triaged themes
- **WHEN** `phase3_export.py` is run with no arguments
- **AND** `voice_staging/raw/` contains directories `dolg_1/`, `bandit_1/`, `csky_2/` each with one `.ogg` file
- **THEN** `talker_service/voices/dolg_1.safetensors`, `bandit_1.safetensors`, and `csky_2.safetensors` are created
- **AND** a summary is printed: "Baked 3 voices to talker_service/voices/"

#### Scenario: Bake a single theme with --only
- **WHEN** `phase3_export.py --only dolg_1` is run
- **THEN** only `talker_service/voices/dolg_1.safetensors` is created
- **AND** other themes are skipped

#### Scenario: Theme directory has no source audio
- **WHEN** `voice_staging/raw/empty_theme/` exists but contains no `.ogg` files
- **THEN** a warning is logged: "Skipping empty_theme: no source audio found"
- **AND** processing continues for other themes

#### Scenario: Output directory created automatically
- **WHEN** `talker_service/voices/` does not exist
- **THEN** it is created before baking begins

### Requirement: phase3_export.py uses pocket_tts create_voice_from_audio
The export script SHALL use `pocket_tts.create_voice_from_audio()` (or equivalent API) to convert source `.ogg` audio into a `.safetensors` voice cache. The script SHALL NOT depend on the talker_service runtime — it imports pocket_tts directly.

#### Scenario: pocket_tts not installed
- **WHEN** `phase3_export.py` is run and `import pocket_tts` fails
- **THEN** an error is printed: "pocket_tts is required for voice export" and exits with code 1

### Requirement: phase1_triage.py supports --source-dir override
`tools/voice_triage/phase1_triage.py` SHALL accept an optional `--source-dir` argument that overrides the default `SOURCE_DIR` constant. This allows triaging voices from mod directories (e.g., Dux Characters Kit) in addition to the base Anomaly unpacked directory.

#### Scenario: Triage from Dux mod directory
- **WHEN** `phase1_triage.py --source-dir "F:\GAMMA\mods\305- Dux Characters Kit...\gamedata\sounds\characters_voice\human"` is run
- **THEN** voice themes are discovered from the specified directory instead of the default Anomaly path

#### Scenario: Default source directory unchanged
- **WHEN** `phase1_triage.py` is run with no `--source-dir` argument
- **THEN** the default `SOURCE_DIR` (Anomaly unpacked) is used as before

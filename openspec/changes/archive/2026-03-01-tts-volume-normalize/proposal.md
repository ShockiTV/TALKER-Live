## Why

pocket_tts produces low-amplitude waveforms that vary across voices and phrases. The current fixed volume multiplier (MCM range 1.0–5.0, default 4.0) is insufficient — audio is still too quiet in-game at max setting. Additionally, the linear boost amplifies inconsistency: some lines clip while others remain inaudible.

## What Changes

- Peak-normalize raw PCM audio to -1.0..1.0 before the ffmpeg volume boost, ensuring consistent base amplitude across all voices and phrases
- Raise the MCM slider ceiling from 5.0 to 15.0 to provide more headroom
- Raise the default volume boost from 4.0 to 8.0 to match the louder baseline after normalization
- Update all config defaults and Python model to match

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `service-tts-generation`: Volume boost range changes from 1.0–5.0 to 1.0–15.0, default from 4.0 to 8.0. PCM audio is peak-normalized before the ffmpeg volume filter.

## Impact

- **Python**: `talker_service/src/talker_service/tts/engine.py` — add normalization step, update default constant
- **Python**: `talker_service/src/talker_service/models/config.py` — update default and range comment
- **Lua**: `gamedata/scripts/talker_mcm.script` — update slider max and default
- **Lua**: `bin/lua/interface/config_defaults.lua` — update default
- No API or wire protocol changes. Existing MCM values < 5.0 remain valid.

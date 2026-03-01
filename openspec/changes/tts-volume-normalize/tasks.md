## 1. Peak normalization in TTS engine

- [ ] 1.1 In `talker_service/src/talker_service/tts/engine.py` `_generate_audio_sync()`: after `np.concatenate(chunks)`, add peak normalization — compute `peak = np.max(np.abs(raw_audio))`, if peak > 1e-6 then `raw_audio = raw_audio / peak`, log the peak value
- [ ] 1.2 Update `DEFAULT_VOLUME_BOOST` constant from 4.0 to 8.0 and update the comment

## 2. MCM slider range and defaults

- [ ] 2.1 In `gamedata/scripts/talker_mcm.script`: change `tts_volume_boost` slider `max` from 5.0 to 15.0, `step` from 0.1 to 0.5, `def` from 4.0 to 8.0
- [ ] 2.2 In `bin/lua/interface/config_defaults.lua`: change `tts_volume_boost` default from 4.0 to 8.0
- [ ] 2.3 In `bin/lua/interface/config.lua`: change fallback default in `tts_volume_boost()` getter from 4.0 to 8.0

## 3. Python config model

- [ ] 3.1 In `talker_service/src/talker_service/models/config.py`: update `tts_volume_boost` default from 4.0 to 8.0 and range comment from 1.0-5.0 to 1.0-15.0

## 4. Run tests

- [ ] 4.1 Run Python tests to verify no regressions
- [ ] 4.2 Run Lua tests to verify no regressions

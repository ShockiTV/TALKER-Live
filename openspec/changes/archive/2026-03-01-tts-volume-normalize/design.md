## Context

pocket_tts produces float32 PCM waveforms whose peak amplitude varies significantly across voices and input text. The current pipeline applies a fixed linear volume multiplier (default 4.0×, user-configurable 1.0–5.0×) via ffmpeg's `volume` filter. In practice, the output is still too quiet in-game even at max setting, and different voices/phrases have inconsistent loudness.

## Goals / Non-Goals

**Goals:**
- Make TTS audio consistently loud enough to hear in-game without cranking the slider to max
- Remove voice-to-voice and phrase-to-phrase volume inconsistency
- Preserve user control over final volume level via the MCM slider

**Non-Goals:**
- Full loudness normalization (LUFS-based) — overkill for this use case
- Changing the X-Ray OGG metadata (tested, no audible difference)
- Modifying the Lua playback path (play_no_feedback parameters are fine)

## Decisions

**Peak normalization before ffmpeg boost**: After concatenating all pocket_tts chunks into a single float32 buffer, divide by `max(abs(signal))` to normalize the peak to ±1.0. This makes the volume slider predictable — it's now "how loud relative to full scale" rather than "how much do we multiply an unknown quiet signal." The normalization is two vectorized numpy ops on a ~300–750 KB array (~0.1–0.3 ms), negligible vs. the 2–10 s TTS generation time.

**Guard against silent/near-silent audio**: Skip normalization if peak amplitude is below 1e-6 to avoid divide-by-zero or amplifying pure noise.

**Raise MCM ceiling to 15.0, default to 8.0**: Post-normalization, the signal is at full scale. A 4.0× multiplier was barely audible on raw pocket_tts output but would be very loud on normalized audio. However, X-Ray engine 3D attenuation and in-game ambience require significant headroom. Default of 8.0 provides a good starting point; ceiling of 15.0 gives users room to adjust for their setup.

## Risks / Trade-offs

- **Clipping**: Normalized audio boosted by 8.0–15.0× will hard-clip. This is intentional — pocket_tts output quality doesn't benefit from dynamic range preservation, and X-Ray engine applies its own distance attenuation that absorbs much of the boost. Users who find it too loud can lower the slider.
- **Existing user settings**: Users who set `tts_volume_boost` to e.g. 3.0 will hear louder audio after this change (normalization makes the base louder). The new default will be written on first load, so explicit user values are preserved. Documenting the change in CHANGELOG is sufficient.

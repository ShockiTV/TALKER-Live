"""Local Whisper transcription using faster-whisper.

Accepts raw PCM audio bytes (16kHz mono int16), writes them to a temporary
WAV file, and runs faster-whisper for local transcription.

Includes hallucination filtering — Whisper is prone to generating phantom
text (e.g. "You", "Thank you") when fed silence or very short audio.
"""

from __future__ import annotations

import os
import struct
import tempfile
import wave

from loguru import logger

from faster_whisper import WhisperModel

from ..config import settings

# Minimum audio duration in seconds — anything shorter is almost certainly
# a click / key-up artefact, not real speech.
_MIN_AUDIO_SECONDS = 0.6

# Segments with no_speech_prob above this threshold are discarded.
_NO_SPEECH_THRESHOLD = 0.6

# Known Whisper hallucination strings (lowercased, stripped).
# These appear when the model is fed silence / noise and tries to produce
# *something*.  Extend this set as new phantoms are discovered.
_HALLUCINATIONS: frozenset[str] = frozenset(
    s.lower()
    for s in (
        "you",
        "thank you",
        "thanks for watching",
        "thanks for listening",
        "thank you for watching",
        "thank you for listening",
        "bye",
        "the end",
        "subtitle",
        "subtitles",
        "subtitles by",
        "subscriptions",
        "subscribe",
    )
)


class WhisperLocalProvider:
    """Transcribe audio locally using faster-whisper."""

    def __init__(
        self,
        model_name: str | None = None,
        beam_size: int | None = None,
    ) -> None:
        model_name = model_name or settings.whisper_model
        self._beam_size = beam_size if beam_size is not None else settings.whisper_beam_size
        logger.info(
            "Loading faster-whisper model '{}' (beam_size={})...",
            model_name,
            self._beam_size,
        )
        self._model = WhisperModel(model_name, compute_type="int8", device="cpu")
        logger.info("faster-whisper model '{}' ready (beam_size={})", model_name, self._beam_size)

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        prompt: str = "",
        language: str = "en",
    ) -> str:
        """Transcribe raw PCM int16 mono 16 kHz audio bytes."""
        if not audio_bytes:
            return ""

        # --- Duration gate ---------------------------------------------------
        duration = len(audio_bytes) / (16000 * 2)  # 16 kHz, int16 = 2 bytes
        if duration < _MIN_AUDIO_SECONDS:
            logger.debug(
                "Audio too short ({:.2f}s < {:.2f}s) — skipping transcription",
                duration,
                _MIN_AUDIO_SECONDS,
            )
            return ""

        # --- RMS energy gate --------------------------------------------------
        rms = _rms_energy(audio_bytes)
        if rms < 300:
            logger.debug("Audio RMS energy too low ({:.0f}) — skipping", rms)
            return ""

        # Write raw PCM to a temporary WAV so faster-whisper can read it
        wav_path = self._pcm_to_wav(audio_bytes)

        try:
            segments, _info = self._model.transcribe(
                wav_path,
                language=language if language else None,
                initial_prompt=prompt if prompt else None,
                vad_filter=True,
                beam_size=self._beam_size,
            )

            # Collect only segments that the model is confident contain speech
            parts: list[str] = []
            for seg in segments:
                if seg.no_speech_prob > _NO_SPEECH_THRESHOLD:
                    logger.debug(
                        "Dropping segment (no_speech_prob={:.2f}): '{}'",
                        seg.no_speech_prob,
                        seg.text.strip(),
                    )
                    continue
                parts.append(seg.text)

            text = "".join(parts).strip()

            # --- Hallucination filter -----------------------------------------
            if text.lower() in _HALLUCINATIONS:
                logger.info(
                    "Whisper hallucination filtered: '{}' (duration={:.2f}s)",
                    text,
                    duration,
                )
                return ""

            logger.info("Whisper local transcription: '{}'", text)
            return text
        except Exception:
            logger.opt(exception=True).error("Whisper local transcription failed")
            return ""
        finally:
            # Clean up the temp WAV file
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    @staticmethod
    def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """Write raw PCM int16 mono bytes to a temporary WAV file.

        Returns the path to the temporary file.
        """
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return tmp.name


def _rms_energy(pcm_bytes: bytes) -> float:
    """Compute RMS energy of int16 PCM audio."""
    n_samples = len(pcm_bytes) // 2
    if n_samples == 0:
        return 0.0
    samples = struct.unpack(f"<{n_samples}h", pcm_bytes[: n_samples * 2])
    mean_sq = sum(s * s for s in samples) / n_samples
    return mean_sq ** 0.5

"""Local Whisper transcription using faster-whisper.

Accepts raw PCM audio bytes (16kHz mono int16), writes them to a temporary
WAV file, and runs faster-whisper for local transcription.
"""

from __future__ import annotations

import io
import tempfile
import wave

from loguru import logger

from faster_whisper import WhisperModel

# Default model — small footprint, English-only
_DEFAULT_MODEL = "base.en"


class WhisperLocalProvider:
    """Transcribe audio locally using faster-whisper."""

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        logger.info("Loading faster-whisper model '{}'...", model_name)
        self._model = WhisperModel(model_name, compute_type="int8", device="cpu")
        logger.info("faster-whisper model '{}' loaded", model_name)

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

        # Write raw PCM to a temporary WAV so faster-whisper can read it
        wav_path = self._pcm_to_wav(audio_bytes)

        try:
            segments, _info = self._model.transcribe(
                wav_path,
                language=language if language else None,
                initial_prompt=prompt if prompt else None,
            )
            text = "".join(seg.text for seg in segments).strip()
            logger.info("Whisper local transcription: '{}'", text)
            return text
        except Exception:
            logger.opt(exception=True).error("Whisper local transcription failed")
            return ""

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

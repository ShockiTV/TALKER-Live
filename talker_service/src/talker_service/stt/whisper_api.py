"""OpenAI Whisper API transcription provider.

Accepts raw PCM audio bytes (16kHz mono int16), writes them to a temporary
WAV file, and sends to the OpenAI Whisper API for transcription.
"""

from __future__ import annotations

import os
import tempfile
import wave

from loguru import logger

import openai


class WhisperAPIProvider:
    """Transcribe audio using the OpenAI Whisper API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self._api_key:
            logger.warning("No OpenAI API key set — Whisper API transcription will fail")
        else:
            openai.api_key = self._api_key
            logger.info("Whisper API provider initialized")

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        prompt: str = "",
        language: str = "en",
    ) -> str:
        """Transcribe raw PCM int16 mono 16 kHz audio bytes via OpenAI API."""
        if not audio_bytes:
            return ""

        wav_path = self._pcm_to_wav(audio_bytes)

        try:
            with open(wav_path, "rb") as audio_file:
                transcript = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    prompt=prompt if prompt else None,
                    language=language if language else None,
                )
            text = transcript.text.strip()
            logger.info("Whisper API transcription: '{}'", text)
            return text
        except Exception:
            logger.opt(exception=True).error("Whisper API transcription failed")
            return ""

    @staticmethod
    def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """Write raw PCM int16 mono bytes to a temporary WAV file."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return tmp.name

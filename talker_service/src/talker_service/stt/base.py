"""STT provider protocol and base class."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class STTProvider(Protocol):
    """Protocol for speech-to-text providers.

    All providers accept raw PCM audio bytes (16kHz mono int16)
    and return the transcribed text as a string.
    """

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        prompt: str = "",
        language: str = "en",
    ) -> str:
        """Transcribe raw PCM audio bytes to text.

        Args:
            audio_bytes: Raw 16kHz mono int16 PCM audio data.
            prompt: Optional context hint for the transcription model.
            language: ISO 639-1 language code (default ``"en"``).

        Returns:
            Transcribed text string (may be empty on failure).
        """
        ...

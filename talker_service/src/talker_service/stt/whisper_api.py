"""OpenAI Whisper API transcription provider.

Accepts raw PCM audio bytes (16kHz mono int16), writes them to a temporary
WAV file, and sends to the OpenAI Whisper API for transcription.

When ``endpoint`` is set (e.g. ``http://whisper:8200/v1``), the provider
targets a local faster-whisper-server container instead of OpenAI's cloud.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import wave

from loguru import logger

import openai
import httpx


class WhisperAPIProvider:
    """Transcribe audio using the OpenAI Whisper API (or compatible endpoint)."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._endpoint = endpoint or ""
        self._http_client = http_client

        client_kwargs = {}
        if self._http_client is not None:
            client_kwargs["http_client"] = self._http_client

        if self._endpoint:
            # Local faster-whisper-server — api_key not needed but required by client.
            # Auto-append /v1 if missing (OpenAI-compatible servers expect /v1/audio/...).
            base_url = self._endpoint.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"
            self._client = openai.AsyncOpenAI(
                base_url=base_url,
                api_key=self._api_key or "unused",
                **client_kwargs,
            )
            logger.info("Whisper API provider initialized (endpoint: {})", base_url)
        else:
            # Default OpenAI cloud
            if not self._api_key:
                logger.warning("No OpenAI API key set — Whisper API transcription will fail")
            self._client = openai.AsyncOpenAI(api_key=self._api_key, **client_kwargs)
            logger.info("Whisper API provider initialized (OpenAI cloud)")

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
            transcript = asyncio.run(
                self._transcribe_file(wav_path, prompt=prompt, language=language)
            )
            text = transcript.text.strip()
            logger.info("Whisper API transcription: '{}'", text)
            return text
        except Exception:
            logger.opt(exception=True).error("Whisper API transcription failed")
            return ""
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    async def _transcribe_file(
        self,
        wav_path: str,
        *,
        prompt: str,
        language: str,
    ):
        with open(wav_path, "rb") as audio_file:
            return await self._client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                prompt=prompt if prompt else None,
                language=language if language else None,
            )

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

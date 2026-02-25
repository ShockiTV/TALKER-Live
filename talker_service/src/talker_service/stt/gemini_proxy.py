"""Gemini proxy transcription provider.

Uses a LiteLLM-compatible proxy to send audio to Gemini for transcription.
Accepts raw PCM audio bytes (16kHz mono int16), converts to WAV, then
base64-encodes and sends via the proxy chat completions endpoint.
"""

from __future__ import annotations

import base64
import tempfile
import wave

import requests
from loguru import logger

from ..config import settings


class GeminiProxyProvider:
    """Transcribe audio using a Gemini-compatible proxy endpoint."""

    def __init__(
        self,
        proxy_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._proxy_url = proxy_url or settings.proxy_endpoint
        self._api_key = api_key or settings.proxy_api_key
        logger.info("Gemini proxy STT provider initialized ({})", self._proxy_url)

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        prompt: str = "",
        language: str = "en",
    ) -> str:
        """Transcribe raw PCM int16 mono 16 kHz audio bytes via Gemini proxy."""
        if not audio_bytes:
            return ""

        wav_path = self._pcm_to_wav(audio_bytes)

        lang_map = {
            "en": "English", "ru": "Russian", "es": "Spanish", "fr": "French",
            "de": "German", "it": "Italian", "pt": "Portuguese", "pl": "Polish",
            "uk": "Ukrainian", "zh": "Chinese",
        }
        language_name = lang_map.get(language, language)

        instruction = f"Transcribe the following audio. The language is {language_name}."
        if prompt:
            instruction += f" For context, here is a hint about the content: '{prompt}'."
        instruction += " Return only the transcribed text, without any additional comments or formatting."

        try:
            with open(wav_path, "rb") as f:
                encoded_data = base64.b64encode(f.read()).decode("ascii")

            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gemini/gemini-2.5-flash-lite",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruction},
                            {
                                "type": "file",
                                "file": {
                                    "file_data": f"data:audio/wav;base64,{encoded_data}",
                                },
                            },
                        ],
                    }
                ],
            }

            resp = requests.post(self._proxy_url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()

            text = (
                resp.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            logger.info("Gemini proxy transcription: '{}'", text)
            return text
        except Exception:
            logger.opt(exception=True).error("Gemini proxy transcription failed")
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

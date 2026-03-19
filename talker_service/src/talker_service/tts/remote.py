"""Remote TTS client that delegates audio generation to a shared TTS HTTP service.

Used when ``TTS_SERVICE_URL`` is set (e.g. ``http://tts-service:8100``).
The shared TTS service runs pocket_tts in a Docker container and exposes
``POST /generate`` returning OGG Vorbis audio bytes.
"""

from __future__ import annotations

from typing import Optional

import httpx
from loguru import logger

# Match the timeout used by the embedded TTSEngine.
TTS_TIMEOUT_S = 30


class TTSRemoteClient:
    """HTTP client for the shared TTS microservice.

    Drop-in replacement for ``TTSEngine`` — exposes the same
    ``generate_audio(text, voice_id)`` async interface so the
    ``DialogueGenerator`` doesn't need to know which backend is active.
    """

    def __init__(self, base_url: str, http_client: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.volume_boost: float = 8.0  # updated by config mirror callback
        self._client = http_client or httpx.AsyncClient(timeout=TTS_TIMEOUT_S)
        self._owns_client = http_client is None
        logger.info("TTSRemoteClient initialized (endpoint: {})", self.base_url)

    def set_http_client(self, client: httpx.AsyncClient | None) -> None:
        """Swap the HTTP client instance used for outgoing requests."""
        if client is None:
            return
        self._client = client
        self._owns_client = False

    async def generate_audio(
        self,
        text: str,
        voice_id: str,
    ) -> Optional[tuple[bytes, int]]:
        """Request OGG audio from the remote TTS service.

        Args:
            text: Dialogue text to synthesize.
            voice_id: Voice ID matching a ``.safetensors`` file on the server.

        Returns:
            ``(ogg_bytes, duration_ms)`` on success, or ``None`` on error
            (triggers text-only fallback in the caller).
        """
        if not text or not text.strip():
            return None

        url = f"{self.base_url}/generate"
        payload = {
            "text": text,
            "voice_id": voice_id,
            "volume_boost": self.volume_boost,
        }

        try:
            resp = await self._client.post(url, json=payload, timeout=TTS_TIMEOUT_S)
            if resp.status_code != 200:
                body = resp.text[:300]
                logger.error(
                    "TTS service returned {} for '{}': {}",
                    resp.status_code,
                    text[:50],
                    body,
                )
                return None

            ogg_bytes = resp.content
            # Duration is returned as a header by the TTS service.
            duration_ms = int(resp.headers.get("X-Audio-Duration-Ms", 0))
            logger.info(
                "Remote TTS: {} bytes, {}ms for '{}'",
                len(ogg_bytes),
                duration_ms,
                text[:50],
            )
            return ogg_bytes, duration_ms

        except httpx.TimeoutException:
            logger.error(
                "TTS service timed out ({}s) for '{}'", TTS_TIMEOUT_S, text[:50]
            )
            return None
        except Exception:
            logger.opt(exception=True).error(
                "TTS service request failed for '{}'", text[:50]
            )
            return None

    async def close(self):
        """Close the underlying HTTP client."""
        if self._owns_client:
            await self._client.aclose()

    def shutdown(self):
        """No-op for API compatibility with TTSEngine.shutdown()."""
        # The httpx client is closed via ``close()`` during lifespan teardown.
        pass

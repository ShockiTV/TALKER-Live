"""STT provider factory.

Selects the appropriate STT provider based on the ``stt_method`` parameter.

Provider selection:
- ``"local"``  → WhisperLocalProvider (faster-whisper, CPU)
- ``"api"``    → WhisperAPIProvider   (OpenAI Whisper-1 API)
- ``"proxy"``  → GeminiProxyProvider  (chat-completion proxy)
- fallback     → WhisperLocalProvider

The factory lazily loads heavy dependencies (faster-whisper, openai)
so the service can start even if ``[stt]`` extras are not installed.
"""

from __future__ import annotations

from loguru import logger

from .base import STTProvider


def get_stt_provider(method: str = "local", **kwargs) -> STTProvider:
    """Return an STT provider instance.

    Args:
        method: One of ``"local"``, ``"api"``, ``"proxy"``.
        **kwargs: Forwarded to the provider constructor.
    """
    method = (method or "local").strip().lower()

    if method == "api":
        from .whisper_api import WhisperAPIProvider
        logger.info("Using Whisper API provider for STT")
        return WhisperAPIProvider(**kwargs)

    if method == "proxy":
        from .gemini_proxy import GeminiProxyProvider
        logger.info("Using Gemini proxy provider for STT")
        return GeminiProxyProvider(**kwargs)

    # Default: local
    from .whisper_local import WhisperLocalProvider
    logger.info("Using Whisper local provider for STT")
    return WhisperLocalProvider(**kwargs)

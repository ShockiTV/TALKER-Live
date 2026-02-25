"""
STT (Speech-to-Text) module for transcribing player microphone audio.

This module provides optional Whisper integration for transcribing streamed
audio chunks received from talker_bridge. If Whisper dependencies are not
installed, STT is disabled and audio topics are silently ignored.

Install with: pip install ".[stt]"
"""

from loguru import logger

STT_AVAILABLE = False

try:
    # Probe for at least one heavy STT dependency to confirm extras are installed.
    # faster-whisper is the primary local provider; openai is the API provider.
    # If neither is importable, STT is not usable.
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        import openai  # noqa: F401

    # Light imports that are always available within the package
    from talker_service.stt.factory import get_stt_provider  # noqa: F401
    from talker_service.stt.audio_buffer import AudioBuffer  # noqa: F401

    STT_AVAILABLE = True
    logger.info("STT dependencies available — speech-to-text enabled")
except ImportError as e:
    logger.warning("STT dependencies not installed — speech-to-text disabled ({})", e)

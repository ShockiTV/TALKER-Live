"""
TTS module for in-engine NPC voice playback.

This module provides optional pocket_tts integration for generating OGG Vorbis audio
from dialogue text. If pocket_tts is not installed, TTS generation is disabled and
the service falls back to text-only dialogue display.
"""

from loguru import logger

TTS_AVAILABLE = False
TTSEngine = None

try:
    from talker_service.tts.engine import TTSEngine as _TTSEngine
    TTSEngine = _TTSEngine
    TTS_AVAILABLE = True
    logger.info("pocket_tts loaded successfully — TTS available")
except ImportError as e:
    logger.warning("pocket_tts not installed — TTS disabled ({})", e)
except Exception as e:
    logger.error("Failed to load TTS engine: {}", e)

__all__ = ["TTS_AVAILABLE", "TTSEngine"]

"""Tests for STT provider factory — selection logic and lazy imports."""

import sys
from unittest.mock import patch, MagicMock
import importlib

import pytest

from talker_service.stt.base import STTProvider


def _mock_stt_modules():
    """Context manager that mocks heavy STT dependencies so factory imports work."""
    # Create mock modules for heavy dependencies
    mock_faster_whisper = MagicMock()
    mock_openai = MagicMock()

    # Mock WhisperModel class
    mock_faster_whisper.WhisperModel = MagicMock()

    return patch.dict("sys.modules", {
        "faster_whisper": mock_faster_whisper,
        "openai": mock_openai,
        "openai.audio": MagicMock(),
        "openai.audio.transcriptions": MagicMock(),
    })


# ── Provider selection ────────────────────────────────────────────────────────


class TestGetSTTProvider:
    """get_stt_provider() returns the correct provider type."""

    def test_default_returns_local(self):
        with _mock_stt_modules():
            # Force re-import of modules with mocked deps
            for mod_name in list(sys.modules):
                if "talker_service.stt" in mod_name:
                    del sys.modules[mod_name]

            from talker_service.stt.factory import get_stt_provider
            from talker_service.stt.whisper_local import WhisperLocalProvider
            provider = get_stt_provider("local")
            assert isinstance(provider, WhisperLocalProvider)

    def test_method_api_returns_whisper_api(self):
        with _mock_stt_modules():
            for mod_name in list(sys.modules):
                if "talker_service.stt" in mod_name:
                    del sys.modules[mod_name]

            from talker_service.stt.factory import get_stt_provider
            from talker_service.stt.whisper_api import WhisperAPIProvider
            provider = get_stt_provider("api")
            assert isinstance(provider, WhisperAPIProvider)

    def test_method_proxy_returns_gemini(self):
        with _mock_stt_modules():
            for mod_name in list(sys.modules):
                if "talker_service.stt" in mod_name:
                    del sys.modules[mod_name]

            from talker_service.stt.factory import get_stt_provider
            from talker_service.stt.gemini_proxy import GeminiProxyProvider
            provider = get_stt_provider("proxy")
            assert isinstance(provider, GeminiProxyProvider)

    def test_empty_method_defaults_to_local(self):
        with _mock_stt_modules():
            for mod_name in list(sys.modules):
                if "talker_service.stt" in mod_name:
                    del sys.modules[mod_name]

            from talker_service.stt.factory import get_stt_provider
            from talker_service.stt.whisper_local import WhisperLocalProvider
            provider = get_stt_provider("")
            assert isinstance(provider, WhisperLocalProvider)

    def test_none_method_defaults_to_local(self):
        with _mock_stt_modules():
            for mod_name in list(sys.modules):
                if "talker_service.stt" in mod_name:
                    del sys.modules[mod_name]

            from talker_service.stt.factory import get_stt_provider
            from talker_service.stt.whisper_local import WhisperLocalProvider
            provider = get_stt_provider(None)
            assert isinstance(provider, WhisperLocalProvider)

    def test_case_insensitive(self):
        with _mock_stt_modules():
            for mod_name in list(sys.modules):
                if "talker_service.stt" in mod_name:
                    del sys.modules[mod_name]

            from talker_service.stt.factory import get_stt_provider
            from talker_service.stt.gemini_proxy import GeminiProxyProvider
            provider = get_stt_provider("PROXY")
            assert isinstance(provider, GeminiProxyProvider)

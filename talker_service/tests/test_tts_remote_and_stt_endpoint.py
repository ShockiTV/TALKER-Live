"""Tests for TTSRemoteClient and WhisperAPIProvider endpoint extension."""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from talker_service.tts.remote import TTSRemoteClient


# ── TTSRemoteClient ──────────────────────────────────────────────────────────


class TestTTSRemoteClient:
    """TTSRemoteClient sends correct payload and handles errors."""

    @pytest.fixture
    def client(self):
        return TTSRemoteClient("http://tts-service:8100")

    @pytest.mark.asyncio
    async def test_generate_audio_sends_correct_payload(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"OggS_fake_audio"
        mock_resp.headers = {"X-Audio-Duration-Ms": "1234"}

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.generate_audio("Hello stalker", "dolg_1")

        mock_post.assert_called_once_with(
            "http://tts-service:8100/generate",
            json={"text": "Hello stalker", "voice_id": "dolg_1", "volume_boost": 8.0},
            timeout=30,
        )
        assert result == (b"OggS_fake_audio", 1234)

    @pytest.mark.asyncio
    async def test_generate_audio_uses_current_volume_boost(self, client):
        client.volume_boost = 12.0
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"audio"
        mock_resp.headers = {"X-Audio-Duration-Ms": "500"}

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await client.generate_audio("text", "v1")

        payload = mock_post.call_args[1]["json"]
        assert payload["volume_boost"] == 12.0

    @pytest.mark.asyncio
    async def test_generate_audio_empty_text_returns_none(self, client):
        assert await client.generate_audio("", "v1") is None
        assert await client.generate_audio("   ", "v1") is None

    @pytest.mark.asyncio
    async def test_generate_audio_timeout_returns_none(self, client):
        with patch.object(
            client._client, "post", new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timeout"),
        ):
            result = await client.generate_audio("Hello", "v1")
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_audio_http_error_returns_none(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.generate_audio("Hello", "v1")
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_audio_connection_error_returns_none(self, client):
        with patch.object(
            client._client, "post", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            result = await client.generate_audio("Hello", "v1")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_duration_header_defaults_to_zero(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"audio"
        mock_resp.headers = {}  # no X-Audio-Duration-Ms

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.generate_audio("Hi", "v1")
        assert result == (b"audio", 0)

    def test_shutdown_is_noop(self, client):
        """shutdown() exists for API compat with TTSEngine."""
        client.shutdown()  # should not raise


# ── WhisperAPIProvider endpoint parameter ────────────────────────────────────


def _fresh_whisper_api():
    """Clear cached stt modules and re-import WhisperAPIProvider."""
    for mod_name in list(sys.modules):
        if "talker_service.stt" in mod_name:
            del sys.modules[mod_name]
    from talker_service.stt.whisper_api import WhisperAPIProvider
    return WhisperAPIProvider


class TestWhisperAPIProviderEndpoint:
    """WhisperAPIProvider correctly handles the endpoint parameter."""

    def test_custom_endpoint_sets_base_url(self):
        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_openai.AsyncOpenAI.return_value = mock_client
        with patch.dict("sys.modules", {"openai": mock_openai}):
            WhisperAPIProvider = _fresh_whisper_api()
            provider = WhisperAPIProvider(endpoint="http://whisper:8200/v1")

        mock_openai.AsyncOpenAI.assert_called_once_with(
            base_url="http://whisper:8200/v1",
            api_key="unused",
        )
        assert provider._endpoint == "http://whisper:8200/v1"
        assert provider._client is mock_client

    def test_no_endpoint_uses_default_openai(self):
        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_openai.AsyncOpenAI.return_value = mock_client
        with patch.dict("sys.modules", {"openai": mock_openai}):
            WhisperAPIProvider = _fresh_whisper_api()
            provider = WhisperAPIProvider(api_key="sk-test123")

        mock_openai.AsyncOpenAI.assert_called_once_with(api_key="sk-test123")
        assert provider._endpoint == ""

    def test_custom_endpoint_with_api_key(self):
        mock_openai = MagicMock()
        mock_openai.AsyncOpenAI.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            WhisperAPIProvider = _fresh_whisper_api()
            WhisperAPIProvider(api_key="my-key", endpoint="http://local:8200/v1")

        mock_openai.AsyncOpenAI.assert_called_once_with(
            base_url="http://local:8200/v1",
            api_key="my-key",
        )


# ── Factory kwargs forwarding ────────────────────────────────────────────────


class TestFactoryEndpointForwarding:
    """get_stt_provider forwards endpoint kwarg to WhisperAPIProvider."""

    def test_endpoint_kwarg_forwarded(self):
        mock_openai = MagicMock()
        mock_openai.AsyncOpenAI.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            for mod_name in list(sys.modules):
                if "talker_service.stt" in mod_name:
                    del sys.modules[mod_name]

            from talker_service.stt.factory import get_stt_provider
            from talker_service.stt.whisper_api import WhisperAPIProvider

            provider = get_stt_provider("api", endpoint="http://whisper:8200/v1")

            assert isinstance(provider, WhisperAPIProvider)
            mock_openai.AsyncOpenAI.assert_called_once_with(
                base_url="http://whisper:8200/v1",
                api_key="unused",
            )

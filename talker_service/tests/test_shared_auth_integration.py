"""Integration-style tests for shared authenticated client injection."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from talker_service.auth.keycloak import KeycloakAuth
from talker_service.storage.embedding import EmbeddingClient
from talker_service.stt.whisper_api import WhisperAPIProvider
from talker_service.tts.remote import TTSRemoteClient


class _ScriptedKeycloakAuth(KeycloakAuth):
    def __init__(self, access_token: str):
        super().__init__(
            token_url="https://hub/auth/realms/talker/protocol/openid-connect/token",
            client_id="talker-client",
            client_secret="",
            username="player1",
            password="pw",
        )
        self._access_token_value = access_token

    async def _request_token(self, grant_type: str, refresh_token: str | None = None) -> str | None:
        now = self._now()
        self._access_token = self._access_token_value
        self._access_expires_at = now + 3600
        self._refresh_token = "refresh-token"
        self._refresh_expires_at = now + 3600
        return self._access_token


@pytest.mark.asyncio
async def test_tts_remote_client_uses_shared_auth_header():
    seen_auth: list[str | None] = []

    async def _handler(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("Authorization"))
        return httpx.Response(
            200,
            content=b"OggS",
            headers={"X-Audio-Duration-Ms": "321"},
            request=request,
        )

    shared_client = httpx.AsyncClient(
        auth=_ScriptedKeycloakAuth("tts-token"),
        transport=httpx.MockTransport(_handler),
    )
    try:
        tts = TTSRemoteClient("https://hub/api/tts", http_client=shared_client)
        result = await tts.generate_audio("hello", "voice")
        assert result == (b"OggS", 321)
        assert seen_auth == ["Bearer tts-token"]
    finally:
        await shared_client.aclose()


@pytest.mark.asyncio
async def test_embedding_client_uses_shared_auth_header():
    seen_auth: list[str | None] = []

    async def _handler(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"embedding": [0.1, 0.2]}, request=request)

    shared_client = httpx.AsyncClient(
        auth=_ScriptedKeycloakAuth("embed-token"),
        transport=httpx.MockTransport(_handler),
    )
    try:
        embed = EmbeddingClient(base_url="https://hub/api/embed", model="nomic-embed-text", http_client=shared_client)
        result = await embed.embed("hello")
        assert result == [0.1, 0.2]
        assert seen_auth == ["Bearer embed-token"]
    finally:
        await shared_client.aclose()


def test_whisper_provider_uses_shared_auth_client(monkeypatch):
    seen_auth: list[str | None] = []

    async def _handler(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"text": "transcribed text"}, request=request)

    def _make_client():
        return httpx.AsyncClient(
            auth=_ScriptedKeycloakAuth("stt-token"),
            transport=httpx.MockTransport(_handler),
        )

    class _FakeTranscriptions:
        def __init__(self, base_url: str, http_client: httpx.AsyncClient):
            self._base_url = base_url.rstrip("/")
            self._http_client = http_client

        async def create(self, model, file, prompt=None, language=None):
            response = await self._http_client.post(f"{self._base_url}/audio/transcriptions", data={"model": model})
            return SimpleNamespace(text=response.json()["text"])

    class _FakeAsyncOpenAI:
        def __init__(self, *, base_url=None, api_key=None, http_client=None):
            self.audio = SimpleNamespace(
                transcriptions=_FakeTranscriptions(base_url or "", http_client)
            )

        async def close(self):
            pass

    monkeypatch.setattr("talker_service.stt.whisper_api.openai.AsyncOpenAI", _FakeAsyncOpenAI)

    provider = WhisperAPIProvider(endpoint="https://hub/api/stt/v1", auth_factory=_make_client)
    text = provider.transcribe((b"\x00\x01") * 256)
    assert text == "transcribed text"
    assert seen_auth == ["Bearer stt-token"]

"""Unit tests for KeycloakAuth token lifecycle behavior."""

from __future__ import annotations

import httpx
import pytest

from talker_service.auth.keycloak import KeycloakAuth


class _ScriptedKeycloakAuth(KeycloakAuth):
    """KeycloakAuth test double with scripted token responses."""

    def __init__(self, scripted_tokens: list[dict[str, object] | None]):
        super().__init__(
            token_url="https://hub/auth/realms/talker/protocol/openid-connect/token",
            client_id="talker-client",
            client_secret="",
            username="player1",
            password="pw",
        )
        self._scripted_tokens = list(scripted_tokens)
        self.grant_calls: list[dict[str, object | None]] = []

    async def _request_token(self, grant_type: str, refresh_token: str | None = None) -> str | None:
        self.grant_calls.append({"grant_type": grant_type, "refresh_token": refresh_token})

        if not self._scripted_tokens:
            return None

        token_payload = self._scripted_tokens.pop(0)
        if token_payload is None:
            return None

        now = self._now()
        access_token = str(token_payload.get("access_token") or "")
        if not access_token:
            return None

        self._access_token = access_token
        self._access_expires_at = now + float(token_payload.get("expires_in") or 0.0)

        refresh_value = token_payload.get("refresh_token")
        if isinstance(refresh_value, str) and refresh_value:
            self._refresh_token = refresh_value
            self._refresh_expires_at = now + float(token_payload.get("refresh_expires_in") or 0.0)
        else:
            self._refresh_token = None
            self._refresh_expires_at = 0.0

        return self._access_token


@pytest.mark.asyncio
async def test_lazy_init_and_cached_reuse():
    service_headers: list[str | None] = []

    async def _service_handler(request: httpx.Request) -> httpx.Response:
        service_headers.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"ok": True}, request=request)

    auth = _ScriptedKeycloakAuth(
        scripted_tokens=[
            {
                "access_token": "tok-1",
                "refresh_token": "ref-1",
                "expires_in": 3600,
                "refresh_expires_in": 7200,
            }
        ]
    )

    assert auth.grant_calls == []

    transport = httpx.MockTransport(_service_handler)
    async with httpx.AsyncClient(auth=auth, transport=transport) as client:
        await client.get("https://hub/api/tts/health")
        await client.get("https://hub/api/tts/health")

    assert len(auth.grant_calls) == 1
    assert auth.grant_calls[0]["grant_type"] == "password"
    assert service_headers == ["Bearer tok-1", "Bearer tok-1"]


@pytest.mark.asyncio
async def test_refresh_token_used_when_access_expired():
    headers_seen: list[str | None] = []

    async def _service_handler(request: httpx.Request) -> httpx.Response:
        headers_seen.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"ok": True}, request=request)

    auth = _ScriptedKeycloakAuth(
        scripted_tokens=[
            {
                "access_token": "tok-initial",
                "refresh_token": "refresh-1",
                "expires_in": 0,
                "refresh_expires_in": 3600,
            },
            {
                "access_token": "tok-refreshed",
                "refresh_token": "refresh-2",
                "expires_in": 3600,
                "refresh_expires_in": 3600,
            },
        ]
    )

    transport = httpx.MockTransport(_service_handler)
    async with httpx.AsyncClient(auth=auth, transport=transport) as client:
        await client.get("https://hub/api/embed/api/tags")
        await client.get("https://hub/api/embed/api/tags")

    assert len(auth.grant_calls) == 2
    assert auth.grant_calls[0]["grant_type"] == "password"
    assert auth.grant_calls[1]["grant_type"] == "refresh_token"
    assert auth.grant_calls[1]["refresh_token"] == "refresh-1"
    assert headers_seen == ["Bearer tok-initial", "Bearer tok-refreshed"]


@pytest.mark.asyncio
async def test_full_ropc_fallback_when_refresh_expired():
    async def _service_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, request=request)

    auth = _ScriptedKeycloakAuth(
        scripted_tokens=[
            {
                "access_token": "tok-1",
                "refresh_token": "refresh-1",
                "expires_in": 0,
                "refresh_expires_in": 0,
            },
            {
                "access_token": "tok-2",
                "refresh_token": "refresh-2",
                "expires_in": 3600,
                "refresh_expires_in": 3600,
            },
        ]
    )

    transport = httpx.MockTransport(_service_handler)
    async with httpx.AsyncClient(auth=auth, transport=transport) as client:
        await client.get("https://hub/api/stt/v1/health")
        await client.get("https://hub/api/stt/v1/health")

    assert len(auth.grant_calls) == 2
    assert auth.grant_calls[0]["grant_type"] == "password"
    assert auth.grant_calls[1]["grant_type"] == "password"


@pytest.mark.asyncio
async def test_401_retry_once_with_fresh_token():
    seen_headers: list[str | None] = []

    async def _service_handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers.get("Authorization"))
        if len(seen_headers) == 1:
            return httpx.Response(401, json={"error": "expired"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    auth = _ScriptedKeycloakAuth(
        scripted_tokens=[
            {
                "access_token": "stale-token",
                "refresh_token": "refresh-1",
                "expires_in": 3600,
                "refresh_expires_in": 3600,
            },
            {
                "access_token": "fresh-token",
                "refresh_token": "refresh-2",
                "expires_in": 3600,
                "refresh_expires_in": 3600,
            },
        ]
    )

    transport = httpx.MockTransport(_service_handler)
    async with httpx.AsyncClient(auth=auth, transport=transport) as client:
        response = await client.get("https://hub/api/tts/generate")

    assert response.status_code == 200
    assert len(auth.grant_calls) == 2
    assert seen_headers == ["Bearer stale-token", "Bearer fresh-token"]


@pytest.mark.asyncio
async def test_token_failure_falls_back_to_no_auth():
    seen_headers: list[str | None] = []

    async def _service_handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"ok": True}, request=request)

    auth = _ScriptedKeycloakAuth(scripted_tokens=[None])

    transport = httpx.MockTransport(_service_handler)
    async with httpx.AsyncClient(auth=auth, transport=transport) as client:
        response = await client.get("https://hub/api/embed/api/embeddings")

    assert response.status_code == 200
    assert len(auth.grant_calls) == 1
    assert seen_headers == [None]


@pytest.mark.asyncio
async def test_second_401_is_not_retried():
    attempt_count = 0

    async def _service_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        return httpx.Response(401, json={"error": "still unauthorized"}, request=request)

    auth = _ScriptedKeycloakAuth(
        scripted_tokens=[
            {
                "access_token": "tok-1",
                "refresh_token": "ref-1",
                "expires_in": 3600,
                "refresh_expires_in": 3600,
            },
            {
                "access_token": "tok-2",
                "refresh_token": "ref-2",
                "expires_in": 3600,
                "refresh_expires_in": 3600,
            },
        ]
    )

    transport = httpx.MockTransport(_service_handler)
    async with httpx.AsyncClient(auth=auth, transport=transport) as client:
        response = await client.get("https://hub/api/stt/v1/audio/transcriptions")

    assert response.status_code == 401
    assert attempt_count == 2
    assert len(auth.grant_calls) == 2

"""Tests for shared HTTP client factory and hub URL derivation."""

from __future__ import annotations

import pytest

from talker_service.auth.factory import create_shared_http_client, derive_service_urls
from talker_service.auth.keycloak import KeycloakAuth


def _extract_auth(client):
    return getattr(client, "_auth", getattr(client, "auth", None))


def test_derive_urls_from_hub_when_service_urls_empty():
    urls = derive_service_urls(
        env_hub_url="https://talker-live.duckdns.org",
        mcm_hub_url="",
        tts_service_url="",
        stt_endpoint="",
        ollama_base_url="",
    )

    assert urls["hub_url"] == "https://talker-live.duckdns.org"
    assert urls["tts_service_url"] == "https://talker-live.duckdns.org/api/tts"
    assert urls["stt_endpoint"] == "https://talker-live.duckdns.org/api/stt/v1"
    assert urls["ollama_base_url"] == "https://talker-live.duckdns.org/api/embed"


def test_explicit_service_urls_override_hub_derivation():
    urls = derive_service_urls(
        env_hub_url="https://talker-live.duckdns.org",
        mcm_hub_url="",
        tts_service_url="http://127.0.0.1:8100",
        stt_endpoint="http://127.0.0.1:8200/v1",
        ollama_base_url="http://127.0.0.1:11434",
    )

    assert urls["tts_service_url"] == "http://127.0.0.1:8100"
    assert urls["stt_endpoint"] == "http://127.0.0.1:8200/v1"
    assert urls["ollama_base_url"] == "http://127.0.0.1:11434"


def test_mcm_hub_overrides_env_hub():
    urls = derive_service_urls(
        env_hub_url="https://default.example.com",
        mcm_hub_url="https://custom.example.com",
        tts_service_url="",
        stt_endpoint="",
        ollama_base_url="",
    )

    assert urls["hub_url"] == "https://custom.example.com"
    assert urls["tts_service_url"] == "https://custom.example.com/api/tts"
    assert urls["stt_endpoint"] == "https://custom.example.com/api/stt/v1"
    assert urls["ollama_base_url"] == "https://custom.example.com/api/embed"


def test_empty_hub_keeps_urls_empty():
    urls = derive_service_urls(
        env_hub_url="",
        mcm_hub_url="",
        tts_service_url="",
        stt_endpoint="",
        ollama_base_url="",
    )

    assert urls["hub_url"] == ""
    assert urls["tts_service_url"] == ""
    assert urls["stt_endpoint"] == ""
    assert urls["ollama_base_url"] == ""


@pytest.mark.asyncio
async def test_create_shared_client_remote_with_credentials_uses_keycloak_auth():
    client = create_shared_http_client(
        service_type=1,
        hub_url="https://talker-live.duckdns.org",
        auth_username="player1",
        auth_password="pw",
        auth_client_id="talker-client",
        auth_client_secret="",
        timeout=20,
    )
    try:
        auth = _extract_auth(client)
        # Remote service runs on VPS behind Caddy — no outbound auth needed
        assert auth is None
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_create_shared_client_local_with_credentials_uses_keycloak_auth():
    client = create_shared_http_client(
        service_type=0,
        hub_url="https://talker-live.duckdns.org",
        auth_username="player1",
        auth_password="pw",
        auth_client_id="talker-client",
        auth_client_secret="",
        timeout=20,
    )
    try:
        auth = _extract_auth(client)
        # Local service needs Keycloak auth to reach VPS through Caddy
        assert isinstance(auth, KeycloakAuth)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_create_shared_client_local_or_missing_credentials_has_no_auth():
    client = create_shared_http_client(
        service_type=0,
        hub_url="https://talker-live.duckdns.org",
        auth_username="",
        auth_password="",
        auth_client_id="talker-client",
        auth_client_secret="",
        timeout=20,
    )
    try:
        auth = _extract_auth(client)
        assert auth is None
    finally:
        await client.aclose()

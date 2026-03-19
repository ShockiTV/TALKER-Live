"""Factory helpers for per-session shared HTTP clients."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from .keycloak import KeycloakAuth

REMOTE_SERVICE_TYPE = 1


def _trim(value: str | None) -> str:
    return (value or "").strip()


def _normalize_hub_url(url: str) -> str:
    value = _trim(url)
    if not value:
        return ""
    return value.rstrip("/")


def derive_service_urls(
    *,
    env_hub_url: str,
    mcm_hub_url: str,
    tts_service_url: str,
    stt_endpoint: str,
    ollama_base_url: str,
) -> dict[str, str]:
    """Derive service URLs from hub URL while preserving explicit overrides."""
    explicit_tts = _trim(tts_service_url)
    explicit_stt = _trim(stt_endpoint)
    explicit_ollama = _trim(ollama_base_url)

    hub_url = _normalize_hub_url(mcm_hub_url) or _normalize_hub_url(env_hub_url)

    derived_tts = explicit_tts or (f"{hub_url}/api/tts" if hub_url else "")
    derived_stt = explicit_stt or (f"{hub_url}/api/stt/v1" if hub_url else "")
    derived_ollama = explicit_ollama or (f"{hub_url}/api/embed" if hub_url else "")

    return {
        "hub_url": hub_url,
        "tts_service_url": derived_tts,
        "stt_endpoint": derived_stt,
        "ollama_base_url": derived_ollama,
    }


def derive_token_url(hub_url: str) -> str:
    """Build Keycloak token URL from a hub URL."""
    normalized = _normalize_hub_url(hub_url)
    if not normalized:
        return ""

    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        return ""

    return f"{parsed.scheme}://{parsed.netloc}/auth/realms/talker/protocol/openid-connect/token"


def create_shared_http_client(
    *,
    service_type: int,
    hub_url: str,
    auth_username: str,
    auth_password: str,
    auth_client_id: str,
    auth_client_secret: str,
    timeout: float = 30.0,
) -> httpx.AsyncClient:
    """Create a shared AsyncClient with optional KeycloakAuth."""
    token_url = derive_token_url(hub_url)
    username = _trim(auth_username)
    password = auth_password or ""
    client_id = _trim(auth_client_id)

    should_use_auth = (
        service_type == REMOTE_SERVICE_TYPE
        and bool(token_url)
        and bool(username)
        and bool(password)
        and bool(client_id)
    )

    if should_use_auth:
        auth = KeycloakAuth(
            token_url=token_url,
            client_id=client_id,
            client_secret=_trim(auth_client_secret),
            username=username,
            password=password,
        )
        return httpx.AsyncClient(timeout=timeout, auth=auth)

    return httpx.AsyncClient(timeout=timeout)

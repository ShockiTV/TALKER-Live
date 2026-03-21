"""Keycloak-backed outbound auth for shared service gateway calls."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from loguru import logger

_TOKEN_TIMEOUT_SECONDS = 8.0
_EXPIRY_SAFETY_MARGIN_SECONDS = 15.0


class KeycloakAuth(httpx.Auth):
    """httpx.Auth implementation for Keycloak ROPC with token reuse and refresh."""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
    ) -> None:
        self.token_url = (token_url or "").strip()
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self.username = (username or "").strip()
        self.password = password or ""

        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._access_expires_at: float = 0.0
        self._refresh_expires_at: float = 0.0
        self._lock = asyncio.Lock()

    def _is_configured(self) -> bool:
        return bool(self.token_url and self.client_id and self.username and self.password)

    @staticmethod
    def _now() -> float:
        return time.time()

    def _has_valid_access_token(self) -> bool:
        if not self._access_token:
            return False
        return self._access_expires_at > (self._now() + _EXPIRY_SAFETY_MARGIN_SECONDS)

    def _has_valid_refresh_token(self) -> bool:
        if not self._refresh_token:
            return False
        return self._refresh_expires_at > (self._now() + _EXPIRY_SAFETY_MARGIN_SECONDS)

    def clear(self) -> None:
        """Clear all cached token state."""
        self._access_token = None
        self._refresh_token = None
        self._access_expires_at = 0.0
        self._refresh_expires_at = 0.0

    def _build_token_payload(self, grant_type: str, refresh_token: str | None = None) -> dict[str, str]:
        payload: dict[str, str] = {
            "grant_type": grant_type,
            "client_id": self.client_id,
        }
        if self.client_secret:
            payload["client_secret"] = self.client_secret
        if grant_type == "password":
            payload["username"] = self.username
            payload["password"] = self.password
        elif grant_type == "refresh_token" and refresh_token:
            payload["refresh_token"] = refresh_token
        return payload

    async def _request_token(self, grant_type: str, refresh_token: str | None = None) -> str | None:
        payload = self._build_token_payload(grant_type, refresh_token)

        try:
            async with httpx.AsyncClient(timeout=_TOKEN_TIMEOUT_SECONDS) as client:
                response = await client.post(self.token_url, data=payload)
        except Exception as exc:
            logger.warning("Keycloak token request failed (grant_type={}): {}", grant_type, exc)
            return None

        if response.status_code >= 400:
            details: str
            try:
                details_json = response.json()
                if isinstance(details_json, dict):
                    details = str(details_json.get("error_description") or details_json.get("error") or details_json)
                else:
                    details = str(details_json)
            except Exception:
                details = response.text[:300]
            logger.warning(
                "Keycloak token endpoint returned {} (grant_type={}): {}",
                response.status_code,
                grant_type,
                details,
            )
            return None

        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            logger.warning("Keycloak token response parse failed: {}", exc)
            return None

        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            logger.warning("Keycloak token response missing access_token")
            return None

        now = self._now()
        expires_in = float(data.get("expires_in") or 0.0)
        refresh_expires_in = float(data.get("refresh_expires_in") or 0.0)

        self._access_token = access_token
        self._access_expires_at = now + max(expires_in, 0.0)

        refresh_value = data.get("refresh_token")
        if isinstance(refresh_value, str) and refresh_value:
            self._refresh_token = refresh_value
            self._refresh_expires_at = now + max(refresh_expires_in, 0.0)
        elif grant_type == "password":
            self._refresh_token = None
            self._refresh_expires_at = 0.0

        return access_token

    async def _get_or_refresh_access_token(self) -> str | None:
        if not self._is_configured():
            return None

        async with self._lock:
            if self._has_valid_access_token():
                return self._access_token

            if self._has_valid_refresh_token() and self._refresh_token:
                refreshed = await self._request_token("refresh_token", refresh_token=self._refresh_token)
                if refreshed:
                    return refreshed

            return await self._request_token("password")

    async def async_auth_flow(self, request: httpx.Request):  # type: ignore[override]
        token = await self._get_or_refresh_access_token()
        if token:
            request.headers["Authorization"] = f"Bearer {token}"
        else:
            request.headers.pop("Authorization", None)

        response = yield request

        if response.status_code != 401:
            return

        async with self._lock:
            self.clear()

        retry_token = await self._get_or_refresh_access_token()
        if retry_token:
            request.headers["Authorization"] = f"Bearer {retry_token}"
        else:
            request.headers.pop("Authorization", None)

        yield request

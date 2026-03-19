"""Ollama embedding client wrapper."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger


class EmbeddingClient:
    """Compute embeddings using Ollama /api/embeddings."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str = "nomic-embed-text",
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = http_client or httpx.AsyncClient(timeout=self.timeout)
        self._owns_client = http_client is None

    def set_http_client(self, client: httpx.AsyncClient | None) -> None:
        """Swap the HTTP client used for embedding calls."""
        if client is None:
            return
        self._client = client
        self._owns_client = False

    async def close(self) -> None:
        """Close internal HTTP client when owned by this instance."""
        if self._owns_client:
            await self._client.aclose()

    async def embed(self, text: str) -> list[float] | None:
        """Return embedding vector, or None on network/provider failure."""
        if not text:
            return None

        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": self.model,
            "prompt": text,
        }

        try:
            response = await self._client.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            embedding = data.get("embedding")
            if isinstance(embedding, list):
                return embedding
            logger.warning("Embedding response missing vector payload")
            return None
        except Exception as exc:
            logger.warning("Embedding request failed: {}", exc)
            return None

    async def is_reachable(self) -> bool:
        """Check whether Ollama responds to /api/tags."""
        url = f"{self.base_url}/api/tags"
        try:
            response = await self._client.get(url, timeout=self.timeout)
            response.raise_for_status()
            return True
        except Exception:
            return False

    async def ensure_model_pulled(self) -> bool:
        """Ensure embedding model exists locally. Returns False on failure."""
        tags_url = f"{self.base_url}/api/tags"
        pull_url = f"{self.base_url}/api/pull"

        try:
            tags_resp = await self._client.get(tags_url, timeout=self.timeout)
            tags_resp.raise_for_status()
            tags_data: dict[str, Any] = tags_resp.json()
            names = {
                item.get("name")
                for item in tags_data.get("models", [])
                if isinstance(item, dict)
            }
            if self.model in names or f"{self.model}:latest" in names:
                return True

            logger.info("Pulling missing Ollama model: {}", self.model)
            pull_resp = await self._client.post(pull_url, json={"name": self.model}, timeout=self.timeout)
            pull_resp.raise_for_status()
            return True
        except Exception as exc:
            logger.warning("Ollama model pull/health check failed: {}", exc)
            return False

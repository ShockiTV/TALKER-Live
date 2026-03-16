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
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model
        self.timeout = timeout

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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
            response.raise_for_status()
            return True
        except Exception:
            return False

    async def ensure_model_pulled(self) -> bool:
        """Ensure embedding model exists locally. Returns False on failure."""
        tags_url = f"{self.base_url}/api/tags"
        pull_url = f"{self.base_url}/api/pull"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                tags_resp = await client.get(tags_url)
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
                pull_resp = await client.post(pull_url, json={"name": self.model})
                pull_resp.raise_for_status()
                return True
        except Exception as exc:
            logger.warning("Ollama model pull/health check failed: {}", exc)
            return False

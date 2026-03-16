"""Tests for storage foundation components (Neo4j availability + embeddings)."""

import httpx
import pytest

from talker_service.storage.embedding import EmbeddingClient
from talker_service.storage.neo4j_client import Neo4jClient


def test_neo4j_is_unavailable_without_uri():
    client = Neo4jClient(uri="")
    assert client.is_available() is False


@pytest.mark.asyncio
async def test_embedding_graceful_failure(monkeypatch):
    async def _boom(self, url, json=None):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.AsyncClient, "post", _boom)

    client = EmbeddingClient(base_url="http://127.0.0.1:11434", model="nomic-embed-text")
    embedding = await client.embed("hello")

    assert embedding is None

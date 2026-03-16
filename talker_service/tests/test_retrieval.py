"""Tests for hybrid retrieval (RRF, budget packing, chronological output)."""

import pytest

from talker_service.storage.retrieval import rrf_merge, pack_by_budget, retrieve_context


def test_rrf_merge_with_overlap():
    vector = [
        {"ts": 10, "cs": "a", "text": "one", "game_time_ms": 10, "token_count": 5},
        {"ts": 20, "cs": "b", "text": "two", "game_time_ms": 20, "token_count": 5},
    ]
    bm25 = [
        {"ts": 20, "cs": "b", "text": "two", "game_time_ms": 20, "token_count": 5},
        {"ts": 30, "cs": "c", "text": "three", "game_time_ms": 30, "token_count": 5},
    ]

    merged = rrf_merge(vector, bm25)
    keys = {(row["ts"], row["cs"]) for row in merged}

    assert (10, "a") in keys
    assert (20, "b") in keys
    assert (30, "c") in keys
    assert merged[0]["cs"] == "b"


def test_pack_by_budget_skips_over_budget_items():
    rows = [
        {"ts": 1, "cs": "a", "text": "aaa", "token_count": 3},
        {"ts": 2, "cs": "b", "text": "bbbb", "token_count": 4},
        {"ts": 3, "cs": "c", "text": "cc", "token_count": 2},
    ]

    packed = pack_by_budget(rows, budget=5)

    assert len(packed) == 2
    assert packed[0]["cs"] == "a"
    assert packed[1]["cs"] == "c"


class _FakeNeo4j:
    def __init__(self):
        self.scopes = []

    def is_available(self):
        return True

    def search_vector(self, *, session_id, char_id, embedding, scope, limit):
        self.scopes.append(scope)
        if scope == "global":
            return [
                {"ts": 2, "cs": "g2", "text": "global two", "game_time_ms": 200, "token_count": 2},
            ]
        return [
            {"ts": 1, "cs": "c1", "text": "char one", "game_time_ms": 100, "token_count": 2},
        ]

    def search_bm25(self, *, session_id, char_id, query_text, scope, limit):
        self.scopes.append(scope)
        if scope == "global":
            return [
                {"ts": 1, "cs": "g1", "text": "global one", "game_time_ms": 50, "token_count": 2},
            ]
        return [
            {"ts": 3, "cs": "c3", "text": "char three", "game_time_ms": 300, "token_count": 2},
        ]


class _FakeEmbedding:
    async def embed(self, text):
        return [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_retrieve_context_sorts_chronologically_and_scopes():
    neo4j = _FakeNeo4j()

    rows = await retrieve_context(
        session_id="lua-1",
        char_id="char-1",
        query_text="wolf",
        budget=10,
        scope="character",
        neo4j_client=neo4j,
        embedding_client=_FakeEmbedding(),
    )

    assert [r["game_time_ms"] for r in rows] == [100, 300]
    assert "character" in neo4j.scopes

    rows_global = await retrieve_context(
        session_id="lua-1",
        char_id="char-1",
        query_text="wolf",
        budget=10,
        scope="global",
        neo4j_client=neo4j,
        embedding_client=_FakeEmbedding(),
    )

    assert [r["game_time_ms"] for r in rows_global] == [50, 200]
    assert "global" in neo4j.scopes


@pytest.mark.asyncio
async def test_token_count_defaults_to_len_div_4():
    class _NoTokenNeo4j(_FakeNeo4j):
        def search_vector(self, **kwargs):
            return [{"ts": 1, "cs": "x", "text": "abcdefgh", "game_time_ms": 100}]

        def search_bm25(self, **kwargs):
            return []

    rows = await retrieve_context(
        session_id="lua-1",
        char_id="char-1",
        query_text="wolf",
        budget=10,
        scope="character",
        neo4j_client=_NoTokenNeo4j(),
        embedding_client=_FakeEmbedding(),
    )

    assert rows[0]["token_count"] == 2

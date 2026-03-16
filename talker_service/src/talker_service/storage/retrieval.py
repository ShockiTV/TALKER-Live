"""Hybrid retrieval helpers (vector + BM25 + RRF + budget packing)."""

from __future__ import annotations

from typing import Any

from loguru import logger


def _row_key(row: dict[str, Any]) -> tuple[Any, Any]:
    return row.get("ts"), row.get("cs")


def _normalized_token_count(row: dict[str, Any]) -> int:
    token_count = row.get("token_count")
    if isinstance(token_count, int) and token_count > 0:
        return token_count
    text = str(row.get("text") or "")
    return max(1, len(text) // 4)


def rrf_merge(
    vector_rows: list[dict[str, Any]],
    bm25_rows: list[dict[str, Any]],
    *,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion merge.

    score = 1/(k + rank_v) + 1/(k + rank_b)
    """
    merged: dict[tuple[Any, Any], dict[str, Any]] = {}

    for idx, row in enumerate(vector_rows, start=1):
        key = _row_key(row)
        entry = merged.setdefault(key, dict(row))
        entry["_rank_v"] = idx

    for idx, row in enumerate(bm25_rows, start=1):
        key = _row_key(row)
        entry = merged.setdefault(key, dict(row))
        entry["_rank_b"] = idx

    scored: list[dict[str, Any]] = []
    for row in merged.values():
        rank_v = row.get("_rank_v")
        rank_b = row.get("_rank_b")
        score = 0.0
        if rank_v is not None:
            score += 1.0 / (k + rank_v)
        if rank_b is not None:
            score += 1.0 / (k + rank_b)
        row["rrf_score"] = score
        row["token_count"] = _normalized_token_count(row)
        scored.append(row)

    scored.sort(key=lambda r: r.get("rrf_score", 0.0), reverse=True)
    return scored


def pack_by_budget(rows: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    """Greedy packing in rank order under token budget."""
    if budget <= 0:
        return []

    packed: list[dict[str, Any]] = []
    used = 0

    for row in rows:
        cost = _normalized_token_count(row)
        if used + cost > budget:
            continue
        packed.append(row)
        used += cost

    return packed


async def retrieve_context(
    session_id: str,
    char_id: str,
    query_text: str,
    budget: int,
    scope: str = "character",
    *,
    neo4j_client=None,
    embedding_client=None,
) -> list[dict[str, Any]]:
    """Retrieve context chunks using hybrid search and token-budget packing."""
    if not neo4j_client or not neo4j_client.is_available():
        return []

    embedding = None
    if embedding_client and query_text:
        embedding = await embedding_client.embed(query_text)

    vector_rows = neo4j_client.search_vector(
        session_id=session_id,
        char_id=char_id,
        embedding=embedding,
        scope=scope,
        limit=50,
    )
    bm25_rows = neo4j_client.search_bm25(
        session_id=session_id,
        char_id=char_id,
        query_text=query_text,
        scope=scope,
        limit=20,
    )

    merged = rrf_merge(vector_rows, bm25_rows)
    packed = pack_by_budget(merged, int(budget))

    packed.sort(key=lambda r: int(r.get("game_time_ms") or 0))
    logger.debug(
        "retrieve_context: scope={}, vector={}, bm25={}, packed={}",
        scope,
        len(vector_rows),
        len(bm25_rows),
        len(packed),
    )
    return packed

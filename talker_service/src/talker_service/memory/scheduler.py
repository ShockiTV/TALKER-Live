"""Budget-pool compaction scheduler.

Limits the total number of compaction LLM calls per dialogue cycle
and prioritises characters with the highest tier bloat (most over-cap).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .compaction import CompactionEngine

# Default max characters to compact per scheduling call.
COMPACTION_BUDGET = 3


class CompactionScheduler:
    """Shared budget-pool scheduler for post-dialogue compaction.

    After witness injection, the caller passes all candidate character IDs
    to :meth:`schedule`.  The scheduler:

    1. Queries ``npc.memories.tiers`` for every character in one batch.
    2. Scores each character via ``CompactionEngine.score_character()``.
    3. Sorts descending (highest bloat first).
    4. Runs ``check_and_compact()`` for the top *budget* characters.
    5. Logs any deferred characters.

    The ``schedule()`` method is designed to be wrapped in
    ``asyncio.create_task()`` so it doesn't block dialogue display.
    """

    def __init__(self, engine: "CompactionEngine", *, budget: int = COMPACTION_BUDGET):
        self.engine = engine
        self.budget = budget

    async def schedule(self, character_ids: set[str]) -> None:
        """Score and compact the most bloated characters within budget.

        Args:
            character_ids: Set of character IDs to evaluate.
        """
        if not character_ids or self.budget <= 0:
            if character_ids and self.budget <= 0:
                logger.debug(
                    "Compaction budget is 0 — deferring {} characters",
                    len(character_ids),
                )
            return

        # 1. Batch-query tier counts for all candidates
        # Use a stable ordering so zip(ids, results) aligns correctly.
        id_list = sorted(character_ids)
        queries = [
            {"query": "npc.memories.tiers", "character_id": cid}
            for cid in id_list
        ]

        try:
            results = await self.engine.state_client.query_batch(queries)
        except Exception as e:
            logger.warning("Compaction scheduler: tier query failed, skipping cycle: {}", e)
            return

        if not results:
            logger.debug("Compaction scheduler: empty tier query response")
            return

        # 2. Score each character
        from .compaction import CompactionEngine

        scored: list[tuple[str, int]] = []
        for cid, result in zip(id_list, results):
            tiers = result.get("tiers") if isinstance(result, dict) else None
            if not tiers:
                continue
            score = CompactionEngine.score_character(tiers)
            if score > 0:
                scored.append((cid, score))

        if not scored:
            logger.debug("Compaction scheduler: all characters below cap, nothing to compact")
            return

        # 3. Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # 4. Run compaction for top N within budget
        selected = scored[: self.budget]
        deferred = scored[self.budget :]

        logger.info(
            "Compaction scheduler: compacting {}/{} characters (budget={}), {} deferred",
            len(selected),
            len(scored),
            self.budget,
            len(deferred),
        )

        for cid, score in selected:
            logger.debug("Compacting {} (score={})", cid, score)
            try:
                await self.engine.check_and_compact(cid)
            except Exception:
                logger.opt(exception=True).error("Compaction failed for {}", cid)

        if deferred:
            deferred_ids = [cid for cid, _ in deferred]
            logger.debug("Deferred compaction for: {}", deferred_ids)

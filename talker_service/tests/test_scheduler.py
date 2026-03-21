"""Tests for CompactionScheduler and score_character()."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from talker_service.memory.compaction import CompactionEngine, TIER_CAPS
from talker_service.memory.scheduler import CompactionScheduler


# ---------------------------------------------------------------------------
# Task 2.2 — score_character unit tests
# ---------------------------------------------------------------------------

class TestScoreCharacter:
    """Unit tests for CompactionEngine.score_character()."""

    def test_over_cap_events(self):
        """Events over cap → positive score."""
        tiers = {"events": 120, "summaries": 5, "digests": 3, "cores": 2}
        assert CompactionEngine.score_character(tiers) == 20  # 120 - 100

    def test_multiple_tiers_over_cap(self):
        """Multiple tiers over cap → summed excess."""
        tiers = {"events": 110, "summaries": 12, "digests": 3, "cores": 2}
        # events: 110-100=10, summaries: 12-10=2, digests: 0, cores: 0
        assert CompactionEngine.score_character(tiers) == 12

    def test_all_below_cap_returns_zero(self):
        """All tiers at or below cap → 0."""
        tiers = {"events": 50, "summaries": 5, "digests": 3, "cores": 2}
        assert CompactionEngine.score_character(tiers) == 0

    def test_exactly_at_cap_returns_zero(self):
        """Tiers exactly at cap → 0."""
        tiers = {
            "events": TIER_CAPS["events"],
            "summaries": TIER_CAPS["summaries"],
            "digests": TIER_CAPS["digests"],
            "cores": TIER_CAPS["cores"],
        }
        assert CompactionEngine.score_character(tiers) == 0

    def test_empty_tiers_returns_zero(self):
        """Empty tiers dict → 0."""
        assert CompactionEngine.score_character({}) == 0

    def test_partial_tiers(self):
        """Only some tier keys present → missing tiers treated as 0."""
        tiers = {"events": 120}
        assert CompactionEngine.score_character(tiers) == 20

    def test_all_tiers_massively_over_cap(self):
        """All tiers heavily over cap."""
        tiers = {"events": 200, "summaries": 20, "digests": 15, "cores": 10}
        expected = (200 - 100) + (20 - 10) + (15 - 5) + (10 - 5)
        assert CompactionEngine.score_character(tiers) == expected  # 100+10+10+5=125


# ---------------------------------------------------------------------------
# Task 3.4 — CompactionScheduler unit tests
# ---------------------------------------------------------------------------

class TestCompactionScheduler:
    """Unit tests for CompactionScheduler."""

    @pytest.fixture
    def mock_state_client(self):
        client = MagicMock()
        client.query_batch = AsyncMock()
        client.mutate_batch = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def mock_llm_client(self):
        client = MagicMock()
        client.complete = AsyncMock(return_value="Compressed text here.")
        return client

    @pytest.fixture
    def engine(self, mock_state_client, mock_llm_client):
        return CompactionEngine(
            state_client=mock_state_client,
            llm_client=mock_llm_client,
        )

    @pytest.fixture
    def scheduler(self, engine):
        return CompactionScheduler(engine, budget=3)

    @pytest.mark.asyncio
    async def test_budget_limits_compactions(self, scheduler, engine, mock_state_client):
        """8 candidates with budget 3 → only top 3 get compacted."""
        char_ids = {f"c{i}" for i in range(8)}

        # Return tier counts — each with descending bloat
        tier_results = []
        for i in range(8):
            tier_results.append({
                "tiers": {
                    "events": 100 + (80 - i * 10),  # c0=180, c1=170, ..., c7=110
                    "summaries": 5,
                    "digests": 3,
                    "cores": 2,
                }
            })
        mock_state_client.query_batch.return_value = tier_results

        # Mock check_and_compact to track calls
        engine.check_and_compact = AsyncMock()

        await scheduler.schedule(char_ids)

        # Should compact exactly 3 characters
        assert engine.check_and_compact.call_count == 3

    @pytest.mark.asyncio
    async def test_priority_ordering_highest_first(self, scheduler, engine, mock_state_client):
        """Characters with highest scores get compacted first."""
        char_ids = {"low", "high", "mid"}

        # Return tier results in the same order as char_ids iteration
        # We need to control the mapping — use a list matching iteration order
        id_list = sorted(char_ids)  # deterministic ordering

        tier_map = {
            "high": {"tiers": {"events": 200, "summaries": 5, "digests": 3, "cores": 2}},  # score=100
            "low": {"tiers": {"events": 101, "summaries": 5, "digests": 3, "cores": 2}},   # score=1
            "mid": {"tiers": {"events": 150, "summaries": 5, "digests": 3, "cores": 2}},   # score=50
        }

        # Build results in iteration order of char_ids (set → sorted for determinism)
        mock_state_client.query_batch.return_value = [tier_map[cid] for cid in id_list]

        engine.check_and_compact = AsyncMock()

        # Use sorted set to match query order
        scheduler_set = set(id_list)
        await scheduler.schedule(scheduler_set)

        # All 3 should be compacted (budget=3), highest first
        calls = [call.args[0] for call in engine.check_and_compact.call_args_list]
        assert calls[0] == "high"
        assert calls[1] == "mid"
        assert calls[2] == "low"

    @pytest.mark.asyncio
    async def test_zero_score_characters_skipped(self, scheduler, engine, mock_state_client):
        """Characters at or below cap score 0 → skipped entirely."""
        char_ids = {"a", "b"}

        mock_state_client.query_batch.return_value = [
            {"tiers": {"events": 50, "summaries": 5, "digests": 3, "cores": 2}},
            {"tiers": {"events": 80, "summaries": 8, "digests": 4, "cores": 3}},
        ]

        engine.check_and_compact = AsyncMock()

        await scheduler.schedule(char_ids)

        engine.check_and_compact.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_query_failure_skips_cycle(self, scheduler, engine, mock_state_client):
        """Batch query failure → no compaction, no crash."""
        mock_state_client.query_batch.side_effect = Exception("WS timeout")

        engine.check_and_compact = AsyncMock()

        await scheduler.schedule({"c1", "c2"})

        engine.check_and_compact.assert_not_called()

    @pytest.mark.asyncio
    async def test_budget_zero_disables_compaction(self, engine, mock_state_client):
        """Budget=0 → no compaction runs."""
        sched = CompactionScheduler(engine, budget=0)

        engine.check_and_compact = AsyncMock()

        await sched.schedule({"c1", "c2"})

        engine.check_and_compact.assert_not_called()
        # query_batch should not even be called
        mock_state_client.query_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_character_ids(self, scheduler, engine, mock_state_client):
        """Empty character set → no-op."""
        engine.check_and_compact = AsyncMock()

        await scheduler.schedule(set())

        engine.check_and_compact.assert_not_called()
        mock_state_client.query_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_fewer_candidates_than_budget(self, scheduler, engine, mock_state_client):
        """2 candidates with budget 3 → both compacted."""
        char_ids = {"c1", "c2"}

        mock_state_client.query_batch.return_value = [
            {"tiers": {"events": 120, "summaries": 5, "digests": 3, "cores": 2}},
            {"tiers": {"events": 110, "summaries": 5, "digests": 3, "cores": 2}},
        ]

        engine.check_and_compact = AsyncMock()

        await scheduler.schedule(char_ids)

        assert engine.check_and_compact.call_count == 2

    @pytest.mark.asyncio
    async def test_check_and_compact_failure_continues(self, scheduler, engine, mock_state_client):
        """If check_and_compact fails for one character, others still run."""
        char_ids = {"fail", "ok"}
        id_list = sorted(char_ids)

        mock_state_client.query_batch.return_value = [
            {"tiers": {"events": 200, "summaries": 5, "digests": 3, "cores": 2}},
            {"tiers": {"events": 150, "summaries": 5, "digests": 3, "cores": 2}},
        ]

        call_log = []

        async def mock_compact(cid):
            call_log.append(cid)
            if cid == "ok":
                raise Exception("Boom")

        engine.check_and_compact = AsyncMock(side_effect=mock_compact)

        await scheduler.schedule(char_ids)

        # Both should have been attempted
        assert len(call_log) == 2


# ---------------------------------------------------------------------------
# Task 5.2 — Integration: 8 candidates budget 3 → only top 3 compacted
# ---------------------------------------------------------------------------

class TestSchedulerIntegration:
    """Higher-level integration tests for budget-pool scheduling."""

    @pytest.fixture
    def mock_state_client(self):
        client = MagicMock()
        client.query_batch = AsyncMock()
        client.mutate_batch = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def mock_llm_client(self):
        client = MagicMock()
        client.complete = AsyncMock(return_value="Compressed.")
        return client

    @pytest.fixture
    def engine(self, mock_state_client, mock_llm_client):
        return CompactionEngine(
            state_client=mock_state_client,
            llm_client=mock_llm_client,
        )

    @pytest.mark.asyncio
    async def test_eight_candidates_budget_three(self, engine, mock_state_client):
        """8 over-cap candidates with budget 3 → exactly 3 check_and_compact calls."""
        scheduler = CompactionScheduler(engine, budget=3)
        char_ids = {f"npc_{i}" for i in range(8)}

        # Varying scores
        mock_state_client.query_batch.return_value = [
            {"tiers": {"events": 100 + (i + 1) * 10, "summaries": 5, "digests": 3, "cores": 2}}
            for i in range(8)
        ]

        engine.check_and_compact = AsyncMock()

        await scheduler.schedule(char_ids)

        assert engine.check_and_compact.call_count == 3

    @pytest.mark.asyncio
    async def test_mixed_over_and_under_cap(self, engine, mock_state_client):
        """Mix of over-cap and under-cap → only over-cap compacted within budget."""
        scheduler = CompactionScheduler(engine, budget=3)
        char_ids = {"over1", "over2", "under1", "under2"}

        tier_map = {
            "over1": {"tiers": {"events": 150, "summaries": 5, "digests": 3, "cores": 2}},
            "over2": {"tiers": {"events": 120, "summaries": 5, "digests": 3, "cores": 2}},
            "under1": {"tiers": {"events": 50, "summaries": 5, "digests": 3, "cores": 2}},
            "under2": {"tiers": {"events": 80, "summaries": 5, "digests": 3, "cores": 2}},
        }

        id_list = sorted(char_ids)
        mock_state_client.query_batch.return_value = [tier_map[cid] for cid in id_list]

        engine.check_and_compact = AsyncMock()

        await scheduler.schedule(char_ids)

        # Only 2 characters are over cap
        assert engine.check_and_compact.call_count == 2

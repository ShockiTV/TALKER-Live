"""Tests for CompactionEngine (memory tier compression)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from talker_service.memory.compaction import (
    CompactionEngine,
    TIER_CAPS,
    COMPACTION_SIZES,
    create_compaction_task,
)


@pytest.fixture
def mock_state_client():
    """Mock StateQueryClient."""
    client = MagicMock()
    client.query_batch = AsyncMock()
    client.mutate_batch = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_llm_client():
    """Mock LLMClient."""
    client = MagicMock()
    client.complete = AsyncMock(return_value="Compressed summary text here.")
    return client


@pytest.fixture
def compaction_engine(mock_state_client, mock_llm_client):
    """CompactionEngine instance with mocked dependencies."""
    return CompactionEngine(
        state_client=mock_state_client,
        llm_client=mock_llm_client,
    )


class TestCompactionEngine:
    """Tests for CompactionEngine core functionality."""
    
    @pytest.mark.asyncio
    async def test_no_compaction_when_under_cap(self, compaction_engine, mock_state_client):
        """Test that compaction is skipped when all tiers are under cap."""
        # Mock tier counts - all under cap
        mock_state_client.query_batch.return_value = [
            {
                "tiers": {
                    "events": 50,      # Under 100 cap
                    "summaries": 5,    # Under 10 cap
                    "digests": 2,      # Under 5 cap
                    "cores": 2,        # Under 5 cap
                }
            }
        ]
        
        await compaction_engine.check_and_compact("char_001")
        
        # Should only query tiers, not mutate
        assert mock_state_client.query_batch.call_count == 1
        mock_state_client.mutate_batch.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_events_to_summaries_compaction(self, compaction_engine, mock_state_client, mock_llm_client):
        """Test events tier over cap triggers events→summaries compaction."""
        # Mock tier counts - events over cap
        mock_state_client.query_batch.side_effect = [
            # First call: get tier counts
            [{"tiers": {"events": 105, "summaries": 5, "digests": 2, "cores": 2}}],
        ]
        
        # Test the tier checking logic directly
        compaction_engine._compact_tier = AsyncMock()
        await compaction_engine._compact_character("char_001")
        
        # Should call compact_tier for events
        compaction_engine._compact_tier.assert_any_call(
            character_id="char_001",
            source_tier="events",
            target_tier="summaries",
        )
    
    @pytest.mark.asyncio
    async def test_summaries_to_digests_compaction(self, compaction_engine, mock_state_client):
        """Test summaries tier over cap triggers summaries→digests compaction."""
        mock_state_client.query_batch.return_value = [
            {"tiers": {"events": 50, "summaries": 12, "digests": 2, "cores": 2}}
        ]
        
        # Mock _compact_tier to prevent cascade
        compaction_engine._compact_tier = AsyncMock()
        
        await compaction_engine._compact_character("char_001")
        
        # Should call compact_tier for summaries (and cascade to digests, cores)
        compaction_engine._compact_tier.assert_any_call(
            character_id="char_001",
            source_tier="summaries",
            target_tier="digests",
        )
    
    @pytest.mark.asyncio
    async def test_digests_to_cores_compaction(self, compaction_engine, mock_state_client):
        """Test digests tier over cap triggers digests→cores compaction."""
        mock_state_client.query_batch.return_value = [
            {"tiers": {"events": 50, "summaries": 5, "digests": 7, "cores": 2}}
        ]
        
        compaction_engine._compact_tier = AsyncMock()
        
        await compaction_engine._compact_character("char_001")
        
        compaction_engine._compact_tier.assert_any_call(
            character_id="char_001",
            source_tier="digests",
            target_tier="cores",
        )
    
    @pytest.mark.asyncio
    async def test_cores_self_compact(self, compaction_engine, mock_state_client):
        """Test cores tier over cap triggers cores→cores self-compaction."""
        mock_state_client.query_batch.side_effect = [
            # Tier counts - cores over cap
            [{"tiers": {"events": 50, "summaries": 5, "digests": 2, "cores": 7}}],
            # Get cores
            [{
                "items": [
                    {"seq": 301, "text": "Core 1"},
                    {"seq": 302, "text": "Core 2"},
                ]
            }],
        ]
        
        await compaction_engine.check_and_compact("char_001")
        
        mutations = mock_state_client.mutate_batch.call_args[0][0]
        assert mutations[0]["resource"] == "memory.cores"
        assert mutations[1]["resource"] == "memory.cores"  # Self-compact
    
    @pytest.mark.asyncio
    async def test_cascade_compaction(self, compaction_engine, mock_state_client):
        """Test that compaction cascades when multiple tiers are over cap."""
        mock_state_client.query_batch.return_value = [
            {"tiers": {"events": 105, "summaries": 11, "digests": 2, "cores": 2}}
        ]
        
        compaction_engine._compact_tier = AsyncMock()
        
        await compaction_engine._compact_character("char_001")
        
        # Should call compact_tier for events, summaries, and cascade to digests/cores
        assert compaction_engine._compact_tier.call_count == 4  # All tiers
        compaction_engine._compact_tier.assert_any_call(
            character_id="char_001", source_tier="events", target_tier="summaries"
        )
        compaction_engine._compact_tier.assert_any_call(
            character_id="char_001", source_tier="summaries", target_tier="digests"
        )
    
    @pytest.mark.asyncio
    async def test_atomic_pattern_uses_seq_ids(self, compaction_engine, mock_state_client, mock_llm_client):
        """Test that delete uses explicit seq IDs (atomic pattern)."""
        # Provide tier counts + items for events tier only
        mock_state_client.query_batch.side_effect = [
            [{"tiers": {"events": 105, "summaries": 5, "digests": 2, "cores": 2}}],
            [{"items": [{"seq": i, "text": f"Event {i}"} for i in range(5, 15)]}],  # seqs 5-14
        ]
        
        # Mock remaining cascade queries to return empty
        def query_side_effect(*args, **kwargs):
            if mock_state_client.query_batch.call_count == 1:
                return [{"tiers": {"events": 105, "summaries": 5, "digests": 2, "cores": 2}}]
            elif mock_state_client.query_batch.call_count == 2:
                return [{"items": [{"seq": i, "text": f"Event {i}"} for i in range(5, 15)]}]
            else:
                # Cascade queries return empty
                return [{"items": []}]
        
        mock_state_client.query_batch.side_effect = query_side_effect
        
        await compaction_engine.check_and_compact("char_001")
        
        # Find the mutation call for events tier
        found = False
        for call in mock_state_client.mutate_batch.call_args_list:
            mutations = call[0][0]
            delete_mutation = mutations[0]
            if delete_mutation.get("resource") == "memory.events":
                # Should delete by explicit seq IDs
                assert delete_mutation["ids"] == list(range(5, 15))
                found = True
                break
        
        assert found, "Events tier mutation not found"
    
    @pytest.mark.asyncio
    async def test_skip_if_not_enough_items(self, compaction_engine, mock_state_client, mock_llm_client):
        """Test compaction skips if not enough items to compact."""
        # Return tier counts showing events over cap
        # Then return only 5 items for events (need 10 for events compaction)
        # Return empty for cascade tiers
        call_count = 0
        def query_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"tiers": {"events": 105, "summaries": 5, "digests": 2, "cores": 2}}]
            elif call_count == 2:
                # Events tier query - only 5 items (need 10)
                return [{"items": [{"seq": i, "text": f"Event {i}"} for i in range(1, 6)]}]
            else:
                # Cascade queries - no items
                return [{"items": []}]
        
        mock_state_client.query_batch.side_effect = query_side_effect
        
        await compaction_engine.check_and_compact("char_001")
        
        # Should not mutate since we don't have enough items for events tier
        # and cascade tiers have no items
        mock_state_client.mutate_batch.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_llm_failure_handled(self, compaction_engine, mock_state_client, mock_llm_client):
        """Test that LLM failure is handled gracefully."""
        def query_side_effect(*args, **kwargs):
            if mock_state_client.query_batch.call_count == 1:
                return [{"tiers": {"events": 105, "summaries": 5, "digests": 2, "cores": 2}}]
            elif mock_state_client.query_batch.call_count == 2:
                return [{"items": [{"seq": i, "text": f"Event {i}"} for i in range(1, 11)]}]
            else:
                # Cascade queries return empty
                return [{"items": []}]
        
        mock_state_client.query_batch.side_effect = query_side_effect
        
        # LLM fails
        mock_llm_client.complete.side_effect = Exception("LLM timeout")
        
        # Should not raise
        await compaction_engine.check_and_compact("char_001")
        
        # Should not mutate when LLM fails
        mock_state_client.mutate_batch.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_empty_llm_response_handled(self, compaction_engine, mock_state_client, mock_llm_client):
        """Test that empty LLM response is handled."""
        def query_side_effect(*args, **kwargs):
            if mock_state_client.query_batch.call_count == 1:
                return [{"tiers": {"events": 105, "summaries": 5, "digests": 2, "cores": 2}}]
            elif mock_state_client.query_batch.call_count == 2:
                return [{"items": [{"seq": i, "text": f"Event {i}"} for i in range(1, 11)]}]
            else:
                return [{"items": []}]
        
        mock_state_client.query_batch.side_effect = query_side_effect
        
        # LLM returns empty string
        mock_llm_client.complete.return_value = "   "
        
        await compaction_engine.check_and_compact("char_001")
        
        # Should not mutate when LLM returns empty
        mock_state_client.mutate_batch.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_concurrent_compaction_prevention(self, compaction_engine, mock_state_client, mock_llm_client):
        """Test that concurrent compaction for same character is prevented."""
        def query_side_effect(*args, **kwargs):
            if mock_state_client.query_batch.call_count <= 2:
                if mock_state_client.query_batch.call_count == 1:
                    return [{"tiers": {"events": 105, "summaries": 5, "digests": 2, "cores": 2}}]
                else:
                    return [{"items": [{"seq": i, "text": f"Event {i}"} for i in range(1, 11)]}]
            else:
                # Cascade queries return empty
                return [{"items": []}]
        
        mock_state_client.query_batch.side_effect = query_side_effect
        
        # Start two compactions concurrently
        import asyncio
        await asyncio.gather(
            compaction_engine.check_and_compact("char_001"),
            compaction_engine.check_and_compact("char_001"),
        )
        
        # Should prevent concurrent execution - only one should run
        # The exact count depends on whether the second call checks in
        # We just verify it's not doubled (should be ~2-7, not 8+)
        assert mock_state_client.query_batch.call_count <= 7


class TestCompactionPrompts:
    """Tests for compaction prompt generation."""
    
    def test_events_to_summary_prompt(self):
        """Test events→summary prompt construction."""
        from talker_service.prompts.compaction import build_compaction_prompt
        
        prompt = build_compaction_prompt(
            character_id="char_001",
            source_tier="events",
            source_texts=["Event 1", "Event 2", "Event 3"],
        )
        
        assert "compressing raw event records" in prompt.lower()
        assert "summary" in prompt.lower()
        assert "Event 1" in prompt
        assert "Event 2" in prompt
        assert "char_001" in prompt
        assert "third person" in prompt.lower()
    
    def test_summaries_to_digest_prompt(self):
        """Test summaries→digest prompt construction."""
        from talker_service.prompts.compaction import build_compaction_prompt
        
        prompt = build_compaction_prompt(
            character_id="char_002",
            source_tier="summaries",
            source_texts=["Summary A", "Summary B"],
        )
        
        assert "merging" in prompt.lower()
        assert "digest" in prompt.lower()
        assert "Summary A" in prompt
        assert "coherent narrative" in prompt.lower()
    
    def test_digests_to_core_prompt(self):
        """Test digests→core prompt construction."""
        from talker_service.prompts.compaction import build_compaction_prompt
        
        prompt = build_compaction_prompt(
            character_id="char_003",
            source_tier="digests",
            source_texts=["Digest X"],
        )
        
        assert "core memory" in prompt.lower()
        assert "most significant" in prompt.lower()
        assert "Digest X" in prompt
    
    def test_cores_self_compact_prompt(self):
        """Test cores→cores self-compact prompt."""
        from talker_service.prompts.compaction import build_compaction_prompt
        
        prompt = build_compaction_prompt(
            character_id="char_004",
            source_tier="cores",
            source_texts=["Core 1", "Core 2"],
        )
        
        assert "core memories" in prompt.lower()
        assert "critical experiences" in prompt.lower()
        assert "highest level of compression" in prompt.lower()


class TestCreateCompactionTask:
    """Tests for create_compaction_task helper."""
    
    @pytest.mark.asyncio
    async def test_creates_background_task(self, compaction_engine, mock_state_client):
        """Test that compaction task runs in background."""
        mock_state_client.query_batch.return_value = [
            {"tiers": {"events": 50, "summaries": 5, "digests": 2, "cores": 2}}
        ]
        
        # Create task
        task = create_compaction_task(compaction_engine, "char_001")
        
        # Task should be a Task
        import asyncio
        assert isinstance(task, asyncio.Task)
        
        # Wait for completion
        await task
        
        # Should have queried
        mock_state_client.query_batch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_task_exception_handled(self, compaction_engine, mock_state_client):
        """Test that task exceptions don't crash."""
        # Make query fail
        mock_state_client.query_batch.side_effect = Exception("Network error")
        
        # Create task
        task = create_compaction_task(compaction_engine, "char_001")
        
        # Should not raise even though query failed
        await task
        
        # Task completed (with error logged internally)
        assert task.done()


class TestTierConstants:
    """Tests for tier constants matching Lua."""
    
    def test_tier_caps_match_lua(self):
        """Test that Python TIER_CAPS match Lua CAPS."""
        # These values must match bin/lua/domain/repo/memory_store_v2.lua
        assert TIER_CAPS["events"] == 100
        assert TIER_CAPS["summaries"] == 10
        assert TIER_CAPS["digests"] == 5
        assert TIER_CAPS["cores"] == 5
    
    def test_compaction_sizes(self):
        """Test compaction batch sizes."""
        assert COMPACTION_SIZES["events"] == 10       # 10 events → 1 summary
        assert COMPACTION_SIZES["summaries"] == 2     # 2 summaries → 1 digest
        assert COMPACTION_SIZES["digests"] == 2       # 2 digests → 1 core
        assert COMPACTION_SIZES["cores"] == 2         # 2 cores → 1 core

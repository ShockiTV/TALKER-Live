"""
CompactionEngine - LLM-driven memory tier compression.

Implements four-tier compaction cascade:
- events (10) → 1 summary
- summaries (2) → 1 digest
- digests (2) → 1 core
- cores (2) → 1 core (self-compacting terminal tier)

Uses atomic delete+append pattern to eliminate race conditions.
"""

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from ..llm.models import Message

if TYPE_CHECKING:
    from ..llm.base import LLMClient
    from ..state.client import StateQueryClient


# Tier capacity thresholds (must match Lua CAPS)
TIER_CAPS = {
    "events": 100,
    "summaries": 10,
    "digests": 5,
    "cores": 5,
}

# Compaction batch sizes (how many items to merge per compaction)
COMPACTION_SIZES = {
    "events": 10,       # 10 events → 1 summary
    "summaries": 2,     # 2 summaries → 1 digest
    "digests": 2,       # 2 digests → 1 core
    "cores": 2,         # 2 cores → 1 core (self-compact)
}


class CompactionEngine:
    """Manages memory tier compaction using LLM-driven compression.
    
    Compaction runs as a background task when tier caps are exceeded.
    Uses atomic delete+append pattern to avoid race conditions.
    """
    
    def __init__(
        self,
        state_client: "StateQueryClient",
        llm_client: "LLMClient",
    ):
        """
        Args:
            state_client: Client for querying and mutating game state
            llm_client: LLM client (should be the fast/cheap model)
        """
        self.state_client = state_client
        self.llm_client = llm_client
        
        # Track active compactions to prevent concurrent runs for same character
        self._active_compactions: set[str] = set()
        self._lock = asyncio.Lock()
    
    async def check_and_compact(self, character_id: str) -> None:
        """Check if compaction is needed for a character and run it if so.
        
        This is the entry point called after events are stored.
        Runs as a background task (non-blocking).
        
        Args:
            character_id: Character to check for compaction
        """
        # Skip if already compacting for this character
        async with self._lock:
            if character_id in self._active_compactions:
                logger.debug(f"Compaction already running for {character_id}, skipping")
                return
            self._active_compactions.add(character_id)
        
        try:
            await self._compact_character(character_id)
        finally:
            async with self._lock:
                self._active_compactions.discard(character_id)
    
    async def _compact_character(self, character_id: str) -> None:
        """Run compaction cascade for a character.
        
        Checks each tier in order and cascades as needed:
        1. events → summaries
        2. summaries → digests
        3. digests → cores
        4. cores → cores (self-compact)
        
        Args:
            character_id: Character to compact
        """
        # Query current tier counts
        result = await self.state_client.query_batch([
            {"query": "npc.memories.tiers", "character_id": character_id}
        ])
        
        if not result or not result[0].get("tiers"):
            logger.debug(f"No memory tiers found for {character_id}")
            return
        
        tiers = result[0]["tiers"]
        
        # Check and compact each tier (cascade order)
        cascaded = False
        
        # Events → Summaries
        if tiers.get("events", 0) > TIER_CAPS["events"]:
            await self._compact_tier(
                character_id=character_id,
                source_tier="events",
                target_tier="summaries",
            )
            cascaded = True
        
        # Summaries → Digests
        if cascaded or tiers.get("summaries", 0) > TIER_CAPS["summaries"]:
            await self._compact_tier(
                character_id=character_id,
                source_tier="summaries",
                target_tier="digests",
            )
            cascaded = True
        
        # Digests → Cores
        if cascaded or tiers.get("digests", 0) > TIER_CAPS["digests"]:
            await self._compact_tier(
                character_id=character_id,
                source_tier="digests",
                target_tier="cores",
            )
            cascaded = True
        
        # Cores → Cores (self-compact)
        if cascaded or tiers.get("cores", 0) > TIER_CAPS["cores"]:
            await self._compact_tier(
                character_id=character_id,
                source_tier="cores",
                target_tier="cores",
            )
    
    async def _compact_tier(
        self,
        character_id: str,
        source_tier: str,
        target_tier: str,
    ) -> None:
        """Compact a single tier using the atomic delete+append pattern.
        
        Steps:
        1. Read N oldest items from source tier (with their seqs)
        2. Call LLM to compress into single item
        3. Send state.mutate.batch: delete source items + append result to target
        
        Args:
            character_id: Character ID
            source_tier: Source tier name (events, summaries, digests, cores)
            target_tier: Target tier name (summaries, digests, cores, cores)
        """
        batch_size = COMPACTION_SIZES.get(source_tier, 2)
        
        # Step 1: Read source items
        result = await self.state_client.query_batch([
            {
                "query": "npc.memories.tier",
                "character_id": character_id,
                "tier": source_tier,
                "limit": batch_size,
            }
        ])
        
        if not result or not result[0].get("items"):
            logger.debug(f"No {source_tier} items found for {character_id}")
            return
        
        source_items = result[0]["items"]
        if len(source_items) < batch_size:
            logger.debug(
                f"Not enough {source_tier} items for {character_id} "
                f"({len(source_items)}/{batch_size}), skipping compaction"
            )
            return
        
        # Extract seqs and texts
        seqs = [item["seq"] for item in source_items]
        texts = [item.get("text", "") for item in source_items]
        
        logger.info(
            f"Compacting {len(source_items)} {source_tier} for {character_id} "
            f"(seqs {min(seqs)}-{max(seqs)})"
        )
        
        # Step 2: Call LLM to compress
        from ..prompts.compaction import build_compaction_prompt
        
        prompt = build_compaction_prompt(
            character_id=character_id,
            source_tier=source_tier,
            source_texts=texts,
        )
        
        try:
            compressed_text = await self.llm_client.complete([
                Message(role="system", content=prompt)
            ])
        except Exception as e:
            logger.error(f"LLM compaction failed for {character_id} {source_tier}: {e}")
            return
        
        if not compressed_text or not compressed_text.strip():
            logger.warning(f"LLM returned empty compaction for {character_id} {source_tier}")
            return
        
        # Step 3: Atomic delete+append mutation
        max_seq = max(seqs)
        
        mutations = [
            # Delete source items by seq_lte
            {
                "character_id": character_id,
                "verb": "delete",
                "resource": source_tier,
                "data": {"seq_lte": max_seq},
            },
            # Append compressed result to target tier
            {
                "character_id": character_id,
                "verb": "append",
                "resource": target_tier,
                "data": {"text": compressed_text.strip()},
            },
        ]
        
        # Send mutation batch
        success = await self.state_client.mutate_batch(mutations)
        
        if success:
            logger.info(
                f"Compacted {len(source_items)} {source_tier} → {target_tier} for {character_id} "
                f"({len(compressed_text)} chars)"
            )
        else:
            logger.error(f"Mutation failed for {character_id} {source_tier} compaction")


def create_compaction_task(
    engine: CompactionEngine,
    character_id: str,
) -> asyncio.Task:
    """Create a background compaction task (non-blocking helper).
    
    Args:
        engine: CompactionEngine instance
        character_id: Character to compact
    
    Returns:
        Asyncio task
    """
    async def _wrapper():
        try:
            await engine.check_and_compact(character_id)
        except Exception:
            logger.opt(exception=True).error(
                f"Compaction task failed for {character_id}"
            )
    
    return asyncio.create_task(_wrapper())

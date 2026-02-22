"""Main dialogue generation orchestrator."""

import asyncio
from typing import Any, Callable, Protocol

from loguru import logger

from .speaker import SpeakerSelector
from .cleaner import clean_dialogue, extract_speaker_id
from .retry_queue import DialogueRetryQueue, get_retry_attempt

from ..llm import LLMClient, Message, LLMOptions
from ..state.batch import BatchQuery
from ..state.client import StateQueryTimeout
from ..prompts import (
    create_dialogue_request_prompt,
    create_pick_speaker_prompt,
    create_compress_memories_prompt,
    create_update_narrative_prompt,
    Character,
    Event,
    MemoryContext,
)
from ..prompts.world_context import build_world_context, get_all_story_ids
from ..state.models import SceneContext


# Memory compression threshold
COMPRESSION_THRESHOLD = 12


class StateQueryProtocol(Protocol):
    """Protocol for state query client."""
    
    async def execute_batch(self, batch: Any, *, timeout: float | None = None) -> Any: ...


class ZMQPublisherProtocol(Protocol):
    """Protocol for ZMQ publishing."""
    
    async def publish(self, topic: str, payload: dict[str, Any]) -> bool: ...


# Type for LLM client factory function
LLMClientFactory = Callable[[], LLMClient]


class DialogueGenerator:
    """Orchestrates dialogue generation flow.
    
    Flow:
    1. Receive game event
    2. Pick speaker (with cooldown filtering)
    3. Query memory context
    4. Check if memory compression needed
    5. Build prompt and generate dialogue
    6. Publish dialogue.display command
    7. Update memory if needed
    """
    
    def __init__(
        self,
        llm_client: LLMClient | LLMClientFactory,
        state_client: StateQueryProtocol,
        publisher: ZMQPublisherProtocol,
        speaker_selector: SpeakerSelector | None = None,
        llm_timeout: float = 60.0,
        retry_queue: DialogueRetryQueue | None = None,
    ):
        """Initialize dialogue generator.
        
        Args:
            llm_client: LLM client or factory function that returns one
            state_client: State query client for game state
            publisher: ZMQ publisher for sending commands
            speaker_selector: Optional speaker selector (created if None)
            llm_timeout: Timeout for LLM calls in seconds
            retry_queue: Optional retry queue for deferring transient failures.
                When provided, StateQueryTimeout errors are enqueued for retry
                instead of being silently discarded.
        """
        # Store either a fixed client or a factory
        if callable(llm_client) and not isinstance(llm_client, LLMClient):
            self._llm_factory: LLMClientFactory | None = llm_client
            self._llm_client: LLMClient | None = None
        else:
            self._llm_factory = None
            self._llm_client = llm_client
            
        self.state = state_client
        self.publisher = publisher
        self.speakers = speaker_selector or SpeakerSelector()
        self.llm_timeout = llm_timeout
        self.retry_queue = retry_queue
        
        # Lock to prevent concurrent memory updates for same character
        self._memory_locks: dict[str, asyncio.Lock] = {}
    
    @property
    def llm(self) -> LLMClient:
        """Get the current LLM client (from factory if configured)."""
        if self._llm_factory:
            return self._llm_factory()
        return self._llm_client
    
    def _get_memory_lock(self, character_id: str) -> asyncio.Lock:
        """Get or create a memory lock for a character."""
        if character_id not in self._memory_locks:
            self._memory_locks[character_id] = asyncio.Lock()
        return self._memory_locks[character_id]
    
    async def generate_from_event(
        self,
        event: dict[str, Any],
        is_important: bool = False
    ) -> None:
        """Generate dialogue in response to a game event.
        
        Args:
            event: Game event dict
            is_important: Whether event should always trigger dialogue
        """
        logger.info(f"Generating dialogue from event: {event.get('type', 'legacy')}")
        
        # Get witnesses from event
        witnesses = event.get("witnesses", [])
        if not witnesses:
            logger.debug("No witnesses in event, skipping dialogue")
            return
        
        # Get current game time from event
        current_time_ms = event.get("game_time_ms", 0)
        
        # Pick speaker
        try:
            speaker_id = await self._pick_speaker(event, witnesses, current_time_ms)
        except StateQueryTimeout as e:
            if self.retry_queue:
                attempt = get_retry_attempt(event)
                logger.warning(
                    f"State query timeout during speaker selection, "
                    f"deferring to retry queue (attempt {attempt}): {e}"
                )
                self.retry_queue.enqueue("event", event, attempt_count=attempt)
            else:
                logger.error(f"Speaker selection failed (no retry queue): {e}")
            return
        if not speaker_id:
            logger.debug("No speaker selected, skipping dialogue")
            return
        
        # Set cooldown
        self.speakers.set_spoke(speaker_id, current_time_ms)
        
        # Generate and display dialogue
        try:
            await self._generate_dialogue_for_speaker(speaker_id, event)
        except StateQueryTimeout as e:
            if self.retry_queue:
                attempt = get_retry_attempt(event)
                logger.warning(
                    f"State query timeout during event dialogue, "
                    f"deferring to retry queue (attempt {attempt}): {e}"
                )
                self.retry_queue.enqueue("event", event, attempt_count=attempt)
            else:
                logger.error(f"Dialogue generation failed (no retry queue): {e}")
    
    async def generate_from_instruction(
        self,
        speaker_id: str,
        event: dict[str, Any]
    ) -> None:
        """Generate dialogue for a specific speaker (bypass speaker selection).
        
        Used for idle conversations and directed dialogue.
        
        Args:
            speaker_id: Character ID who should speak
            event: Event context
        """
        logger.info(f"Generating dialogue from instruction for speaker {speaker_id}")
        
        current_time_ms = event.get("game_time_ms", 0)
        
        # Check if speaker spoke too recently
        last_spoke = self.speakers.get_last_spoke_time(speaker_id)
        if last_spoke and (current_time_ms - last_spoke) < self.speakers.cooldown_ms:
            logger.debug(f"Speaker {speaker_id} spoke too recently, skipping")
            return
        
        # Set cooldown
        self.speakers.set_spoke(speaker_id, current_time_ms)
        
        # Generate and display dialogue
        try:
            await self._generate_dialogue_for_speaker(speaker_id, event)
        except StateQueryTimeout as e:
            if self.retry_queue:
                attempt = get_retry_attempt(event)
                logger.warning(
                    f"State query timeout during instruction dialogue, "
                    f"deferring to retry queue (attempt {attempt}): {e}"
                )
                self.retry_queue.enqueue(
                    "instruction", event,
                    speaker_id=speaker_id, attempt_count=attempt,
                )
            else:
                logger.error(f"Dialogue generation failed (no retry queue): {e}")
    
    async def _pick_speaker(
        self,
        event: dict[str, Any],
        witnesses: list[dict[str, Any]],
        current_time_ms: int
    ) -> str | None:
        """Pick a speaker from witnesses.
        
        Args:
            event: Event context
            witnesses: List of witness dicts
            current_time_ms: Current game time
            
        Returns:
            Speaker ID or None if no speaker selected
        """
        # Filter out player (game_id 0)
        candidates = [w for w in witnesses if str(w.get("game_id", "")) != "0"]
        if not candidates:
            logger.debug("No non-player witnesses")
            return None
        
        # Player-directed events (is_dialogue flag) bypass cooldown so the NPC
        # always responds when the player explicitly speaks to them.
        flags = event.get("flags", {})
        is_player_directed = flags.get("is_dialogue", False)

        if is_player_directed:
            available = candidates
            logger.debug("Player-directed event — skipping cooldown filter")
        else:
            # Filter by cooldown
            available = self.speakers.filter_by_cooldown(candidates, current_time_ms)
            if not available:
                logger.debug("All speakers on cooldown")
                return None
        
        # If only one speaker, return them directly
        if len(available) == 1:
            return str(available[0].get("game_id", ""))
        
        # Use LLM to pick speaker
        try:
            # Convert witnesses from dicts to Character objects
            prompt_witnesses = [
                Character(
                    game_id=str(w.get("game_id", "")),
                    name=w.get("name", "Unknown"),
                    faction=w.get("faction", "stalker"),
                    experience=w.get("experience", "Experienced"),
                    reputation=w.get("reputation", 0),
                    personality=w.get("personality", ""),
                )
                for w in available
            ]
            
            # Build recent events list (use event as single item for now)
            prompt_events = [Event.from_dict(event)]
            
            prompt_messages = create_pick_speaker_prompt(prompt_events, prompt_witnesses)
            messages = [Message(role=m.role, content=m.content) for m in prompt_messages]
            
            response = await self.llm.complete(
                messages,
                LLMOptions(temperature=0.3, max_tokens=50, timeout=self.llm_timeout)
            )
            
            speaker_id = extract_speaker_id(response)
            
            if speaker_id:
                # Validate speaker is in available list
                valid_ids = {str(w.get("game_id", "")) for w in available}
                if speaker_id in valid_ids:
                    return speaker_id
                else:
                    logger.warning(f"LLM picked invalid speaker {speaker_id}")
            
            # Fallback to first available
            return str(available[0].get("game_id", ""))
            
        except Exception as e:
            logger.error(f"Speaker selection failed: {e}")
            # Fallback to first available
            return str(available[0].get("game_id", ""))
    
    async def _generate_dialogue_for_speaker(
        self,
        speaker_id: str,
        event: dict[str, Any]
    ) -> None:
        """Generate and display dialogue for a speaker.
        
        Uses a single batch query to fetch memories, character data,
        world context, and alive status in one ZMQ roundtrip.
        
        Args:
            speaker_id: Character ID
            event: Event context
        """
        try:
            # Gather all story IDs for alive check
            story_ids = get_all_story_ids()
            
            # Single batch query for all needed state.
            # store.memories is queried first so its last_update_time_ms can be
            # $ref'd by the store.events filter in the same roundtrip.
            batch = (
                BatchQuery()
                .add("mem", "store.memories", params={"character_id": speaker_id})
                .add("events", "store.events",
                     filter={
                         "game_time_ms": {"$gt": BatchQuery.ref("mem", "last_update_time_ms")},
                         "witnesses": {"$elemMatch": {"game_id": speaker_id}},
                     })
                .add("char", "query.character", params={"id": speaker_id})
                .add("world", "query.world")
            )
            if story_ids:
                batch.add("alive", "query.characters_alive", params={"ids": story_ids})
            
            result = await self.state.execute_batch(batch)
            
            # Manually construct MemoryContext from separate mem + events results
            mem_data = result["mem"]
            events_data = result["events"] if result.ok("events") else []
            new_events = [Event.from_dict(e) for e in events_data] if isinstance(events_data, list) else []
            memory_ctx = MemoryContext(
                narrative=mem_data.get("narrative"),
                last_update_time_ms=mem_data.get("last_update_time_ms", 0),
                new_events=new_events,
            )
            character = Character.from_dict(result["char"])
            
            # Check if memory compression needed (run in background)
            asyncio.create_task(
                self._maybe_compress_memory(speaker_id, memory_ctx)
            )
            
            # Build scene context dict from world query result
            scene_context = None
            world_state_context = ""
            try:
                scene_ctx = SceneContext.from_dict(result["world"])
                scene_context = {
                    "loc": scene_ctx.loc,
                    "poi": scene_ctx.poi,
                    "time": scene_ctx.time,
                    "weather": scene_ctx.weather,
                    "emission": scene_ctx.emission,
                    "psy_storm": scene_ctx.psy_storm,
                    "sheltering": scene_ctx.sheltering,
                    "campfire": scene_ctx.campfire,
                    "brain_scorcher_disabled": scene_ctx.brain_scorcher_disabled,
                    "miracle_machine_disabled": scene_ctx.miracle_machine_disabled,
                }
                
                # Get alive status from batch result (if available)
                alive_status = result["alive"] if story_ids and result.ok("alive") else {}
                
                # Build world state context using pre-fetched alive data
                try:
                    world_state_context = await build_world_context(
                        scene_ctx,
                        recent_events=memory_ctx.new_events,
                        alive_status=alive_status,
                    )
                except Exception as e:
                    logger.warning(f"Failed to build world context: {e}")
                    world_state_context = ""
            except Exception as e:
                logger.warning(f"Failed to parse scene context: {e}")
            
            prompt_memory = MemoryContext(
                narrative=memory_ctx.narrative,
                last_update_time_ms=memory_ctx.last_update_time_ms,
                new_events=[
                    *memory_ctx.new_events,
                    Event.from_dict(event),  # Add input event as most recent
                ],
            )
            
            # Build dialogue prompt with scene and world context
            prompt_messages, timestamp_to_delete = create_dialogue_request_prompt(
                character,
                prompt_memory,
                scene_context=scene_context,
                world_state_context=world_state_context,
            )
            
            # Convert prompt Message objects to LLM Message objects
            messages = [Message(role=m.role, content=m.content) for m in prompt_messages]
            
            # Generate dialogue
            response = await self.llm.complete(
                messages,
                LLMOptions(temperature=0.8, max_tokens=200, timeout=self.llm_timeout)
            )
            
            dialogue = clean_dialogue(response)
            
            if not dialogue:
                logger.warning("Generated empty dialogue after cleaning")
                return
            
            # Publish dialogue.display command
            await self._publish_dialogue(speaker_id, dialogue, event)
            
        except StateQueryTimeout:
            # Let StateQueryTimeout propagate to callers for retry handling
            raise
        except Exception as e:
            logger.error(f"Dialogue generation failed: {e}")
    
    async def _maybe_compress_memory(
        self,
        speaker_id: str,
        memory_ctx: Any
    ) -> None:
        """Check if memory compression is needed and trigger if so.
        
        Args:
            speaker_id: Character ID
            memory_ctx: Memory context from state query
        """
        if not memory_ctx.new_events:
            return
        
        if len(memory_ctx.new_events) < COMPRESSION_THRESHOLD:
            return
        
        lock = self._get_memory_lock(speaker_id)
        if lock.locked():
            logger.debug(f"Memory update already in progress for {speaker_id}")
            return
        
        async with lock:
            await self._compress_memory(speaker_id, memory_ctx)
    
    async def _compress_memory(
        self,
        speaker_id: str,
        memory_ctx: Any
    ) -> None:
        """Compress memories and update narrative.
        
        Args:
            speaker_id: Character ID
            memory_ctx: Memory context from state query
        """
        logger.info(f"Compressing memories for {speaker_id}")
        
        try:
            # Get character for prompt via batch query
            batch = BatchQuery().add("char", "query.character", params={"id": speaker_id})
            result = await self.state.execute_batch(batch)
            character = Character.from_dict(result["char"])
            
            # Events from state query are already correct type
            prompt_events = memory_ctx.new_events
            
            current_narrative = memory_ctx.narrative
            
            if not current_narrative:
                # Bootstrap: Use compression prompt
                prompt_messages = create_compress_memories_prompt(prompt_events, character)
            else:
                # Update existing narrative
                prompt_messages = create_update_narrative_prompt(
                    character,
                    current_narrative,
                    prompt_events
                )
            
            # Convert prompt Message objects to LLM Message objects
            messages = [Message(role=m.role, content=m.content) for m in prompt_messages]
            
            response = await self.llm.complete(
                messages,
                LLMOptions(temperature=0.3, max_tokens=2000, timeout=self.llm_timeout)
            )
            
            new_narrative = response.strip()
            
            if not new_narrative:
                logger.warning("Generated empty narrative")
                return
            
            # Get timestamp from newest event
            newest_time = max(e.game_time_ms for e in memory_ctx.new_events)
            
            # Publish memory.update command
            await self.publisher.publish("memory.update", {
                "character_id": speaker_id,
                "narrative": new_narrative,
                "last_event_time_ms": newest_time,
            })
            
            logger.info(f"Memory updated for {speaker_id}, length: {len(new_narrative)}")
            
        except Exception as e:
            logger.error(f"Memory compression failed: {e}")
    
    async def _publish_dialogue(
        self,
        speaker_id: str,
        dialogue: str,
        event: dict[str, Any]
    ) -> None:
        """Publish dialogue.display command.
        
        Args:
            speaker_id: Character ID
            dialogue: Cleaned dialogue text
            event: Original event context
        """
        payload = {
            "speaker_id": speaker_id,
            "dialogue": dialogue,
            "create_event": True,
            "event_context": {
                "world_context": event.get("world_context", ""),
            },
        }
        
        success = await self.publisher.publish("dialogue.display", payload)
        if success:
            logger.info(f"Published dialogue for {speaker_id}: {dialogue[:50]}...")
        else:
            logger.error("Failed to publish dialogue command")

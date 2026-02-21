"""Event handlers for game events, player input, and heartbeat."""

import asyncio
import random
import time
from datetime import datetime
from typing import Any, Optional, Protocol, TYPE_CHECKING

from loguru import logger

from ..models.messages import GameEventMessage, PlayerDialogueMessage, HeartbeatMessage

if TYPE_CHECKING:
    from ..dialogue import DialogueGenerator
    from ..dialogue.retry_queue import DialogueRetryQueue


class PublisherProtocol(Protocol):
    """Protocol for ZMQ publisher."""
    async def publish(self, topic: str, payload: dict[str, Any]) -> bool: ...


# Track last heartbeat for health check
_last_heartbeat: Optional[datetime] = None
_last_heartbeat_game_time: Optional[int] = None

# Dialogue generator (injected by main)
_dialogue_generator: Optional["DialogueGenerator"] = None

# Publisher for sending heartbeat acks (injected by main)
_publisher: Optional[PublisherProtocol] = None

# Retry queue for deferred dialogue generation (injected by main)
_retry_queue: Optional["DialogueRetryQueue"] = None

# Base probability for dialogue generation
BASE_DIALOGUE_CHANCE = 0.25


def set_dialogue_generator(generator: "DialogueGenerator") -> None:
    """Set the dialogue generator instance."""
    global _dialogue_generator
    _dialogue_generator = generator
    logger.info("Dialogue generator injected into event handlers")


def set_publisher(publisher: PublisherProtocol) -> None:
    """Set the publisher instance for sending heartbeat acks."""
    global _publisher
    _publisher = publisher
    logger.info("Publisher injected into event handlers")


def set_retry_queue(queue: "DialogueRetryQueue") -> None:
    """Set the retry queue instance for heartbeat-aware flush."""
    global _retry_queue
    _retry_queue = queue
    logger.info("Retry queue injected into event handlers")


def get_last_heartbeat() -> Optional[str]:
    """Get last heartbeat timestamp as ISO string."""
    if _last_heartbeat is None:
        return None
    return _last_heartbeat.isoformat()


def _should_someone_speak(event: GameEventMessage, is_important: bool) -> bool:
    """Determine if someone should speak in response to an event.
    
    Args:
        event: The game event
        is_important: Whether the event was marked important
        
    Returns:
        True if dialogue should be generated
    """
    # Filter out silent events
    flags = event.get_flags()
    if flags.get("is_silent", False):
        logger.debug("Event is silent, no dialogue")
        return False
    
    # Always respond to important events
    if is_important:
        return True
    
    # Check if player is the only witness (no one to speak)
    witnesses = event.witnesses or []
    non_player_witnesses = [w for w in witnesses if str(w.game_id) != "0"]
    if len(non_player_witnesses) == 0:
        logger.debug("No non-player witnesses, no dialogue")
        return False
    
    # Random chance for non-important events
    return random.random() < BASE_DIALOGUE_CHANCE


async def handle_game_event(payload: dict[str, Any]) -> None:
    """Handle incoming game event from Lua.
    
    Parses the event and triggers dialogue generation if appropriate.
    
    Payload structure from Lua:
    {
        "event": { type, content, game_time_ms, world_context, witnesses, flags, ... },
        "is_important": bool
    }
    """
    try:
        # Extract event from payload wrapper
        event_data = payload.get("event", payload)
        is_important = payload.get("is_important", False)
        
        event = GameEventMessage(**event_data)
        
        event_type = event.type or "UNKNOWN"
        witnesses_count = len(event.witnesses)
        flags = event.get_flags()
        
        # Log event details
        logger.info(
            f"Game Event: type={event_type}, "
            f"witnesses={witnesses_count}, "
            f"game_time={event.game_time_ms}, "
            f"important={is_important}, "
            f"flags={flags}"
        )
        
        # Log context details at debug level
        if event.context:
            logger.debug(f"Event context: {event.context}")
        if event.world_context:
            logger.debug(f"World context: {event.world_context}")
        if event.witnesses:
            witness_names = [w.name for w in event.witnesses]
            logger.debug(f"Witnesses: {witness_names}")
        
        # Check if dialogue should be generated
        if not _should_someone_speak(event, is_important):
            logger.debug("Skipping dialogue generation for this event")
            return
        
        # Handle idle conversation events (direct instruction)
        if flags.get("is_idle", False):
            # Spawn as background task to avoid blocking message loop
            asyncio.create_task(_handle_idle_event(event))
            return
        
        # Regular event-triggered dialogue
        # Spawn as background task to avoid blocking message loop
        asyncio.create_task(_handle_regular_event(event))
            
    except Exception as e:
        logger.error(f"Error processing game event: {e}")
        logger.debug(f"Raw payload: {payload}")


async def _handle_idle_event(event: GameEventMessage) -> None:
    """Handle idle conversation event (direct instruction to speak)."""
    if _dialogue_generator is None:
        logger.warning("Dialogue generator not available for idle event")
        return
    
    # Convert context to dict (EventContext is a Pydantic model)
    context_dict = {}
    if event.context:
        if hasattr(event.context, "model_dump"):
            context_dict = event.context.model_dump()
        elif isinstance(event.context, dict):
            context_dict = event.context
    
    # Get the speaker from context
    speaker_id = None
    actor = context_dict.get("actor")
    if actor and isinstance(actor, dict):
        speaker_id = str(actor.get("game_id"))
    
    if not speaker_id:
        logger.error("Idle event has no valid speaker")
        return
    
    logger.info(f"Triggering idle dialogue for speaker {speaker_id}")
    
    # Convert to dict format expected by generator
    event_dict = {
        "type": event.type,
        "context": context_dict,
        "game_time_ms": event.game_time_ms,
        "world_context": event.world_context,
        "witnesses": [{"game_id": w.game_id, "name": w.name, "faction": w.faction} 
                      for w in event.witnesses],
        "flags": event.get_flags(),
    }
    
    await _dialogue_generator.generate_from_instruction(speaker_id, event_dict)


async def _handle_regular_event(event: GameEventMessage) -> None:
    """Handle regular event-triggered dialogue."""
    if _dialogue_generator is None:
        logger.warning("Dialogue generator not available for event")
        return
    
    logger.info(f"Triggering dialogue generation for event type={event.type}")
    
    # Convert context to dict (EventContext is a Pydantic model)
    context_dict = {}
    if event.context:
        if hasattr(event.context, "model_dump"):
            context_dict = event.context.model_dump()
        elif isinstance(event.context, dict):
            context_dict = event.context
    
    # Convert to dict format expected by generator
    event_dict = {
        "type": event.type,
        "context": context_dict,
        "game_time_ms": event.game_time_ms,
        "world_context": event.world_context,
        "witnesses": [{"game_id": w.game_id, "name": w.name, "faction": w.faction,
                       "experience": getattr(w, "experience", ""),
                       "reputation": getattr(w, "reputation", "")} 
                      for w in event.witnesses],
        "flags": event.get_flags(),
    }
    
    await _dialogue_generator.generate_from_event(event_dict)


async def handle_player_dialogue(payload: dict[str, Any]) -> None:
    """Handle player dialogue input from Lua.
    
    Phase 1: Just log the input.
    Phase 2+: Will trigger AI response generation.
    """
    try:
        msg = PlayerDialogueMessage(**payload)
        
        logger.info(f"Player Dialogue: \"{msg.text}\"")
        if msg.context:
            logger.debug(f"Dialogue context: {msg.context}")
            
    except Exception as e:
        logger.error(f"Error processing player dialogue: {e}")
        logger.debug(f"Raw payload: {payload}")


async def handle_player_whisper(payload: dict[str, Any]) -> None:
    """Handle player whisper input from Lua.
    
    Phase 1: Just log the input.
    Phase 2+: Will trigger AI response generation with whisper mode.
    """
    try:
        msg = PlayerDialogueMessage(**payload)
        
        logger.info(f"Player Whisper: \"{msg.text}\"")
        if msg.context:
            logger.debug(f"Whisper context: {msg.context}")
            
    except Exception as e:
        logger.error(f"Error processing player whisper: {e}")
        logger.debug(f"Raw payload: {payload}")


async def handle_heartbeat(payload: dict[str, Any]) -> None:
    """Handle heartbeat message from Lua.
    
    Updates last_seen timestamp for health monitoring, sends ack back,
    and checks for connectivity gap to trigger retry queue flush.
    """
    global _last_heartbeat, _last_heartbeat_game_time
    
    try:
        msg = HeartbeatMessage(**payload)
        
        _last_heartbeat = datetime.now()
        _last_heartbeat_game_time = msg.game_time_ms
        
        # Only log heartbeats if explicitly enabled (reduces log noise)
        from ..config import settings
        if settings.log_heartbeat:
            logger.debug(
                f"Heartbeat received: alive={msg.alive}, "
                f"game_time={msg.game_time_ms}"
            )
        
        # Check retry queue for heartbeat gap (Lua recovered from pause)
        if _retry_queue and _dialogue_generator:
            should_flush = _retry_queue.notify_heartbeat(time.time())
            if should_flush:
                logger.info("Flushing retry queue after heartbeat gap")
                _retry_queue.flush(_dialogue_generator)
        
        # Send heartbeat acknowledgement back to Lua so it knows we're alive
        if _publisher:
            await _publisher.publish("service.heartbeat.ack", {
                "status": "alive",
                "timestamp": datetime.now().isoformat(),
            })
        
    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
        logger.debug(f"Raw payload: {payload}")

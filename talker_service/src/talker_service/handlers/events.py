"""Event handlers for game events, player input, and heartbeat."""

from datetime import datetime
from typing import Any, Optional

from loguru import logger

from ..models.messages import GameEventMessage, PlayerDialogueMessage, HeartbeatMessage


# Track last heartbeat for health check
_last_heartbeat: Optional[datetime] = None
_last_heartbeat_game_time: Optional[int] = None


def get_last_heartbeat() -> Optional[str]:
    """Get last heartbeat timestamp as ISO string."""
    if _last_heartbeat is None:
        return None
    return _last_heartbeat.isoformat()


async def handle_game_event(payload: dict[str, Any]) -> None:
    """Handle incoming game event from Lua.
    
    Phase 1: Just log the event for debugging.
    Phase 2+: Will trigger AI dialogue generation.
    
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
        flags = event.get_flags()  # Use helper to handle Lua's empty table as []
        
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
            
    except Exception as e:
        logger.error(f"Error processing game event: {e}")
        logger.debug(f"Raw payload: {payload}")


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
    
    Updates last_seen timestamp for health monitoring.
    """
    global _last_heartbeat, _last_heartbeat_game_time
    
    try:
        msg = HeartbeatMessage(**payload)
        
        _last_heartbeat = datetime.now()
        _last_heartbeat_game_time = msg.game_time_ms
        
        logger.debug(
            f"Heartbeat received: alive={msg.alive}, "
            f"game_time={msg.game_time_ms}"
        )
        
    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
        logger.debug(f"Raw payload: {payload}")

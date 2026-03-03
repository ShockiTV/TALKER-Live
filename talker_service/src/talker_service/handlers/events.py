"""Event handlers for game events, player input, and heartbeat."""

import asyncio
import base64
import time
from datetime import datetime
from typing import Any, Optional, Protocol, TYPE_CHECKING

from loguru import logger

from ..models.messages import GameEventMessage, PlayerDialogueMessage, HeartbeatMessage
from ._log import log_prefix

# Maximum concurrent dialogue generation tasks
_MAX_CONCURRENT_DIALOGUES = 3
_dialogue_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_DIALOGUES)


def _logged_task(coro, *, name: str = "unnamed"):
    """Create an asyncio task that logs exceptions instead of swallowing them."""
    async def _wrapper():
        try:
            await coro
        except Exception:
            logger.opt(exception=True).error(f"Background task '{name}' failed")
    return asyncio.create_task(_wrapper(), name=name)

if TYPE_CHECKING:
    from ..dialogue.conversation import ConversationManager


class PublisherProtocol(Protocol):
    """Protocol for ZMQ publisher."""
    async def publish(self, topic: str, payload: dict[str, Any], *, session: str | None = None) -> bool: ...


# Track last heartbeat for health check
_last_heartbeat: Optional[datetime] = None
_last_heartbeat_game_time: Optional[int] = None

# Conversation manager (injected by main)
_conversation_manager: Optional["ConversationManager"] = None

# Publisher for sending heartbeat acks (injected by main)
_publisher: Optional[PublisherProtocol] = None

# TTS engine (injected by main — TTSRemoteClient, TTSEngine, or None)
_tts_engine: Any = None

# Monotonic counter for dialogue_id (correlates Python ↔ Lua logs)
_dialogue_id: int = 0


def set_conversation_manager(manager: "ConversationManager") -> None:
    """Set the conversation manager instance."""
    global _conversation_manager
    _conversation_manager = manager
    logger.info("Conversation manager injected into event handlers")


def set_publisher(publisher: PublisherProtocol) -> None:
    """Set the publisher instance for sending heartbeat acks."""
    global _publisher
    _publisher = publisher
    logger.info("Publisher injected into event handlers")


def set_tts_engine(engine: Any) -> None:
    """Set the TTS engine instance (TTSRemoteClient, TTSEngine, or None)."""
    global _tts_engine
    _tts_engine = engine
    logger.info("TTS engine injected into event handlers: {}", type(engine).__name__ if engine else None)


def get_last_heartbeat() -> Optional[str]:
    """Get last heartbeat timestamp as ISO string."""
    if _last_heartbeat is None:
        return None
    return _last_heartbeat.isoformat()


async def handle_game_event(payload: dict[str, Any], session_id: str = "__default__", req_id: int = 0) -> None:
    """Handle incoming game event from Lua (v2 payload format).
    
    Parses the event and triggers dialogue generation.
    
    Payload structure from Lua (v2):
    {
        "event": { type, context, timestamp, ... },
        "candidates": [ { game_id, name, faction, rank, ... }, ... ],
        "world": "Location: X. Time: Y. Weather: Z.",
        "traits": { character_id: { personality_id, backstory_id }, ... }
    }
    """
    try:
        # Parse v2 payload structure
        event_data = payload.get("event", {})
        candidates = payload.get("candidates", [])
        world = payload.get("world", "")
        traits = payload.get("traits", {})
        
        # Basic validation
        if not event_data:
            logger.error("Empty event data in payload")
            return
        
        if not candidates:
            logger.warning("No candidates in payload — skipping dialogue generation")
            return
        
        event_type = event_data.get("type", "UNKNOWN")
        candidates_count = len(candidates)
        
        # Log event details
        pfx = log_prefix(req_id, session_id)
        logger.info(
            f"{pfx}Game Event (v2): type={event_type}, "
            f"candidates={candidates_count}, "
            f"timestamp={event_data.get('timestamp', 0)}"
        )
        
        # Log context details at debug level
        if event_data.get("context"):
            logger.debug(f"{pfx}Event context: {event_data['context']}")
        if world:
            logger.debug(f"{pfx}World: {world}")
        if candidates:
            candidate_names = [c.get("name", "unknown") for c in candidates]
            logger.debug(f"{pfx}Candidates: {candidate_names}")
        
        # Trigger dialogue generation
        _logged_task(
            _handle_event_v2(event_data, candidates, world, traits, session_id=session_id, req_id=req_id),
            name=f"dialogue-{event_type}"
        )
            
    except Exception as e:
        logger.error(f"Error processing game event: {e}")
        logger.debug(f"Raw payload: {payload}")


async def _handle_event_v2(
    event: dict[str, Any],
    candidates: list[dict[str, Any]],
    world: str,
    traits: dict[str, dict[str, str]],
    *,
    session_id: str | None = None,
    req_id: int = 0
) -> None:
    """Handle event using ConversationManager (v2 architecture).
    
    Args:
        event: Event data dict
        candidates: List of candidate speakers (speaker + witnesses)
        world: World context string
        traits: Map of character_id → {personality_id, backstory_id}
        session_id: Session identifier
        req_id: Request ID for logging correlation
    """
    if _conversation_manager is None:
        logger.warning("Conversation manager not available for event")
        return
    
    if _dialogue_semaphore.locked():
        pfx = log_prefix(req_id, session_id)
        logger.debug(f"{pfx}Skipping event — {_MAX_CONCURRENT_DIALOGUES} dialogue tasks already running")
        return
    
    async with _dialogue_semaphore:
        try:
            pfx = log_prefix(req_id, session_id)
            logger.debug(f"{pfx}Calling ConversationManager.handle_event()")
            
            # Call ConversationManager to generate dialogue
            speaker_id, dialogue_text = await _conversation_manager.handle_event(
                event=event,
                candidates=candidates,
                world=world,
                traits=traits,
            )
            
            logger.info(f"{pfx}Dialogue generated: speaker={speaker_id}, text={dialogue_text[:60]}...")

            if _publisher is None:
                logger.warning(f"{pfx}Publisher not available; cannot send dialogue.display")
                return

            # Increment monotonic dialogue_id for this dispatch
            global _dialogue_id
            _dialogue_id += 1
            current_dialogue_id = _dialogue_id

            # Resolve voice_id from the speaker's sound_prefix in candidates
            voice_id = ""
            for c in candidates:
                if str(c.get("game_id", "")) == str(speaker_id):
                    voice_id = c.get("sound_prefix") or ""
                    break

            # Attempt TTS generation if engine is available
            await _dispatch_dialogue(
                speaker_id=str(speaker_id),
                dialogue_text=dialogue_text,
                voice_id=voice_id,
                dialogue_id=current_dialogue_id,
                session_id=session_id,
                pfx=pfx,
            )
            
        except Exception as e:
            logger.opt(exception=True).error(f"{pfx}Failed to generate dialogue: {e}")


async def _dispatch_dialogue(
    *,
    speaker_id: str,
    dialogue_text: str,
    voice_id: str,
    dialogue_id: int,
    session_id: str | None,
    pfx: str,
) -> None:
    """Dispatch dialogue as TTS audio or text-only, depending on engine availability.

    If ``_tts_engine`` is set, attempts ``generate_audio()``.  On success the
    OGG bytes are base64-encoded and published as ``tts.audio``.  On failure
    (or when no engine is injected) the text-only ``dialogue.display`` topic
    is published as a fallback.
    """
    assert _publisher is not None  # caller already checked

    base_payload = {
        "speaker_id": speaker_id,
        "dialogue": dialogue_text,
        "create_event": True,
        "event_context": {"world_context": None},
        "voice_id": voice_id,
        "dialogue_id": dialogue_id,
    }

    if _tts_engine is not None:
        try:
            result = await _tts_engine.generate_audio(dialogue_text, voice_id)
            if result is not None:
                ogg_bytes, duration_ms = result
                audio_b64 = base64.b64encode(ogg_bytes).decode("ascii")
                tts_payload = {
                    **base_payload,
                    "audio_b64": audio_b64,
                    "duration_ms": duration_ms,
                }
                await _publisher.publish("tts.audio", tts_payload, session=session_id)
                logger.debug(
                    f"{pfx}Published tts.audio for speaker={speaker_id} "
                    f"(dialogue_id={dialogue_id}, {len(ogg_bytes)}B ogg, {duration_ms}ms)"
                )
                return
            else:
                logger.warning(f"{pfx}TTS returned None — falling back to dialogue.display")
        except Exception:
            logger.opt(exception=True).warning(
                f"{pfx}TTS generation failed — falling back to dialogue.display"
            )

    # Fallback: text-only
    await _publisher.publish("dialogue.display", base_payload, session=session_id)
    logger.debug(f"{pfx}Published dialogue.display for speaker={speaker_id} (dialogue_id={dialogue_id})")


async def handle_player_dialogue(payload: dict[str, Any], session_id: str = "__default__", req_id: int = 0) -> None:
    """Handle player dialogue input from Lua.
    
    Supports two payload formats:
    - v1 (legacy): {text, context} - just logs the input
    - v2 (future): {event, candidates, world, traits} - calls ConversationManager
    """
    try:
        pfx = log_prefix(req_id, session_id)
        
        # Check if this is a v2 payload (has event + candidates)
        if "event" in payload and "candidates" in payload:
            event_data = payload.get("event", {})
            candidates = payload.get("candidates", [])
            world = payload.get("world", "")
            traits = payload.get("traits", {})
            
            if not candidates:
                logger.debug(f"{pfx}Player dialogue: no candidates nearby, skipping")
                return
            
            logger.info(
                f"{pfx}Player Dialogue (v2): text=\"{event_data.get('context', {}).get('text', '')}\", "
                f"candidates={len(candidates)}"
            )
            
            # Trigger dialogue generation via ConversationManager
            _logged_task(
                _handle_event_v2(event_data, candidates, world, traits, session_id=session_id, req_id=req_id),
                name=f"player_dialogue_{req_id}"
            )
        else:
            # v1 payload: just log (Phase 1 stub)
            msg = PlayerDialogueMessage(**payload)
            logger.info(f"{pfx}Player Dialogue: \"{msg.text}\"")
            if msg.context:
                logger.debug(f"{pfx}Dialogue context: {msg.context}")
            
    except Exception as e:
        logger.error(f"Error processing player dialogue: {e}")
        logger.debug(f"Raw payload: {payload}")


async def handle_player_whisper(payload: dict[str, Any], session_id: str = "__default__", req_id: int = 0) -> None:
    """Handle player whisper input from Lua.
    
    Supports two payload formats:
    - v1 (legacy): {text, target} - just logs the input
    - v2 (future): {event, candidates, world, traits} - calls ConversationManager
    """
    try:
        pfx = log_prefix(req_id, session_id)
        
        # Check if this is a v2 payload (has event + candidates)
        if "event" in payload and "candidates" in payload:
            event_data = payload.get("event", {})
            candidates = payload.get("candidates", [])
            world = payload.get("world", "")
            traits = payload.get("traits", {})
            
            if not candidates:
                logger.debug(f"{pfx}Player whisper: no candidates nearby, skipping")
                return
            
            logger.info(
                f"{pfx}Player Whisper (v2): text=\"{event_data.get('context', {}).get('text', '')}\", "
                f"candidates={len(candidates)}"
            )
            
            # Trigger dialogue generation via ConversationManager
            _logged_task(
                _handle_event_v2(event_data, candidates, world, traits, session_id=session_id, req_id=req_id),
                name=f"player_whisper_{req_id}"
            )
        else:
            # v1 payload: just log (Phase 1 stub)
            msg = PlayerDialogueMessage(**payload)
            logger.info(f"{pfx}Player Whisper: \"{msg.text}\"")
            if msg.context:
                logger.debug(f"{pfx}Whisper context: {msg.context}")
            
    except Exception as e:
        logger.error(f"Error processing player whisper: {e}")
        logger.debug(f"Raw payload: {payload}")


async def handle_heartbeat(payload: dict[str, Any], session_id: str = "__default__", req_id: int = 0) -> None:
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
            pfx = log_prefix(req_id)
            logger.debug(
                f"{pfx}Heartbeat received: alive={msg.alive}, "
                f"game_time={msg.game_time_ms}"
            )

        # If we haven't received a config sync yet, re-request one.
        # This handles the case where the service started while the game was
        # paused/in menu and the initial config.request went unanswered.
        from ..handlers.config import _get_mirror
        mirror = _get_mirror(session_id)
        if not mirror.is_synced and _publisher:
            logger.info("Config not yet synced — re-requesting config sync via heartbeat")
            await _publisher.publish("config.request", {"reason": "heartbeat_no_sync"}, session=session_id)
        
        # Send heartbeat acknowledgement back to Lua so it knows we're alive
        if _publisher:
            await _publisher.publish("service.heartbeat.ack", {
                "status": "alive",
                "timestamp": datetime.now().isoformat(),
            }, session=session_id)
        
    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
        logger.debug(f"Raw payload: {payload}")


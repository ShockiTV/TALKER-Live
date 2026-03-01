"""Main entry point for TALKER service."""

from __future__ import annotations

import asyncio
import atexit
import os
import signal
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket
from loguru import logger

from .config import settings
from .transport.ws_router import WSRouter
from .handlers import events as event_handlers
from .handlers import config as config_handlers
from .handlers import audio as audio_handlers
from .dialogue import DialogueGenerator, SpeakerSelector
from .dialogue.retry_queue import DialogueRetryQueue
from .state.client import StateQueryClient
from .llm import get_llm_client
from .tts import TTS_AVAILABLE, TTSEngine
from .stt import STT_AVAILABLE


def _force_exit():
    """Last-resort exit if stuck threads prevent clean shutdown."""
    def _exit_after(seconds: float):
        threading.Event().wait(seconds)
        logger.warning("Force-exiting after {}s shutdown timeout", seconds)
        os._exit(0)
    t = threading.Thread(target=_exit_after, args=(5.0,), daemon=True)
    t.start()


atexit.register(_force_exit)


# Global instances
ws_router: WSRouter | None = None
dialogue_generator: DialogueGenerator | None = None
tts_engine: TTSEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global ws_router, dialogue_generator, tts_engine
    
    # Startup
    logger.info("Starting TALKER Service v0.4.0 (WebSocket transport)")
    
    ws_router = WSRouter()
    
    # Initialize TTS engine if enabled
    if settings.tts_enabled and TTS_AVAILABLE:
        logger.info("Initializing TTS engine...")
        try:
            tts_engine = TTSEngine()
            await tts_engine.load(settings.voices_dir)
            logger.info(f"TTS engine initialized with {len(tts_engine.voice_cache)} voices")
        except Exception as e:
            logger.error(f"Failed to initialize TTS engine: {e}")
            tts_engine = None
    elif settings.tts_enabled and not TTS_AVAILABLE:
        logger.warning("TTS enabled but pocket_tts not available (install with: pip install \".[tts]\")")
    
    # Initialize dialogue generation components
    logger.info("Initializing dialogue generation pipeline...")
    
    # Create a factory function that gets the LLM client based on current config
    # This allows the client to change when config.sync is received from the game
    def get_current_llm_client():
        from .handlers.config import config_mirror
        from .config import settings
        
        if getattr(settings, "force_proxy_llm", False):
            logger.info("FORCE_PROXY_LLM active — using Proxy client (ignoring MCM model_method=%s)", config_mirror.get("model_method", "?"))
            model_method = 3  # PROVIDER_PROXY
            model_name = getattr(settings, "proxy_model", None)
        else:
            model_method = config_mirror.get("model_method", 0)
            model_name = config_mirror.get("model_name", "")
            
        logger.debug(f"Getting LLM client for model_method={model_method}, model_name={model_name}")
        return get_llm_client(
            model_method,
            timeout=settings.llm_timeout,
            model=model_name if model_name else None,
        )
    
    # Create state query client
    state_client = StateQueryClient(
        router=ws_router,
        timeout=settings.state_query_timeout,
    )
    
    # Create retry queue for deferred dialogue generation
    retry_queue = DialogueRetryQueue(
        max_retries=5,
        heartbeat_interval=5.0,
    )
    
    # Create dialogue generator with factory function and TTS engine
    dialogue_generator = DialogueGenerator(
        llm_client=get_current_llm_client,  # Pass factory, not client
        state_client=state_client,
        publisher=ws_router,
        llm_timeout=settings.llm_timeout,
        retry_queue=retry_queue,
        tts_engine=tts_engine,  # Pass TTS engine if available
    )
    
    # Inject generator into event handlers
    event_handlers.set_dialogue_generator(dialogue_generator)
    event_handlers.set_publisher(ws_router)  # For heartbeat acks
    event_handlers.set_retry_queue(retry_queue)
    
    # Wire config changes to TTS engine volume
    if tts_engine:
        from .handlers.config import config_mirror
        def _on_config_change(cfg):
            vol = getattr(cfg, "tts_volume_boost", None)
            if vol is not None:
                tts_engine.volume_boost = float(vol)
                logger.info(f"TTS volume boost updated to {tts_engine.volume_boost}")
        config_mirror.on_change(_on_config_change)
    
    # Register handlers
    ws_router.on("game.event", event_handlers.handle_game_event)
    ws_router.on("player.dialogue", event_handlers.handle_player_dialogue)
    ws_router.on("player.whisper", event_handlers.handle_player_whisper)
    ws_router.on("config.update", config_handlers.handle_config_update)
    ws_router.on("config.sync", config_handlers.handle_config_sync)
    ws_router.on("system.heartbeat", event_handlers.handle_heartbeat)
    
    # Register STT audio handlers (only when STT deps are installed)
    if STT_AVAILABLE:
        audio_handlers.set_audio_publisher(ws_router)
        ws_router.on("mic.audio.chunk", audio_handlers.handle_audio_chunk)
        ws_router.on("mic.audio.end", audio_handlers.handle_audio_end)
        logger.info("STT audio handlers registered")
        
        # Lazily initialise the STT provider on first config sync so we know
        # which method the user picked (local / api / proxy).
        from .handlers.config import config_mirror
        _stt_initialised = False
        
        def _init_stt_on_config(cfg):
            nonlocal _stt_initialised
            if _stt_initialised:
                return
            _stt_initialised = True
            try:
                from .stt.factory import get_stt_provider
                # STT method is independent of LLM model_method.
                # Default to local Whisper; users can override via
                # stt_method config key ("local", "api", "proxy").
                stt_method = config_mirror.get("stt_method", "local")
                provider = get_stt_provider(stt_method)
                audio_handlers.set_stt_provider(provider)
            except Exception as exc:
                logger.error("Failed to initialise STT provider: {}", exc)
        
        config_mirror.on_change(_init_stt_on_config)
    else:
        logger.info("STT not available — mic.audio.* topics will be ignored")
    
    # Request config sync from Lua once a client connects
    async def request_config_sync():
        await asyncio.sleep(2.0)  # Wait for game client to connect
        logger.info("Requesting config sync from Lua...")
        await ws_router.publish("config.request", {"reason": "service_startup"})
    
    asyncio.create_task(request_config_sync())
    
    logger.info("TALKER Service started — waiting for WebSocket connections on /ws")
    
    yield
    
    # Shutdown
    logger.info("Shutting down TALKER Service...")
    if tts_engine:
        tts_engine.shutdown()
        logger.info("TTS engine shut down")
    if ws_router:
        await ws_router.shutdown()
    logger.info("TALKER Service stopped")


# Create FastAPI app
app = FastAPI(
    title="TALKER Service",
    description="Python compute service for TALKER Expanded mod",
    version="0.4.0",
    lifespan=lifespan,
)


@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    """WebSocket endpoint — delegates to WSRouter."""
    if ws_router:
        await ws_router.websocket_endpoint(websocket)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "ws_connected": ws_router.is_connected if ws_router else False,
        "last_heartbeat": event_handlers.get_last_heartbeat(),
    }


@app.get("/debug/config")
async def debug_config():
    """Debug endpoint to view current config mirror."""
    from .handlers.config import config_mirror
    data = config_mirror.dump()
    data["force_proxy_llm"] = settings.force_proxy_llm
    if settings.force_proxy_llm:
        data["effective_provider"] = "proxy (forced via FORCE_PROXY_LLM)"
        data["effective_model"] = settings.proxy_model or "(default)"
        data["effective_endpoint"] = settings.proxy_endpoint
    return data


def main():
    """Main entry point."""
    # Configure logging
    logger.add(
        settings.log_file,
        rotation="10 MB",
        retention="7 days",
        level=settings.log_level,
    )
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=settings.ws_host,
        port=settings.ws_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()

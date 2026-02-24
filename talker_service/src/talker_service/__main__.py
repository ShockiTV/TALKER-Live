"""Main entry point for TALKER service."""

import asyncio
import signal
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket
from loguru import logger

from .config import settings
from .transport.ws_router import WSRouter
from .handlers import events as event_handlers
from .handlers import config as config_handlers
from .dialogue import DialogueGenerator, SpeakerSelector
from .dialogue.retry_queue import DialogueRetryQueue
from .state.client import StateQueryClient
from .llm import get_llm_client


# Global instances
ws_router: WSRouter | None = None
dialogue_generator: DialogueGenerator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global ws_router, dialogue_generator
    
    # Startup
    logger.info("Starting TALKER Service v0.4.0 (WebSocket transport)")
    
    ws_router = WSRouter()
    
    # Initialize dialogue generation components
    logger.info("Initializing dialogue generation pipeline...")
    
    # Create a factory function that gets the LLM client based on current config
    # This allows the client to change when config.sync is received from the game
    def get_current_llm_client():
        from .handlers.config import config_mirror
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
    
    # Create dialogue generator with factory function
    dialogue_generator = DialogueGenerator(
        llm_client=get_current_llm_client,  # Pass factory, not client
        state_client=state_client,
        publisher=ws_router,
        llm_timeout=settings.llm_timeout,
        retry_queue=retry_queue,
    )
    
    # Inject generator into event handlers
    event_handlers.set_dialogue_generator(dialogue_generator)
    event_handlers.set_publisher(ws_router)  # For heartbeat acks
    event_handlers.set_retry_queue(retry_queue)
    
    # Register handlers
    ws_router.on("game.event", event_handlers.handle_game_event)
    ws_router.on("player.dialogue", event_handlers.handle_player_dialogue)
    ws_router.on("player.whisper", event_handlers.handle_player_whisper)
    ws_router.on("config.update", config_handlers.handle_config_update)
    ws_router.on("config.sync", config_handlers.handle_config_sync)
    ws_router.on("system.heartbeat", event_handlers.handle_heartbeat)
    
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
    return config_mirror.dump()


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

"""Main entry point for TALKER service."""

import asyncio
import signal
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from loguru import logger

from .config import settings
from .transport.router import ZMQRouter
from .handlers import events as event_handlers
from .handlers import config as config_handlers
from .dialogue import DialogueGenerator, SpeakerSelector
from .state.client import StateQueryClient
from .llm import get_llm_client


# Global instances
zmq_router: ZMQRouter | None = None
dialogue_generator: DialogueGenerator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global zmq_router, dialogue_generator
    
    # Startup
    logger.info("Starting TALKER Service v0.3.0 (Phase 2 - AI Processing)")
    logger.info(f"Connecting to Lua PUB at {settings.lua_pub_endpoint}")
    logger.info(f"Binding PUB socket at {settings.service_pub_endpoint}")
    
    zmq_router = ZMQRouter(
        sub_endpoint=settings.lua_pub_endpoint,
        pub_endpoint=settings.service_pub_endpoint,
    )
    
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
        router=zmq_router,
        timeout=settings.state_query_timeout,
    )
    
    # Create dialogue generator with factory function
    dialogue_generator = DialogueGenerator(
        llm_client=get_current_llm_client,  # Pass factory, not client
        state_client=state_client,
        publisher=zmq_router,
        llm_timeout=settings.llm_timeout,
    )
    
    # Inject generator into event handlers
    event_handlers.set_dialogue_generator(dialogue_generator)
    event_handlers.set_publisher(zmq_router)  # For heartbeat acks
    
    # Register handlers
    zmq_router.on("game.event", event_handlers.handle_game_event)
    zmq_router.on("player.dialogue", event_handlers.handle_player_dialogue)
    zmq_router.on("player.whisper", event_handlers.handle_player_whisper)
    zmq_router.on("config.update", config_handlers.handle_config_update)
    zmq_router.on("config.sync", config_handlers.handle_config_sync)
    zmq_router.on("system.heartbeat", event_handlers.handle_heartbeat)
    
    # Start ZMQ router in background
    router_task = asyncio.create_task(zmq_router.run())
    
    # Request config sync from Lua (for recovery after restart)
    async def request_config_sync():
        await asyncio.sleep(1.0)  # Wait for router to connect
        logger.info("Requesting config sync from Lua...")
        await zmq_router.publish("config.request", {"reason": "service_startup"})
    
    asyncio.create_task(request_config_sync())
    
    logger.info("TALKER Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down TALKER Service...")
    if zmq_router:
        await zmq_router.shutdown()
    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass
    logger.info("TALKER Service stopped")


# Create FastAPI app
app = FastAPI(
    title="TALKER Service",
    description="Python compute service for TALKER Expanded mod",
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "zmq_connected": zmq_router.is_connected if zmq_router else False,
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
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()

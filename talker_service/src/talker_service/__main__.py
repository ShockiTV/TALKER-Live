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


# Global router instance
zmq_router: ZMQRouter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global zmq_router
    
    # Startup
    logger.info("Starting TALKER Service v0.1.0")
    logger.info(f"Connecting to Lua PUB at {settings.lua_pub_endpoint}")
    
    zmq_router = ZMQRouter(settings.lua_pub_endpoint)
    
    # Register handlers
    zmq_router.on("game.event", event_handlers.handle_game_event)
    zmq_router.on("player.dialogue", event_handlers.handle_player_dialogue)
    zmq_router.on("player.whisper", event_handlers.handle_player_whisper)
    zmq_router.on("config.update", config_handlers.handle_config_update)
    zmq_router.on("config.sync", config_handlers.handle_config_sync)
    zmq_router.on("system.heartbeat", event_handlers.handle_heartbeat)
    
    # Start ZMQ router in background
    router_task = asyncio.create_task(zmq_router.run())
    
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
    version="0.1.0",
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

"""Main entry point for TALKER service."""

from __future__ import annotations

import asyncio
import atexit
import os
import signal
import threading
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket
from loguru import logger

from .config import settings
from .transport.ws_router import WSRouter
from .handlers import events as event_handlers
from .handlers import config as config_handlers
from .handlers import audio as audio_handlers
from .dialogue.conversation import ConversationManager
from .state.client import StateQueryClient
from .llm import get_llm_client
from .llm.models import ReasoningOptions
from .memory.compaction import CompactionEngine
from .memory.scheduler import CompactionScheduler
from .tts import TTS_AVAILABLE, TTSEngine, TTSRemoteClient
from .stt import STT_AVAILABLE
from .transport.session_registry import SessionRegistry
from .storage import Neo4jClient, EmbeddingClient, init_schema, SessionSyncService


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
conversation_manager: ConversationManager | None = None
tts_engine: TTSEngine | None = None
session_registry: SessionRegistry | None = None
neo4j_client: Neo4jClient | None = None
embedding_client: EmbeddingClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global ws_router, conversation_manager, tts_engine, session_registry, neo4j_client, embedding_client
    
    # Startup
    logger.info("Starting TALKER Service v0.4.0 (WebSocket transport)")
    
    ws_router = WSRouter()

    # Create session registry for multi-session support
    session_registry = SessionRegistry()
    ws_router.set_session_registry(session_registry)
    config_handlers.set_session_registry(session_registry)

    async def _on_shared_client_update(session_id: str, urls: dict[str, str], client):
        nonlocal tts_engine, embedding_client

        if embedding_client:
            if urls.get("ollama_base_url"):
                embedding_client.base_url = urls["ollama_base_url"].rstrip("/")
            embedding_client.set_http_client(client)

        tts_url = (urls.get("tts_service_url") or "").strip()
        if isinstance(tts_engine, TTSRemoteClient):
            if tts_url:
                tts_engine.base_url = tts_url.rstrip("/")
            tts_engine.set_http_client(client)
        elif tts_engine is None and tts_url:
            tts_engine = TTSRemoteClient(tts_url, http_client=client)
            event_handlers.set_tts_engine(tts_engine)

    config_handlers.set_shared_client_update_hook(_on_shared_client_update)

    # Initialize graph memory clients (graceful no-op when NEO4J_URI is unset)
    neo4j_client = Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
    embedding_client = EmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embed_model,
        http_client=config_handlers.get_shared_http_client(),
    )

    if neo4j_client.is_available():
        try:
            init_schema(neo4j_client)
        except Exception as exc:
            logger.warning("Neo4j schema init failed: {}", exc)
        await embedding_client.ensure_model_pulled()
    else:
        logger.info("Neo4j unavailable (NEO4J_URI not set) - graph memory disabled")
    
    # Initialize TTS: remote client (shared microservice) or embedded engine
    if settings.tts_service_url:
        logger.info("Using remote TTS service at {}", settings.tts_service_url)
        tts_engine = TTSRemoteClient(
            settings.tts_service_url,
            http_client=config_handlers.get_shared_http_client(),
        )
        logger.info("TTSRemoteClient ready")
    elif settings.tts_enabled and TTS_AVAILABLE:
        logger.info("Initializing embedded TTS engine...")
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

    # ── Server authority pins ────────────────────────────────────────
    # When .env sets LLM_PROVIDER / LLM_MODEL / etc., pin those values
    # in ConfigMirror so MCM can never override them.
    from .handlers.config import config_mirror
    from .llm.factory import PROVIDER_NAMES

    if settings.llm_provider:
        provider_int = PROVIDER_NAMES.get(settings.llm_provider.lower())
        if provider_int is not None:
            config_mirror.pin("model_method", provider_int)
        else:
            logger.warning("Unknown LLM_PROVIDER '{}' — ignoring pin", settings.llm_provider)
    if settings.llm_model:
        config_mirror.pin("model_name", settings.llm_model)
    if settings.llm_model_fast:
        config_mirror.pin("model_name_fast", settings.llm_model_fast)
    if settings.stt_method:
        config_mirror.pin("stt_method", settings.stt_method)

    if config_mirror._pins:
        logger.info("Active server-authority pins: {}", config_mirror._pins)
    else:
        logger.info("No server-authority pins — MCM controls all settings")
    
    # Create a factory function that gets the LLM client based on current config
    # This allows the client to change when config.sync is received from the game
    def get_current_llm_client():
        model_method = config_mirror.get("model_method", 0)
        model_name = config_mirror.get("model_name", "")
            
        logger.debug(f"Getting LLM client for model_method={model_method}, model_name={model_name}")
        return get_llm_client(
            model_method,
            timeout=settings.llm_timeout,
            model=model_name if model_name else None,
        )

    def get_current_fast_llm_client():
        """Build an LLM client using the fast model name (falls back to the main model)."""
        model_method = config_mirror.get("model_method", 0)
        model_name_fast = config_mirror.get("model_name_fast", "")
        if not model_name_fast:
            # No fast model configured — fall back to main client
            return get_current_llm_client()
        logger.debug(f"Getting fast LLM client for model_method={model_method}, model_name_fast={model_name_fast}")
        return get_llm_client(
            model_method,
            timeout=settings.llm_timeout,
            model=model_name_fast,
            force_new=True,
        )
    
    # Create state query client
    state_client = StateQueryClient(
        router=ws_router,
        timeout=settings.state_query_timeout,
    )

    config_handlers.set_session_sync_service(
        SessionSyncService(state_client=state_client, neo4j_client=neo4j_client)
    )
    
    # Create compaction engine + budget-pool scheduler
    compaction_engine = CompactionEngine(
        state_client=state_client,
        llm_client=get_current_llm_client(),
    )
    compaction_scheduler = CompactionScheduler(compaction_engine)

    # Build reasoning options from settings (if configured)
    reasoning_opts: ReasoningOptions | None = None
    if settings.reasoning_effort:
        reasoning_opts = ReasoningOptions(
            effort=settings.reasoning_effort,  # type: ignore[arg-type]
            summary=settings.reasoning_summary or None,  # type: ignore[arg-type]
        )
        logger.info("Reasoning options: effort={}, summary={}", reasoning_opts.effort, reasoning_opts.summary)

    # Apply feature flags from settings to the session-scoped LLM factory
    _enable_persistence = settings.enable_conversation_persistence
    _enable_pruning = settings.enable_context_pruning

    def _session_llm_factory() -> Any:
        client = get_current_llm_client()
        # Wire pruning flag into per-session clients
        if hasattr(client, "enable_pruning"):
            client.enable_pruning = _enable_pruning
        return client

    # Create conversation manager for tool-based dialogue
    conversation_manager = ConversationManager(
        llm_client=get_current_llm_client(),  # Fallback client
        state_client=state_client,
        session_registry=session_registry if _enable_persistence else None,
        llm_client_factory=_session_llm_factory if _enable_persistence else None,
        fast_llm_client=get_current_fast_llm_client(),
        compaction_engine=compaction_engine,
        compaction_scheduler=compaction_scheduler,
        llm_timeout=settings.llm_timeout,
        reasoning=reasoning_opts,
    )
    
    # Inject conversation manager into event handlers
    event_handlers.set_conversation_manager(conversation_manager)
    event_handlers.set_publisher(ws_router)  # For heartbeat acks
    event_handlers.set_tts_engine(tts_engine)  # For TTS audio dispatch
    event_handlers.set_neo4j_client(neo4j_client)
    event_handlers.set_embedding_client(embedding_client)
    
    # Wire config changes to TTS engine volume
    if tts_engine:
        def _on_config_change(cfg):
            vol = getattr(cfg, "tts_volume_boost", None)
            if vol is not None:
                tts_engine.volume_boost = float(vol)
                logger.info(f"TTS volume boost updated to {tts_engine.volume_boost}")
        session_registry.on_any_config_change(_on_config_change)
    
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
        
        # Eagerly initialise the STT provider if stt_method is pinned;
        # otherwise lazily on first config sync so we know the user's choice.
        def _init_stt(stt_method: str) -> None:
            try:
                from .stt.factory import get_stt_provider
                stt_kwargs = {}
                urls = config_handlers.get_effective_service_urls()
                stt_endpoint = (urls.get("stt_endpoint") or settings.stt_endpoint or "").strip()
                if stt_endpoint:
                    stt_kwargs["endpoint"] = stt_endpoint
                shared_http = config_handlers.get_shared_http_client()
                if shared_http is not None:
                    stt_kwargs["http_client"] = shared_http
                provider = get_stt_provider(stt_method, **stt_kwargs)
                audio_handlers.set_stt_provider(provider)
            except Exception as exc:
                logger.error("Failed to initialise STT provider: {}", exc)

        pinned_stt = config_mirror.get("stt_method")
        if pinned_stt:
            # Server-authority pin — init immediately, no need to wait for Lua
            _init_stt(pinned_stt)
        else:
            # No pin — init on first config sync
            _stt_initialised = False

            def _init_stt_on_config(cfg):
                nonlocal _stt_initialised
                if _stt_initialised:
                    return
                _stt_initialised = True
                stt_method = config_mirror.get("stt_method", "local")
                _init_stt(stt_method)

            session_registry.on_any_config_change(_init_stt_on_config)
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
        if isinstance(tts_engine, TTSRemoteClient):
            await tts_engine.close()
            logger.info("TTSRemoteClient closed")
        else:
            tts_engine.shutdown()
            logger.info("TTS engine shut down")
    if embedding_client:
        await embedding_client.close()
    if ws_router:
        await ws_router.shutdown()
    if neo4j_client:
        neo4j_client.close()
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
    from .llm.factory import PROVIDER_NAMES

    data = config_mirror.dump()

    # Reverse lookup: int → name
    provider_labels = {v: k for k, v in PROVIDER_NAMES.items()}

    method = config_mirror.get("model_method", 0)
    data["effective"] = {
        "provider": provider_labels.get(method, f"unknown({method})"),
        "model": config_mirror.get("model_name", ""),
        "model_fast": config_mirror.get("model_name_fast", ""),
        "stt_method": config_mirror.get("stt_method", "local"),
    }
    if settings.openai_endpoint:
        data["effective"]["openai_endpoint"] = settings.openai_endpoint

    # Conversation / pruning stats from active session LLM clients
    if session_registry:
        conv_stats: list[dict[str, Any]] = []
        for sid, session in session_registry.all_sessions().items():
            client = session.llm_client
            if client and hasattr(client, "pruning_events_count"):
                conv_stats.append({
                    "session_id": sid,
                    "conversation_len": len(client.get_conversation()) if hasattr(client, "get_conversation") else None,
                    "pruning_events_count": client.pruning_events_count,
                    "tokens_removed_total": client.tokens_removed_total,
                    "avg_conversation_tokens": round(client.avg_conversation_tokens, 1),
                })
        if conv_stats:
            data["conversation_stats"] = conv_stats

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

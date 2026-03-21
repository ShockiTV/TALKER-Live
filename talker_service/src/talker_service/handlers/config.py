"""Config handler and config mirror for MCM settings."""

import asyncio
import inspect
from typing import Any, Callable, Optional

import httpx
from loguru import logger

from ..auth import create_shared_http_client, derive_service_urls
from ..config import settings
from ..models.config import MCMConfig
from ._log import log_prefix


class ConfigMirror:
    """Mirrors MCM configuration from the game.
    
    Stores the latest config received from Lua and provides
    typed access to configuration values.

    Server-side pins (set via ``.env``) override MCM values transparently:
    ``get()`` returns the pinned value when one exists for that field.
    """
    
    def __init__(self):
        """Initialize with default config."""
        self._config: MCMConfig = MCMConfig()
        self._callbacks: list[Callable[[MCMConfig], None]] = []
        self._pins: dict[str, Any] = {}
        self._received_sync = False
        logger.info("Config mirror initialized with defaults. Waiting for sync from game.")

    def pin(self, field: str, value: Any) -> None:
        """Pin a field to a server-side value.

        Pinned fields always return the pinned value from ``get()``,
        regardless of what MCM sends.

        Args:
            field: Config field name (e.g. ``"model_method"``)
            value: The authoritative value
        """
        self._pins[field] = value
        logger.info("Config field '{}' pinned to: {}", field, value)
    
    def _audit_pins(self, new_config: MCMConfig) -> None:
        """Log when MCM attempts to change a pinned field."""
        for field, pinned_value in self._pins.items():
            mcm_value = getattr(new_config, field, None)
            if mcm_value is not None and mcm_value != pinned_value:
                logger.info(
                    "MCM wants {}={}, pinned to {} — ignored",
                    field, mcm_value, pinned_value,
                )

    def _effective_llm_values(self) -> tuple[Any, Any]:
        """Return the effective (post-pin) model_method and model_name."""
        return self.get("model_method", 0), self.get("model_name", "")

    def update(self, payload: dict[str, Any]) -> None:
        """Update config from Lua payload.
        
        Args:
            payload: Config dictionary from Lua
        """
        old_effective = self._effective_llm_values()
        self._config = MCMConfig.from_lua_payload(payload)
        self._received_sync = True
        
        logger.info("Config updated from game")
        logger.debug(f"Config values: {self._config.model_dump()}")
        self._audit_pins(self._config)
        
        # Clear LLM client cache only when effective (post-pin) values change
        new_effective = self._effective_llm_values()
        if old_effective != new_effective:
            from ..llm.factory import clear_client_cache
            clear_client_cache()
            logger.info(
                "LLM config changed: method={}->{}, model={!r}->{!r}",
                old_effective[0], new_effective[0],
                old_effective[1], new_effective[1],
            )

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self._config)
            except Exception as e:
                logger.error(f"Config change callback error: {e}")

    def sync(self, payload: dict[str, Any], *, defer_callbacks: bool = False) -> None:
        """Apply a full config sync from the game.

        Always clears the LLM client cache so that any client created
        before the first sync (using defaults) is discarded — unless
        the effective (post-pin) LLM values are unchanged.

        Args:
            payload: Full config dictionary from Lua
            defer_callbacks: If True, store callbacks to fire later via
                ``fire_deferred_callbacks()`` instead of firing immediately.
        """
        old_effective = self._effective_llm_values()
        self._config = MCMConfig.from_lua_payload(payload)
        self._received_sync = True
        self._audit_pins(self._config)

        new_effective = self._effective_llm_values()
        if old_effective != new_effective:
            from ..llm.factory import clear_client_cache
            clear_client_cache()
            logger.info(
                "Config sync applied — LLM cache cleared. "
                "effective method={}, model={!r}",
                new_effective[0], new_effective[1],
            )
        else:
            logger.info(
                "Config sync applied — effective LLM values unchanged "
                "(method={}, model={!r}), cache kept",
                new_effective[0], new_effective[1],
            )

        if defer_callbacks:
            self._deferred_config = self._config
        else:
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(self._config)
                except Exception as e:
                    logger.error(f"Config change callback error: {e}")

    def fire_deferred_callbacks(self) -> None:
        """Fire callbacks that were deferred by ``sync(defer_callbacks=True)``."""
        cfg = getattr(self, "_deferred_config", None)
        if cfg is None:
            return
        self._deferred_config = None
        for callback in self._callbacks:
            try:
                callback(cfg)
            except Exception as e:
                logger.error(f"Config change callback error: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key.

        Pinned values always take priority over MCM config.
        
        Args:
            key: Config key name
            default: Default value if key not found
            
        Returns:
            Pinned value if field is pinned, otherwise config value or default
        """
        if key in self._pins:
            return self._pins[key]
        return getattr(self._config, key, default)
    
    def on_change(self, callback: Callable[[MCMConfig], None]) -> None:
        """Register a callback for config changes.
        
        Args:
            callback: Function to call with new config when it changes
        """
        self._callbacks.append(callback)
    
    def dump(self) -> dict[str, Any]:
        """Dump current config as dictionary.
        
        Returns:
            Full config dictionary including pins
        """
        return {
            "received_sync": self._received_sync,
            "config": self._config.model_dump(),
            "pins": dict(self._pins),
        }
    
    @property
    def config(self) -> MCMConfig:
        """Get the current config object."""
        return self._config
    
    @property
    def is_synced(self) -> bool:
        """Check if we've received at least one sync from the game."""
        return self._received_sync


# Global config mirror instance
config_mirror = ConfigMirror()

# Optional session registry for per-session config routing
_session_registry = None
_session_sync_service = None
_shared_client_update_hook = None
_global_shared_http_client: httpx.AsyncClient | None = None
_global_service_urls = {
    "hub_url": "",
    "tts_service_url": settings.tts_service_url,
    "stt_endpoint": settings.stt_endpoint,
    "ollama_base_url": settings.ollama_base_url,
}


def set_session_registry(registry) -> None:
    """Inject a :class:`SessionRegistry` for per-session config routing.

    When set, ``handle_config_sync`` and ``handle_config_update`` write to
    the session-specific :class:`ConfigMirror` from the registry.  When
    *registry* is ``None``, the global :data:`config_mirror` is used.
    """
    global _session_registry
    _session_registry = registry
    logger.info("Session registry {} for config handlers",
                "set" if registry else "cleared")


def set_session_sync_service(sync_service) -> None:
    """Inject two-step session sync service (optional)."""
    global _session_sync_service
    _session_sync_service = sync_service
    logger.info("Session sync service {}", "set" if sync_service else "cleared")


def set_shared_client_update_hook(hook) -> None:
    """Set optional callback for shared HTTP client updates.

    The callback receives ``(session_id, urls, client)`` where *urls* contains
    ``hub_url``, ``tts_service_url``, ``stt_endpoint``, and ``ollama_base_url``.
    """
    global _shared_client_update_hook
    _shared_client_update_hook = hook


def _extract_session_id(payload: dict[str, Any]) -> str | None:
    if isinstance(payload.get("session_id"), str) and payload.get("session_id"):
        return payload.get("session_id")
    cfg = payload.get("config")
    if isinstance(cfg, dict) and isinstance(cfg.get("session_id"), str) and cfg.get("session_id"):
        return cfg.get("session_id")
    return None


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _setting_explicit(field_name: str) -> bool:
    return field_name in settings.model_fields_set


def _compute_effective_service_urls(mirror: ConfigMirror) -> dict[str, str]:
    explicit_tts = settings.tts_service_url if _setting_explicit("tts_service_url") else ""
    explicit_stt = settings.stt_endpoint if _setting_explicit("stt_endpoint") else ""
    explicit_ollama = settings.ollama_base_url if _setting_explicit("ollama_base_url") else ""

    return derive_service_urls(
        env_hub_url=settings.service_hub_url,
        mcm_hub_url=str(mirror.get("service_hub_url", "") or ""),
        tts_service_url=explicit_tts,
        stt_endpoint=explicit_stt,
        ollama_base_url=explicit_ollama,
    )


async def _apply_shared_client_config(session_id: str, mirror: ConfigMirror) -> None:
    global _global_shared_http_client, _global_service_urls

    urls = _compute_effective_service_urls(mirror)

    service_type = _coerce_int(mirror.get("service_type", 0), 0)
    llm_timeout = _coerce_float(mirror.get("llm_timeout", settings.llm_timeout), float(settings.llm_timeout))

    new_client = create_shared_http_client(
        service_type=service_type,
        hub_url=urls["hub_url"],
        auth_username=str(mirror.get("auth_username", "") or ""),
        auth_password=str(mirror.get("auth_password", "") or ""),
        auth_client_id=str(mirror.get("auth_client_id", "talker-client") or "talker-client"),
        auth_client_secret=str(mirror.get("auth_client_secret", "") or ""),
        timeout=max(llm_timeout, 1.0),
    )

    old_client: httpx.AsyncClient | None = None
    if _session_registry:
        ctx = _session_registry.get_session(session_id)
        old_client = ctx.shared_http_client
        ctx.shared_http_client = new_client
        ctx.tts_service_url = urls["tts_service_url"]
        ctx.stt_endpoint = urls["stt_endpoint"]
        ctx.ollama_base_url = urls["ollama_base_url"]
    else:
        old_client = _global_shared_http_client
        _global_shared_http_client = new_client
        _global_service_urls = urls

    if old_client is not None and old_client is not new_client:
        try:
            await old_client.aclose()
        except Exception as exc:
            logger.debug("Failed to close previous shared HTTP client: {}", exc)

    if _shared_client_update_hook:
        result = _shared_client_update_hook(session_id, urls, new_client)
        if inspect.isawaitable(result):
            await result


def get_shared_http_client(session_id: str = "__default__") -> httpx.AsyncClient | None:
    """Return session-scoped shared HTTP client (or global fallback)."""
    if _session_registry:
        return _session_registry.get_session(session_id).shared_http_client
    return _global_shared_http_client


def get_shared_client_auth_params(session_id: str = "__default__") -> dict | None:
    """Return kwargs suitable for ``create_shared_http_client()``.

    Returns *None* when no mirror data is available yet (pre-config-sync).
    Callers can use the returned dict as ``create_shared_http_client(**params)``
    to build a **new** httpx.AsyncClient with the same auth config — useful
    when the client must be created in a different event loop (e.g. inside
    ``asyncio.run()`` in a thread).
    """
    mirror = _get_mirror(session_id)
    if mirror is None:
        return None
    service_type = _coerce_int(mirror.get("service_type", 0), 0)
    llm_timeout = _coerce_float(
        mirror.get("llm_timeout", settings.llm_timeout),
        float(settings.llm_timeout),
    )
    urls = _compute_effective_service_urls(mirror)
    return {
        "service_type": service_type,
        "hub_url": urls["hub_url"],
        "auth_username": str(mirror.get("auth_username", "") or ""),
        "auth_password": str(mirror.get("auth_password", "") or ""),
        "auth_client_id": str(mirror.get("auth_client_id", "talker-client") or "talker-client"),
        "auth_client_secret": str(mirror.get("auth_client_secret", "") or ""),
        "timeout": max(llm_timeout, 1.0),
    }


def get_effective_service_urls(session_id: str = "__default__") -> dict[str, str]:
    """Return effective session service URLs after env/MCM derivation."""
    if _session_registry:
        ctx = _session_registry.get_session(session_id)
        return {
            "hub_url": _compute_effective_service_urls(_session_registry.get_config(session_id))["hub_url"],
            "tts_service_url": ctx.tts_service_url,
            "stt_endpoint": ctx.stt_endpoint,
            "ollama_base_url": ctx.ollama_base_url,
        }
    return dict(_global_service_urls)


async def _run_session_sync_task(*, connection_session: str, lua_session_id: str, previous: str | None) -> None:
    if not _session_sync_service or not _session_registry:
        return

    ctx = _session_registry.get_session(connection_session)
    try:
        await _session_sync_service.sync_if_needed(
            connection_session=connection_session,
            lua_session_id=lua_session_id,
            player_id=ctx.player_id,
            branch=ctx.branch,
            previous_lua_session_id=previous,
        )
    except Exception as exc:
        logger.opt(exception=True).warning("Session sync task failed: {}", exc)


def _get_mirror(session_id: str | None = None):
    """Return the ConfigMirror for *session_id*.

    Uses the session registry when available; falls back to the module-level
    global singleton.
    """
    if _session_registry and session_id is not None:
        return _session_registry.get_config(session_id)
    return config_mirror


async def handle_config_update(payload: dict[str, Any], session_id: str = "__default__", req_id: int = 0) -> None:
    """Handle config.update message (MCM setting changed).

    Args:
        payload: Config dictionary from Lua
        session_id: Session that sent the update
    """
    logger.info("{}Received config update from game (session={})", log_prefix(req_id, session_id), session_id)
    mirror = _get_mirror(session_id)
    mirror.update(payload)
    await _apply_shared_client_config(session_id, mirror)


async def handle_config_sync(payload: dict[str, Any], session_id: str = "__default__", req_id: int = 0) -> None:
    """Handle config.sync message (full config on game load).

    Always clears the LLM client cache so any client instantiated before
    the first sync (using service defaults) is replaced with one using
    the actual game config.

    Args:
        payload: Full config dictionary from Lua
        session_id: Session that sent the sync
    """
    logger.info("{}Received config sync from game (session={})", log_prefix(req_id, session_id), session_id)
    mirror = _get_mirror(session_id)
    # Sync mirror first (populates auth fields), then create shared client,
    # then fire on_change callbacks so they can access the shared client.
    mirror.sync(payload, defer_callbacks=True)
    await _apply_shared_client_config(session_id, mirror)
    mirror.fire_deferred_callbacks()

    if _session_registry:
        ctx = _session_registry.get_session(session_id)
        incoming_session_id = _extract_session_id(payload)
        if incoming_session_id:
            previous = ctx.game_session_id
            if previous == incoming_session_id:
                logger.debug("Config sync reconnect detected (session_id unchanged: {})", incoming_session_id)
                return
            ctx.game_session_id = incoming_session_id
            asyncio.create_task(
                _run_session_sync_task(
                    connection_session=session_id,
                    lua_session_id=incoming_session_id,
                    previous=previous,
                )
            )

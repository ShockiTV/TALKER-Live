"""Config handler and config mirror for MCM settings."""

from typing import Any, Callable, Optional

from loguru import logger

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

    def sync(self, payload: dict[str, Any]) -> None:
        """Apply a full config sync from the game.

        Always clears the LLM client cache so that any client created
        before the first sync (using defaults) is discarded — unless
        the effective (post-pin) LLM values are unchanged.

        Args:
            payload: Full config dictionary from Lua
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

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self._config)
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
    _get_mirror(session_id).update(payload)


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
    _get_mirror(session_id).sync(payload)

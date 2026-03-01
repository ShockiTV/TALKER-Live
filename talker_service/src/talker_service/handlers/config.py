"""Config handler and config mirror for MCM settings."""

from typing import Any, Callable, Optional

from loguru import logger

from ..models.config import MCMConfig


class ConfigMirror:
    """Mirrors MCM configuration from the game.
    
    Stores the latest config received from Lua and provides
    typed access to configuration values.
    """
    
    def __init__(self):
        """Initialize with default config."""
        self._config: MCMConfig = MCMConfig()
        self._callbacks: list[Callable[[MCMConfig], None]] = []
        self._received_sync = False
        logger.info("Config mirror initialized with defaults. Waiting for sync from game.")
    
    def update(self, payload: dict[str, Any]) -> None:
        """Update config from Lua payload.
        
        Args:
            payload: Config dictionary from Lua
        """
        old_config = self._config
        self._config = MCMConfig.from_lua_payload(payload)
        self._received_sync = True
        
        logger.info("Config updated from game")
        logger.debug(f"Config values: {self._config.model_dump()}")
        
        # Clear LLM client cache when model settings change
        model_changed = (
            old_config.model_method != self._config.model_method or
            old_config.model_name != self._config.model_name
        )
        if model_changed:
            from ..config import settings
            if settings.force_proxy_llm:
                logger.info(
                    f"MCM model changed (method={old_config.model_method}->{self._config.model_method}) "
                    f"but FORCE_PROXY_LLM is active — ignoring, keeping Proxy client"
                )
            else:
                from ..llm.factory import clear_client_cache
                clear_client_cache()
                logger.info(f"LLM config changed: method={old_config.model_method}->{self._config.model_method}, model={old_config.model_name}->{self._config.model_name}")

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self._config)
            except Exception as e:
                logger.error(f"Config change callback error: {e}")

    def sync(self, payload: dict[str, Any]) -> None:
        """Apply a full config sync from the game.

        Unlike update(), this always clears the LLM client cache so that any
        client created before the first sync (using defaults) is discarded.
        When ``force_proxy_llm`` is active the cache is left alone because
        the ProxyClient is always used regardless of MCM values.

        Args:
            payload: Full config dictionary from Lua
        """
        self._config = MCMConfig.from_lua_payload(payload)
        self._received_sync = True

        from ..config import settings
        if settings.force_proxy_llm:
            logger.info(
                f"Config sync applied (MCM method={self._config.model_method}, "
                f"model={self._config.model_name!r}) — FORCE_PROXY_LLM active, "
                f"keeping Proxy client, cache NOT cleared"
            )
        else:
            from ..llm.factory import clear_client_cache
            clear_client_cache()
            logger.info(
                f"Config sync applied — LLM cache cleared. "
                f"method={self._config.model_method}, model={self._config.model_name!r}"
            )

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self._config)
            except Exception as e:
                logger.error(f"Config change callback error: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key.
        
        Args:
            key: Config key name
            default: Default value if key not found
            
        Returns:
            Config value or default
        """
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
            Full config dictionary
        """
        return {
            "received_sync": self._received_sync,
            "config": self._config.model_dump(),
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


async def handle_config_update(payload: dict[str, Any]) -> None:
    """Handle config.update message (MCM setting changed).
    
    Args:
        payload: Config dictionary from Lua
    """
    logger.info("Received config update from game")
    config_mirror.update(payload)


async def handle_config_sync(payload: dict[str, Any]) -> None:
    """Handle config.sync message (full config on game load).

    Always clears the LLM client cache so any client instantiated before
    the first sync (using service defaults) is replaced with one using
    the actual game config.

    Args:
        payload: Full config dictionary from Lua
    """
    logger.info("Received config sync from game (full config)")
    config_mirror.sync(payload)

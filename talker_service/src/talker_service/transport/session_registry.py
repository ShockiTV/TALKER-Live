"""Session registry — per-session ConfigMirror and SessionContext."""

from __future__ import annotations

from typing import Any, Callable

from loguru import logger

from ..handlers.config import ConfigMirror
from ..models.config import MCMConfig
from .session import SessionContext
from .outbox import Outbox


class SessionRegistry:
    """Manages per-session state: config and session context.

    Provides get-or-create semantics: first access for a ``session_id``
    creates default instances; subsequent accesses return the same objects.
    """

    def __init__(
        self,
        *,
        outbox_ttl_seconds: float = 30 * 60,
        outbox_max_size: int = 500,
    ) -> None:
        self._configs: dict[str, ConfigMirror] = {}
        self._sessions: dict[str, SessionContext] = {}
        self._global_callbacks: list[Callable[[MCMConfig], None]] = []
        self._outbox_ttl_seconds = outbox_ttl_seconds
        self._outbox_max_size = outbox_max_size

    # ------------------------------------------------------------------
    # Global config callbacks
    # ------------------------------------------------------------------

    def on_any_config_change(self, callback: Callable[[MCMConfig], None]) -> None:
        """Register a callback that fires when *any* session's config changes.

        The callback is wired into every :class:`ConfigMirror` created by
        :meth:`get_config` (at creation time).  Callbacks registered here
        are intended for shared-resource initialisation (STT provider,
        TTS volume sync) that must fire regardless of which session
        triggered the config sync.
        """
        self._global_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def get_config(self, session_id: str) -> ConfigMirror:
        """Return the :class:`ConfigMirror` for *session_id*, creating if needed.

        Newly created mirrors inherit all callbacks registered via
        :meth:`on_any_config_change`.
        """
        if session_id not in self._configs:
            mirror = ConfigMirror()
            for cb in self._global_callbacks:
                mirror.on_change(cb)
            self._configs[session_id] = mirror
            logger.debug("Created ConfigMirror for session {} ({} global callbacks wired)", session_id, len(self._global_callbacks))
        return self._configs[session_id]

    # ------------------------------------------------------------------
    # Session context
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> SessionContext:
        """Return the :class:`SessionContext` for *session_id*, creating if needed."""
        if session_id not in self._sessions:
            outbox = Outbox(
                ttl_seconds=self._outbox_ttl_seconds,
                max_size=self._outbox_max_size,
            )
            self._sessions[session_id] = SessionContext(
                session_id=session_id,
                outbox=outbox,
            )
            logger.debug("Created SessionContext for session {}", session_id)
        return self._sessions[session_id]

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def remove_session(self, session_id: str) -> None:
        """Remove all state for *session_id*."""
        self._configs.pop(session_id, None)
        self._sessions.pop(session_id, None)
        logger.info("Removed session state for {}", session_id)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def session_ids(self) -> list[str]:
        """All known session IDs (union of configs and sessions)."""
        return list(
            set(self._configs) | set(self._sessions)
        )

    @property
    def active_session_count(self) -> int:
        """Number of sessions with an active WebSocket connection."""
        return sum(
            1 for s in self._sessions.values() if s.is_connected
        )

    def __repr__(self) -> str:
        return (
            f"SessionRegistry(sessions={len(self._sessions)}, "
            f"active={self.active_session_count})"
        )

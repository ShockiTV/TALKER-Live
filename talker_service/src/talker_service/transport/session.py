"""Session context for multi-tenant WebSocket connections."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from fastapi import WebSocket
import httpx

from .outbox import Outbox

if TYPE_CHECKING:
    from ..llm.base import LLMClient


# Default session_id when auth is disabled (local single-player mode)
DEFAULT_SESSION: str = "__default__"


@dataclass
class SessionContext:
    """Per-session state associated with a WebSocket connection.

    Holds the active connection (if any), the outbox for buffering
    messages during disconnection, and session metadata.

    The session persists after disconnection so that:
    - The outbox can accumulate messages.
    - Reconnection with the same token resumes the same session.
    """

    session_id: str
    """Stable identifier derived from the token name (or ``__default__``)."""

    connection: WebSocket | None = None
    """Active WebSocket, or ``None`` if disconnected."""

    outbox: Outbox = field(default_factory=Outbox)
    """Message buffer for when the connection is absent."""

    created_at: float = field(default_factory=time.monotonic)
    """Monotonic timestamp of session creation."""

    last_activity: float = field(default_factory=time.monotonic)
    """Monotonic timestamp of last inbound or outbound activity."""

    llm_client: LLMClient | None = field(default=None, repr=False)
    """Per-session LLM client with isolated conversation state."""

    player_id: str = "local"
    """Player identity extracted from trusted proxy headers."""

    branch: str = "main"
    """Branch label extracted from trusted proxy headers."""

    game_session_id: str | None = None
    """Lua save session_id from config.sync; used for two-step graph sync."""

    shared_http_client: httpx.AsyncClient | None = field(default=None, repr=False)
    """Session-scoped shared HTTP client for outbound TTS/STT/embed API calls."""

    tts_service_url: str = ""
    """Effective session TTS endpoint after env/MCM derivation."""

    stt_endpoint: str = ""
    """Effective session STT endpoint after env/MCM derivation."""

    ollama_base_url: str = ""
    """Effective session embedding endpoint after env/MCM derivation."""

    def touch(self) -> None:
        """Update last_activity to now."""
        self.last_activity = time.monotonic()

    @property
    def is_connected(self) -> bool:
        """Whether the session has an active WebSocket connection."""
        return self.connection is not None

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return (
            f"SessionContext(id={self.session_id!r}, {status}, "
            f"outbox={self.outbox.size})"
        )

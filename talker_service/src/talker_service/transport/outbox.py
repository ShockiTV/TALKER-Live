"""Per-session outbox for buffering outbound messages during disconnection."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


# Default outbox settings
DEFAULT_TTL_MINUTES = 30
DEFAULT_MAX_SIZE = 500


@dataclass
class OutboxMessage:
    """A single buffered outbound message with creation timestamp."""

    raw: str
    """Pre-serialised JSON envelope (ready to send via ``ws.send_text``)."""

    created_at: float = field(default_factory=time.monotonic)
    """Monotonic timestamp when the message was buffered."""


class Outbox:
    """Bounded, ordered message buffer with TTL-based expiration.

    Messages are appended when a session has no active connection and
    drained in order on reconnect.  Stale messages (older than *ttl_seconds*)
    are discarded during drain.  A FIFO eviction policy keeps the buffer
    at most *max_size* entries.
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = DEFAULT_TTL_MINUTES * 60,
        max_size: int = DEFAULT_MAX_SIZE,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_size = max_size
        self._messages: deque[OutboxMessage] = deque()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, raw: str) -> None:
        """Buffer a pre-serialised JSON envelope.

        If the outbox is at capacity, the oldest message is evicted first.
        """
        if len(self._messages) >= self._max_size:
            self._messages.popleft()  # FIFO eviction
        self._messages.append(OutboxMessage(raw=raw))

    def drain(self) -> list[str]:
        """Return all non-expired messages in insertion order and clear.

        Messages older than the TTL are silently discarded.

        Returns:
            List of raw JSON strings ready for ``ws.send_text()``.
        """
        cutoff = time.monotonic() - self._ttl_seconds
        result: list[str] = []
        for msg in self._messages:
            if msg.created_at >= cutoff:
                result.append(msg.raw)
        self._messages.clear()
        return result

    @property
    def size(self) -> int:
        """Number of messages currently buffered (including potentially expired)."""
        return len(self._messages)

    @property
    def is_empty(self) -> bool:
        return len(self._messages) == 0

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return f"Outbox(size={self.size}, max_size={self._max_size}, ttl={self._ttl_seconds}s)"

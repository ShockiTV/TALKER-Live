"""Retry queue for dialogue generation requests that failed due to transient state query timeouts.

When Lua is unresponsive (e.g. player opened the main menu), state queries time out
and dialogue generation silently fails.  This module parks those failed requests and
re-submits them once a heartbeat proves Lua is back online.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from .generator import DialogueGenerator


@dataclass
class RetryItem:
    """A dialogue generation request parked for retry.

    Attributes:
        method: Which generator entry-point to call — ``"event"`` or ``"instruction"``.
        event_dict: The original event dict passed to the generator.
        speaker_id: Speaker character ID (only set for ``"instruction"`` method).
        attempt_count: How many times this item has been attempted (starts at 1).
        enqueued_at: Wall-clock ``time.time()`` when the item was first enqueued.
    """

    method: str
    event_dict: dict[str, Any]
    speaker_id: str | None = None
    attempt_count: int = 1
    enqueued_at: float = field(default_factory=time.time)


class DialogueRetryQueue:
    """Queue for parking and retrying dialogue generation requests.

    Items are enqueued when a ``StateQueryTimeout`` is caught during dialogue
    generation.  When a heartbeat arrives after a connectivity gap (Lua was
    paused), :meth:`flush` drains the queue and re-submits all valid items
    via ``asyncio.create_task()``.

    Parameters:
        max_retries: Maximum number of attempts per item (default 5).
            Items that reach this limit are discarded with a warning log.
        heartbeat_interval: Expected heartbeat interval in seconds.
            A gap >= 2× this value triggers a flush on the next heartbeat.
    """

    def __init__(
        self,
        max_retries: int = 5,
        heartbeat_interval: float = 5.0,
    ) -> None:
        self.max_retries = max_retries
        self.heartbeat_interval = heartbeat_interval

        self._queue: list[RetryItem] = []
        self._last_heartbeat_time: float | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(
        self,
        method: str,
        event_dict: dict[str, Any],
        speaker_id: str | None = None,
        attempt_count: int = 1,
    ) -> None:
        """Add a failed dialogue request to the retry queue.

        Args:
            method: ``"event"`` or ``"instruction"``.
            event_dict: Original event dict.
            speaker_id: Speaker ID (required for ``"instruction"``).
            attempt_count: Current attempt number (1-based).
        """
        item = RetryItem(
            method=method,
            event_dict=event_dict,
            speaker_id=speaker_id,
            attempt_count=attempt_count,
        )
        self._queue.append(item)
        event_type = event_dict.get("type", "unknown")
        logger.info(
            f"Enqueued retry item: method={method}, event_type={event_type}, "
            f"speaker={speaker_id}, attempt={attempt_count} "
            f"(queue size: {self.size})"
        )

    def flush(self, generator: DialogueGenerator) -> int:
        """Drain the queue and re-submit all valid items.

        Items whose ``attempt_count`` >= ``max_retries`` are discarded with
        a warning.  Valid items are dispatched via ``asyncio.create_task()``.

        Args:
            generator: The :class:`DialogueGenerator` to re-invoke.

        Returns:
            Number of items re-submitted.
        """
        # Drain — safe without locking because this runs in a single-threaded
        # asyncio event loop and there are no await points between copy & clear.
        items = list(self._queue)
        self._queue.clear()

        if not items:
            return 0

        resubmitted = 0
        for item in items:
            if item.attempt_count >= self.max_retries:
                event_type = item.event_dict.get("type", "unknown")
                logger.warning(
                    f"Discarding retry item after {item.attempt_count} attempts: "
                    f"method={item.method}, event_type={event_type}, "
                    f"speaker={item.speaker_id}"
                )
                continue

            # Re-submit with incremented attempt count
            next_attempt = item.attempt_count + 1
            if item.method == "instruction" and item.speaker_id:
                asyncio.create_task(
                    _retry_instruction(generator, item, next_attempt)
                )
            else:
                asyncio.create_task(
                    _retry_event(generator, item, next_attempt)
                )
            resubmitted += 1

        logger.info(
            f"Retry queue flushed: {resubmitted} re-submitted, "
            f"{len(items) - resubmitted} discarded"
        )
        return resubmitted

    def notify_heartbeat(self, now: float) -> bool:
        """Record a heartbeat timestamp and detect connectivity gaps.

        If the gap since the previous heartbeat is >= 2× ``heartbeat_interval``,
        returns ``True`` (the caller should trigger :meth:`flush`).
        Otherwise returns ``False``.

        This method does NOT call ``flush()`` itself — the caller (event handler)
        is responsible for obtaining the generator reference and calling flush.

        Args:
            now: Current wall-clock time (``time.time()``).

        Returns:
            ``True`` if a gap was detected (caller should flush), else ``False``.
        """
        prev = self._last_heartbeat_time
        self._last_heartbeat_time = now

        if prev is None:
            # First heartbeat — no gap to detect
            return False

        gap = now - prev
        threshold = self.heartbeat_interval * 2.0

        if gap >= threshold and self.size > 0:
            logger.info(
                f"Heartbeat gap detected: {gap:.1f}s (threshold {threshold:.1f}s), "
                f"retry queue has {self.size} items — flush needed"
            )
            return True

        return False

    @property
    def size(self) -> int:
        """Number of items currently in the queue."""
        return len(self._queue)

    def clear(self) -> None:
        """Remove all items from the queue."""
        self._queue.clear()


# ------------------------------------------------------------------
# Private retry coroutines
# ------------------------------------------------------------------

# Key stamped into event dicts to carry attempt count through the generator.
_RETRY_ATTEMPT_KEY = "_retry_attempt"


def get_retry_attempt(event_dict: dict[str, Any]) -> int:
    """Read the current retry attempt from an event dict.

    Returns 1 (first attempt) if the key is absent.
    """
    return event_dict.get(_RETRY_ATTEMPT_KEY, 1)


async def _retry_event(
    generator: DialogueGenerator,
    item: RetryItem,
    attempt: int,
) -> None:
    """Re-invoke ``generate_from_event`` for a retried item."""
    event_type = item.event_dict.get("type", "unknown")
    logger.info(f"Retrying event dialogue: type={event_type}, attempt={attempt}")
    try:
        # Stamp attempt count so the generator can forward it on re-enqueue
        item.event_dict[_RETRY_ATTEMPT_KEY] = attempt
        await generator.generate_from_event(item.event_dict)
    except Exception as e:
        logger.error(f"Retry attempt {attempt} failed for event {event_type}: {e}")


async def _retry_instruction(
    generator: DialogueGenerator,
    item: RetryItem,
    attempt: int,
) -> None:
    """Re-invoke ``generate_from_instruction`` for a retried item."""
    logger.info(
        f"Retrying instruction dialogue: speaker={item.speaker_id}, attempt={attempt}"
    )
    try:
        # Stamp attempt count so the generator can forward it on re-enqueue
        item.event_dict[_RETRY_ATTEMPT_KEY] = attempt
        await generator.generate_from_instruction(item.speaker_id, item.event_dict)
    except Exception as e:
        logger.error(
            f"Retry attempt {attempt} failed for instruction "
            f"speaker={item.speaker_id}: {e}"
        )

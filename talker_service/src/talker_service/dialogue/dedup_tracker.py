"""Deduplication tracker for system messages in the conversation window.

Maintains three injection-state sets — events, backgrounds, and memories —
to prevent duplicate system messages. Supports full rebuild from surviving
messages after pruning.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm.models import Message


# Tag prefix patterns for rebuild parsing
_EVT_RE = re.compile(r"^EVT:(\d+)")
_BG_RE = re.compile(r"^BG:(\S+)")
_MEM_RE = re.compile(r"^MEM:(\S+):(\d+)")


class DeduplicationTracker:
    """Tracks injected system messages to prevent duplicates.

    Three independent sets:
    - ``_injected_event_ts``: event timestamps (int)
    - ``_injected_bg_ids``: character IDs with backgrounds (str)
    - ``_injected_mem_ids``: (char_id, start_ts) tuples for memories
    """

    def __init__(self) -> None:
        self._injected_event_ts: set[int] = set()
        self._injected_bg_ids: set[str] = set()
        self._injected_mem_ids: set[tuple[str, int]] = set()

    # ------------------------------------------------------------------
    # Check methods
    # ------------------------------------------------------------------

    def is_event_injected(self, ts: int) -> bool:
        """Check if an event timestamp is already tracked."""
        return ts in self._injected_event_ts

    def is_bg_injected(self, char_id: str) -> bool:
        """Check if a character's background is already tracked."""
        return char_id in self._injected_bg_ids

    def is_mem_injected(self, char_id: str, start_ts: int) -> bool:
        """Check if a memory item is already tracked."""
        return (char_id, start_ts) in self._injected_mem_ids

    # ------------------------------------------------------------------
    # Mark methods
    # ------------------------------------------------------------------

    def mark_event(self, ts: int) -> None:
        """Record an event timestamp as injected."""
        self._injected_event_ts.add(ts)

    def mark_bg(self, char_id: str) -> None:
        """Record a character's background as injected."""
        self._injected_bg_ids.add(char_id)

    def mark_mem(self, char_id: str, start_ts: int) -> None:
        """Record a memory item as injected."""
        self._injected_mem_ids.add((char_id, start_ts))

    def has_mem_for_character(self, char_id: str) -> bool:
        """Check if any memory items have been injected for a character."""
        return any(cid == char_id for cid, _ in self._injected_mem_ids)

    # ------------------------------------------------------------------
    # Rebuild from messages
    # ------------------------------------------------------------------

    def rebuild_from_messages(self, messages: list["Message"]) -> None:
        """Rebuild all three sets from surviving system messages.

        Clears all sets and re-scans each system message by tag prefix:
        - ``EVT:{ts}`` → add ts to event set
        - ``BG:{char_id}`` → add char_id to background set
        - ``MEM:{char_id}:{start_ts}`` → add tuple to memory set

        Non-system messages are skipped.

        Args:
            messages: The current conversation message list.
        """
        self._injected_event_ts.clear()
        self._injected_bg_ids.clear()
        self._injected_mem_ids.clear()

        for msg in messages:
            if msg.role != "system":
                continue
            content = msg.content or ""

            m = _EVT_RE.match(content)
            if m:
                self._injected_event_ts.add(int(m.group(1)))
                continue

            m = _BG_RE.match(content)
            if m:
                self._injected_bg_ids.add(m.group(1))
                continue

            m = _MEM_RE.match(content)
            if m:
                self._injected_mem_ids.add((m.group(1), int(m.group(2))))
                continue

    # ------------------------------------------------------------------
    # Inspection (for testing / debugging)
    # ------------------------------------------------------------------

    @property
    def event_count(self) -> int:
        return len(self._injected_event_ts)

    @property
    def bg_count(self) -> int:
        return len(self._injected_bg_ids)

    @property
    def mem_count(self) -> int:
        return len(self._injected_mem_ids)

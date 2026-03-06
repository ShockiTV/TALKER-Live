"""Append-only context block for LLM prompt prefix caching.

Stores background and memory items as typed dataclasses with set-based
dedup tracking. Renders to Markdown in insertion order for cache-stable
LLM wire format.

The rendered output is byte-identical up to the last previously-rendered
item — new items only add tokens at the end, preserving the prefix cache.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


# ---------------------------------------------------------------------------
# Item dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class BackgroundItem:
    """A character background entry in the context block."""
    char_id: str
    name: str
    faction: str
    text: str


@dataclass(frozen=True, slots=True)
class MemoryItem:
    """A character memory entry in the context block."""
    char_id: str
    name: str
    ts: int
    tier: str
    text: str


# Union type for items stored in the block
ContextItem = Union[BackgroundItem, MemoryItem]


# ---------------------------------------------------------------------------
# ContextBlock
# ---------------------------------------------------------------------------

class ContextBlock:
    """Append-only data structure holding all background and memory items.

    Maintains ordered ``_items`` list plus set-based dedup indexes for
    O(1) duplicate detection.  The only way to produce a shorter block
    is to construct a new ``ContextBlock`` and re-add desired items.
    """

    def __init__(self) -> None:
        self._items: list[ContextItem] = []
        self._bg_ids: set[str] = set()
        self._mem_keys: set[tuple[str, int]] = set()

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_background(
        self, char_id: str, name: str, faction: str, text: str,
    ) -> bool:
        """Add a background item if not already present.

        Args:
            char_id: Character ID string.
            name: Character display name.
            faction: Human-readable faction name.
            text: Background text content.

        Returns:
            ``True`` if the item was added, ``False`` if duplicate.
        """
        if char_id in self._bg_ids:
            return False
        self._bg_ids.add(char_id)
        self._items.append(BackgroundItem(char_id=char_id, name=name, faction=faction, text=text))
        return True

    def add_memory(
        self, char_id: str, name: str, ts: int, tier: str, text: str,
    ) -> bool:
        """Add a memory item if not already present.

        Args:
            char_id: Character ID string.
            name: Character display name.
            ts: Memory item timestamp.
            tier: Tier label (e.g. ``SUMMARIES``, ``DIGESTS``, ``CORES``).
            text: Memory narrative text.

        Returns:
            ``True`` if the item was added, ``False`` if duplicate.
        """
        key = (char_id, ts)
        if key in self._mem_keys:
            return False
        self._mem_keys.add(key)
        self._items.append(MemoryItem(char_id=char_id, name=name, ts=ts, tier=tier, text=text))
        return True

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def has_background(self, char_id: str) -> bool:
        """Check if a character's background is already present (O(1))."""
        return char_id in self._bg_ids

    def has_memory(self, char_id: str, ts: int) -> bool:
        """Check if a memory item is already present (O(1))."""
        return (char_id, ts) in self._mem_keys

    def missing(self, char_ids: list[str]) -> list[str]:
        """Return character IDs from *char_ids* that lack a background entry.

        Args:
            char_ids: List of character IDs to check.

        Returns:
            List of IDs not present in ``_bg_ids``, preserving input order.
        """
        return [cid for cid in char_ids if cid not in self._bg_ids]

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_markdown(self) -> str:
        """Render all items as Markdown in insertion order.

        Background items render as::

            ## Name (Faction) [id:char_id]
            background text

        Memory items render as::

            [TIER] Name [id:char_id] @ts: memory text

        Returns:
            Markdown string, or empty string if block is empty.
        """
        if not self._items:
            return ""

        parts: list[str] = []
        for item in self._items:
            if isinstance(item, BackgroundItem):
                parts.append(f"## {item.name} ({item.faction}) [id:{item.char_id}]\n{item.text}")
            elif isinstance(item, MemoryItem):
                parts.append(f"[{item.tier}] {item.name} [id:{item.char_id}] @{item.ts}: {item.text}")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def item_count(self) -> int:
        """Total number of items in the block."""
        return len(self._items)

    @property
    def bg_count(self) -> int:
        """Number of background items."""
        return len(self._bg_ids)

    @property
    def mem_count(self) -> int:
        """Number of memory items."""
        return len(self._mem_keys)

    def get_all_backgrounds(self) -> list[BackgroundItem]:
        """Return all background items in insertion order."""
        return [item for item in self._items if isinstance(item, BackgroundItem)]

    def get_all_memories(self) -> list[MemoryItem]:
        """Return all memory items in insertion order."""
        return [item for item in self._items if isinstance(item, MemoryItem)]

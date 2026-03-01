"""Shared log-prefix helper for correlation IDs.

Produces structured prefixes like ``[R:5 S:player_1 D#3]`` for use in
all handler and generator log lines.
"""

from __future__ import annotations


def log_prefix(
    req_id: int | None = None,
    session_id: str | None = None,
    dialogue_id: int | None = None,
) -> str:
    """Build a structured log prefix string.

    Segments are omitted when the value is ``None``, ``0``, or the
    default session (``"__default__"``).

    Examples::

        log_prefix(req_id=5)                                   # "[R:5] "
        log_prefix(req_id=5, session_id="p1")                  # "[R:5 S:p1] "
        log_prefix(req_id=5, session_id="p1", dialogue_id=3)   # "[R:5 S:p1 D#3] "
        log_prefix(req_id=5, session_id="__default__", dialogue_id=3)  # "[R:5 D#3] "
        log_prefix(dialogue_id=3)                              # "[D#3] "
        log_prefix()                                           # ""
    """
    parts: list[str] = []

    if req_id:
        parts.append(f"R:{req_id}")

    if session_id and session_id != "__default__":
        parts.append(f"S:{session_id}")

    if dialogue_id is not None:
        parts.append(f"D#{dialogue_id}")

    if not parts:
        return ""

    return "[" + " ".join(parts) + "] "

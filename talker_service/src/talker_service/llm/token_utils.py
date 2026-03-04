"""Token estimation utilities for conversation pruning.

Uses a simple heuristic of ~4 characters per token (accurate within ~15%
for GPT-4 / GPT-4o).  Can be swapped for ``tiktoken`` later if precision
is needed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Message

# Rough heuristic: 1 token ≈ 4 characters (English text)
_CHARS_PER_TOKEN = 4


def estimate_message_tokens(message: "Message") -> int:
    """Estimate token count for a single message.

    Accounts for ``content``, ``tool_calls`` (serialized), and per-message
    overhead (~4 tokens for role/name metadata).
    """
    chars = len(message.content or "")

    if message.tool_calls:
        for tc in message.tool_calls:
            if isinstance(tc, dict):
                func = tc.get("function", {})
                chars += len(func.get("name", ""))
                args = func.get("arguments", "")
                chars += len(args) if isinstance(args, str) else len(json.dumps(args, default=str))
            else:
                chars += len(getattr(tc, "name", "") or "")
                args = getattr(tc, "arguments", "")
                chars += len(args) if isinstance(args, str) else len(json.dumps(args, default=str))

    # Per-message overhead (role, separators)
    overhead = 4
    return max(1, chars // _CHARS_PER_TOKEN + overhead)


def estimate_tokens(messages: list["Message"]) -> int:
    """Estimate total token count for a list of messages."""
    return sum(estimate_message_tokens(m) for m in messages)

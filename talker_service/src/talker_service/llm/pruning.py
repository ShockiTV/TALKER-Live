"""Context-aware message pruning for persistent conversations.

Implements priority-based pruning to keep conversations within the LLM's
context window while preserving the most important context.

Priority order (keep → remove):
1. System prompts (always kept)
2. Last N dialogue pairs (user + assistant)
3. Last N tool result message groups
4. Older dialogue messages (removed first when over budget)
5. Older tool messages (removed first when over budget)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from .token_utils import estimate_tokens, estimate_message_tokens

if TYPE_CHECKING:
    from .models import Message

# Number of recent dialogue pairs and tool groups to always preserve
_PRESERVE_DIALOGUE_PAIRS = 5  # = 10 messages (user + assistant)
_PRESERVE_TOOL_GROUPS = 5     # = ~10 messages (assistant tool_call + tool result)


def prune_conversation(
    messages: list["Message"],
    max_tokens: int,
    target_tokens: int,
) -> list["Message"]:
    """Prune a conversation to fit within a token budget.

    Only prunes if estimated tokens exceed *max_tokens*.  When triggered,
    removes messages until the total is at or below *target_tokens*.

    Args:
        messages: Full conversation message list (mutated in-place is avoided).
        max_tokens: Threshold that triggers pruning (e.g. 96 000 = 75 %).
        target_tokens: Target token count after pruning (e.g. 64 000 = 50 %).

    Returns:
        New (possibly shorter) list of messages.  Original list is not modified.
    """
    current_tokens = estimate_tokens(messages)
    if current_tokens <= max_tokens:
        return messages  # No pruning needed

    logger.info(
        "Pruning conversation: {} tokens > {} threshold (target: {})",
        current_tokens, max_tokens, target_tokens,
    )

    # Classify messages by type
    system_msgs: list[tuple[int, "Message"]] = []      # (original_index, msg)
    dialogue_msgs: list[tuple[int, "Message"]] = []     # user/assistant without tool_calls
    tool_call_msgs: list[tuple[int, "Message"]] = []    # assistant with tool_calls
    tool_result_msgs: list[tuple[int, "Message"]] = []  # role="tool"

    for i, msg in enumerate(messages):
        if msg.role == "system":
            system_msgs.append((i, msg))
        elif msg.role == "tool":
            tool_result_msgs.append((i, msg))
        elif msg.role == "assistant" and msg.tool_calls:
            tool_call_msgs.append((i, msg))
        else:
            # user or assistant (text-only)
            dialogue_msgs.append((i, msg))

    # Indices that are ALWAYS kept (never pruned)
    keep_indices: set[int] = set()

    # 1. Always keep system messages
    for idx, _ in system_msgs:
        keep_indices.add(idx)

    # 2. Keep last N dialogue pairs (user + assistant)
    recent_dialogue = dialogue_msgs[-(_PRESERVE_DIALOGUE_PAIRS * 2):]
    for idx, _ in recent_dialogue:
        keep_indices.add(idx)

    # 3. Keep last N tool groups (tool_call assistant + tool results)
    recent_tool_calls = tool_call_msgs[-_PRESERVE_TOOL_GROUPS:]
    for idx, _ in recent_tool_calls:
        keep_indices.add(idx)
    recent_tool_results = tool_result_msgs[-_PRESERVE_TOOL_GROUPS:]
    for idx, _ in recent_tool_results:
        keep_indices.add(idx)

    # Build removable candidates (oldest first) — tools first, then dialogue
    removable_tools: list[tuple[int, "Message"]] = [
        (idx, msg) for idx, msg in tool_result_msgs + tool_call_msgs
        if idx not in keep_indices
    ]
    removable_tools.sort(key=lambda t: t[0])  # oldest first

    removable_dialogue: list[tuple[int, "Message"]] = [
        (idx, msg) for idx, msg in dialogue_msgs
        if idx not in keep_indices
    ]
    removable_dialogue.sort(key=lambda t: t[0])  # oldest first

    # Remove from removable pools until we hit target
    removed_indices: set[int] = set()
    tokens_removed = 0

    for pool_name, pool in [("tools", removable_tools), ("dialogue", removable_dialogue)]:
        for idx, msg in pool:
            if current_tokens - tokens_removed <= target_tokens:
                break
            msg_tokens = estimate_message_tokens(msg)
            removed_indices.add(idx)
            tokens_removed += msg_tokens

    # Build pruned list preserving original order
    pruned = [msg for i, msg in enumerate(messages) if i not in removed_indices]

    after_tokens = estimate_tokens(pruned)
    removed_count = len(removed_indices)
    logger.info(
        "Pruning complete: {} → {} tokens ({} messages removed)",
        current_tokens, after_tokens, removed_count,
    )

    return pruned

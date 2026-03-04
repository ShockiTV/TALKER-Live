"""Tests for token estimation and conversation pruning."""

import pytest

from talker_service.llm.models import Message
from talker_service.llm.token_utils import estimate_tokens, estimate_message_tokens
from talker_service.llm.pruning import prune_conversation


# ---------------------------------------------------------------------------
# Token estimation tests (Task 5.2 / 2.1 validation)
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    """Verify the 4-chars-per-token heuristic produces reasonable estimates."""

    def test_short_message(self):
        msg = Message(role="user", content="Hello world")
        tokens = estimate_message_tokens(msg)
        # 11 chars → ~3 tokens + 4 overhead ≈ 7
        assert 5 <= tokens <= 10

    def test_empty_content(self):
        msg = Message(role="system", content="")
        tokens = estimate_message_tokens(msg)
        # Only overhead
        assert tokens == 4

    def test_long_message(self):
        content = "A" * 4000  # 4000 chars → ~1000 tokens + 4 overhead
        msg = Message(role="assistant", content=content)
        tokens = estimate_message_tokens(msg)
        assert 1000 <= tokens <= 1010

    def test_message_with_tool_calls(self):
        msg = Message(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_memories",
                        "arguments": '{"character_id": "123", "tiers": ["events"]}',
                    },
                }
            ],
        )
        tokens = estimate_message_tokens(msg)
        # tool_calls are serialized and counted; should be > overhead
        assert tokens > 10

    def test_estimate_tokens_list(self):
        msgs = [
            Message(role="system", content="System prompt" * 100),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Response"),
        ]
        total = estimate_tokens(msgs)
        assert total == sum(estimate_message_tokens(m) for m in msgs)

    def test_estimate_tokens_empty_list(self):
        assert estimate_tokens([]) == 0


# ---------------------------------------------------------------------------
# Pruning tests (Task 5.2)
# ---------------------------------------------------------------------------


def _make_conversation(
    n_system: int = 1,
    n_dialogue_pairs: int = 10,
    n_tool_groups: int = 5,
    content_size: int = 400,
) -> list[Message]:
    """Helper to build a realistic conversation for pruning tests."""
    msgs: list[Message] = []
    for i in range(n_system):
        msgs.append(Message(role="system", content=f"System prompt {i}. " + "X" * content_size))
    for i in range(n_dialogue_pairs):
        msgs.append(Message(role="user", content=f"User message {i}. " + "Y" * content_size))
        msgs.append(Message(role="assistant", content=f"Assistant reply {i}. " + "Z" * content_size))
    for i in range(n_tool_groups):
        msgs.append(
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {"name": "get_memories", "arguments": f'{{"id": "{i}"}}'},
                    }
                ],
            )
        )
        msgs.append(Message(role="tool", content=f"Tool result {i}. " + "T" * content_size))
    return msgs


class TestPruneConversation:
    """Verify pruning algorithm preserves correct messages."""

    def test_no_pruning_below_threshold(self):
        """If conversation is under max_tokens, return original list."""
        msgs = _make_conversation(n_dialogue_pairs=2, n_tool_groups=1)
        result = prune_conversation(msgs, max_tokens=999_999, target_tokens=500_000)
        assert result is msgs  # identity — not even copied

    def test_pruning_reduces_tokens(self):
        """Large conversation is pruned down to near target."""
        msgs = _make_conversation(n_dialogue_pairs=50, n_tool_groups=20, content_size=800)
        before = estimate_tokens(msgs)
        # Set threshold very low to force pruning
        result = prune_conversation(msgs, max_tokens=100, target_tokens=50)
        after = estimate_tokens(result)
        assert after < before

    def test_system_prompts_always_kept(self):
        """System messages are never removed."""
        msgs = _make_conversation(n_system=3, n_dialogue_pairs=30)
        result = prune_conversation(msgs, max_tokens=100, target_tokens=50)
        system_msgs = [m for m in result if m.role == "system"]
        assert len(system_msgs) == 3

    def test_recent_dialogue_kept(self):
        """Last 5 dialogue pairs (10 messages) are preserved."""
        msgs = _make_conversation(n_dialogue_pairs=20, n_tool_groups=0)
        result = prune_conversation(msgs, max_tokens=100, target_tokens=50)

        # Extract user messages from result
        user_msgs = [m for m in result if m.role == "user"]
        # The last 5 user messages should be present (they come from pairs 15-19)
        assert any("User message 19" in m.content for m in user_msgs)
        assert any("User message 18" in m.content for m in user_msgs)

    def test_recent_tool_groups_kept(self):
        """Last N tool call/result pairs are preserved."""
        msgs = _make_conversation(n_dialogue_pairs=2, n_tool_groups=15)
        result = prune_conversation(msgs, max_tokens=100, target_tokens=50)

        # Last tool results should be kept
        tool_msgs = [m for m in result if m.role == "tool"]
        assert any("Tool result 14" in m.content for m in tool_msgs)

    def test_older_messages_removed_first(self):
        """Oldest dialogue/tool messages are removed before recent ones."""
        msgs = _make_conversation(n_dialogue_pairs=20, n_tool_groups=10)
        result = prune_conversation(msgs, max_tokens=100, target_tokens=50)

        # First user message (index 0 of dialogue) likely removed
        user_msgs_content = [m.content for m in result if m.role == "user"]
        # "User message 0" is oldest and should be removed
        assert not any("User message 0" in c for c in user_msgs_content)

    def test_chronological_order_preserved(self):
        """Pruned messages maintain original order."""
        msgs = _make_conversation(n_dialogue_pairs=20, n_tool_groups=5)
        result = prune_conversation(msgs, max_tokens=100, target_tokens=50)

        # Verify system messages come first
        if result:
            assert result[0].role == "system"

        # Verify user messages appear in order
        user_indices = [
            int(m.content.split(".")[0].split()[-1])
            for m in result
            if m.role == "user" and "User message" in m.content
        ]
        assert user_indices == sorted(user_indices)

    def test_empty_conversation(self):
        """Empty list returns empty list."""
        result = prune_conversation([], max_tokens=100, target_tokens=50)
        assert result == []

    def test_all_system_messages(self):
        """Conversation with only system messages: nothing prunable."""
        msgs = [Message(role="system", content=f"Sys {i}") for i in range(5)]
        result = prune_conversation(msgs, max_tokens=0, target_tokens=0)
        assert len(result) == 5  # all kept

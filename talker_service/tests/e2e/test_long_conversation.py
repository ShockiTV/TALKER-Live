"""E2E test for long conversations with the Responses API.

Validates that persistent conversation state in OpenAIClient grows over
multiple events, that previous_response_id threading works correctly,
and that reset_conversation() clears all state.

Server-side truncation (``truncation="auto"``) replaces client-side pruning.
These tests exercise the OpenAIClient's conversation persistence at the
unit/integration boundary — no live LLM needed.

Key assertions:
- Conversation grows across multiple complete_with_tools() calls
- previous_response_id is threaded across calls
- reset_conversation() clears thread ID and messages
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from talker_service.llm.openai_client import OpenAIClient
from talker_service.llm.models import Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_output_message(text: str = "OK"):
    """Build a mock ResponseOutputMessage object."""
    content_item = MagicMock()
    content_item.type = "output_text"
    content_item.text = text
    msg = MagicMock()
    msg.type = "message"
    msg.content = [content_item]
    return msg


def _mock_function_call(call_id: str, name: str, arguments: dict):
    """Build a mock ResponseFunctionToolCall object."""
    item = MagicMock()
    item.type = "function_call"
    item.call_id = call_id
    item.name = name
    item.arguments = json.dumps(arguments)
    return item


def _make_responses_api_response(
    response_id: str = "resp_test",
    text: str = "OK",
    tool_calls: list | None = None,
):
    """Build a mock Responses API Response object."""
    output = []
    if tool_calls:
        output.extend(tool_calls)
    else:
        output.append(_mock_output_message(text))
    resp = MagicMock()
    resp.id = response_id
    resp.output = output
    return resp


DUMMY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_info",
            "description": "Test tool",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
    }
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLongConversation:
    """Tests for conversation persistence and threading across multiple events."""

    async def test_conversation_grows_across_calls(self):
        """Conversation accumulates messages over multiple complete_with_tools calls."""
        client = OpenAIClient(api_key="test-key", model="gpt-4o-mini")

        resp1 = _make_responses_api_response("resp_1", "Response 1")
        resp2 = _make_responses_api_response("resp_2", "Response 2")
        resp3 = _make_responses_api_response("resp_3", "Response 3")
        client._client.responses.create = AsyncMock(side_effect=[resp1, resp2, resp3])

        system = Message(role="system", content="You are a test assistant.")
        user1 = Message(role="user", content="Event 1: A stalker was killed.")

        await client.complete_with_tools([system, user1], tools=DUMMY_TOOLS)
        conv_after_1 = client.get_conversation()

        # Should have: system + user + assistant
        assert len(conv_after_1) >= 3

        # Second call — add more messages
        user2 = Message(role="user", content="Event 2: An artifact was found.")
        await client.complete_with_tools([user2], tools=DUMMY_TOOLS)
        conv_after_2 = client.get_conversation()

        # Conversation should have grown
        assert len(conv_after_2) > len(conv_after_1)

        # Third call
        user3 = Message(role="user", content="Event 3: An emission is approaching.")
        await client.complete_with_tools([user3], tools=DUMMY_TOOLS)
        conv_after_3 = client.get_conversation()

        assert len(conv_after_3) > len(conv_after_2)

    async def test_previous_response_id_threaded(self):
        """previous_response_id is passed to subsequent calls."""
        client = OpenAIClient(api_key="test-key", model="gpt-4o-mini")

        resp1 = _make_responses_api_response("resp_first", "Reply 1")
        resp2 = _make_responses_api_response("resp_second", "Reply 2")
        client._client.responses.create = AsyncMock(side_effect=[resp1, resp2])

        system = Message(role="system", content="System.")
        user1 = Message(role="user", content="Event 1.")
        await client.complete_with_tools([system, user1], tools=DUMMY_TOOLS)

        # First call should NOT have previous_response_id
        first_kwargs = client._client.responses.create.call_args_list[0][1]
        assert "previous_response_id" not in first_kwargs
        assert client._last_response_id == "resp_first"

        user2 = Message(role="user", content="Event 2.")
        await client.complete_with_tools([user2], tools=DUMMY_TOOLS)

        # Second call SHOULD have previous_response_id from first
        second_kwargs = client._client.responses.create.call_args_list[1][1]
        assert second_kwargs["previous_response_id"] == "resp_first"
        assert client._last_response_id == "resp_second"

    async def test_truncation_auto_always_set(self):
        """truncation='auto' is always included in requests."""
        client = OpenAIClient(api_key="test-key", model="gpt-4o-mini")

        resp = _make_responses_api_response("resp_1", "OK")
        client._client.responses.create = AsyncMock(return_value=resp)

        system = Message(role="system", content="System.")
        user = Message(role="user", content="Event.")
        await client.complete_with_tools([system, user], tools=DUMMY_TOOLS)

        call_kwargs = client._client.responses.create.call_args[1]
        assert call_kwargs["truncation"] == "auto"

    async def test_many_events_conversation_integrity(self):
        """Conversation remains well-formed after many events."""
        client = OpenAIClient(api_key="test-key", model="gpt-4o-mini")

        responses = [
            _make_responses_api_response(f"resp_{i}", f"Reply {i}: " + "w" * 50)
            for i in range(12)
        ]
        client._client.responses.create = AsyncMock(side_effect=responses)

        system = Message(role="system", content="System prompt text here.")
        for i in range(12):
            user = Message(role="user", content=f"EVENT_{i}_" + "q" * 50)
            if i == 0:
                await client.complete_with_tools([system, user], tools=DUMMY_TOOLS)
            else:
                await client.complete_with_tools([user], tools=DUMMY_TOOLS)

        conv = client.get_conversation()

        # All messages should have valid roles
        valid_roles = {"system", "user", "assistant", "tool"}
        for msg in conv:
            assert msg.role in valid_roles, f"Invalid role: {msg.role}"

        # The most recent events should still be in the conversation
        all_content = " ".join(m.content for m in conv if m.content)
        assert "EVENT_11_" in all_content, "Most recent user message should be preserved"
        assert "Reply 11" in all_content, "Most recent assistant reply should be preserved"

    async def test_reset_conversation_clears_state(self):
        """reset_conversation() clears all accumulated messages and thread ID."""
        client = OpenAIClient(api_key="test-key", model="gpt-4o-mini")

        resp = _make_responses_api_response("resp_abc", "Hello")
        client._client.responses.create = AsyncMock(return_value=resp)

        system = Message(role="system", content="Test system.")
        user = Message(role="user", content="Test user.")
        await client.complete_with_tools([system, user], tools=DUMMY_TOOLS)

        assert len(client.get_conversation()) >= 3
        assert client._last_response_id == "resp_abc"

        client.reset_conversation()
        assert len(client.get_conversation()) == 0
        assert client._last_response_id is None

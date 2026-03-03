"""Unit tests for LLM tool-calling infrastructure.

Covers:
- ToolCall, ToolResult, LLMToolResponse models (5.1)
- Message.tool_result() factory and Message.to_dict() with tool fields (5.2)
- BaseLLMClient._parse_tool_calls() (5.3)
- BaseLLMClient._build_tool_response() (5.4)
- OpenAIClient.complete_with_tools() (5.5)
- OllamaClient.complete_with_tools() (5.6)
- ConversationManager tool loop (5.7)
- _handle_background() handler (5.8)
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.llm.models import (
    LLMToolResponse,
    Message,
    ToolCall,
    ToolResult,
)
from talker_service.llm.base import BaseLLMClient, LLMError
from talker_service.llm.openai_client import OpenAIClient
from talker_service.llm.openrouter_client import OpenRouterClient
from talker_service.llm.ollama_client import OllamaClient
from talker_service.llm.proxy_client import ProxyClient
from talker_service.dialogue.conversation import ConversationManager


# -----------------------------------------------------------------------
# 5.1  ToolCall / ToolResult / LLMToolResponse
# -----------------------------------------------------------------------


class TestToolCallModel:
    """Tests for the ToolCall dataclass."""

    def test_creation(self):
        tc = ToolCall(id="call_abc123", name="get_memories", arguments={"character_id": "12467", "tiers": ["events"]})
        assert tc.id == "call_abc123"
        assert tc.name == "get_memories"
        assert tc.arguments == {"character_id": "12467", "tiers": ["events"]}

    def test_empty_arguments(self):
        tc = ToolCall(id="call_1", name="noop", arguments={})
        assert tc.arguments == {}


class TestToolResultModel:
    """Tests for the ToolResult dataclass."""

    def test_creation(self):
        tr = ToolResult(tool_call_id="call_abc", name="get_memories", content='{"events": []}')
        assert tr.tool_call_id == "call_abc"
        assert tr.name == "get_memories"
        assert tr.content == '{"events": []}'


class TestLLMToolResponse:
    """Tests for the LLMToolResponse dataclass."""

    def test_text_only(self):
        r = LLMToolResponse(text="Hello world", tool_calls=[])
        assert r.text == "Hello world"
        assert r.tool_calls == []
        assert r.has_tool_calls is False

    def test_tool_calls_only(self):
        tc = ToolCall(id="call_1", name="t", arguments={})
        r = LLMToolResponse(text=None, tool_calls=[tc])
        assert r.text is None
        assert r.has_tool_calls is True

    def test_defaults(self):
        r = LLMToolResponse()
        assert r.text is None
        assert r.tool_calls == []
        assert r.has_tool_calls is False


# -----------------------------------------------------------------------
# 5.2  Message.tool_result() / Message.to_dict() with tool fields
# -----------------------------------------------------------------------


class TestMessageToolFields:
    """Tests for Message model tool-calling extensions."""

    def test_standard_message_unchanged(self):
        """Standard message serialization has no extra fields."""
        msg = Message(role="user", content="hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "hello"}
        assert "tool_calls" not in d
        assert "tool_call_id" not in d
        assert "name" not in d

    def test_tool_result_factory(self):
        msg = Message.tool_result("call_1", "get_memories", '{"events": []}')
        assert msg.role == "tool"
        assert msg.content == '{"events": []}'
        assert msg.tool_call_id == "call_1"
        assert msg.name == "get_memories"

    def test_tool_result_to_dict(self):
        msg = Message.tool_result("call_1", "get_memories", '{"events": []}')
        d = msg.to_dict()
        assert d["role"] == "tool"
        assert d["content"] == '{"events": []}'
        assert d["tool_call_id"] == "call_1"
        assert d["name"] == "get_memories"

    def test_assistant_message_with_tool_calls(self):
        tc = ToolCall(id="call_1", name="get_memories", arguments={"character_id": "42"})
        msg = Message(role="assistant", content="", tool_calls=[tc])
        d = msg.to_dict()

        assert "tool_calls" in d
        assert len(d["tool_calls"]) == 1
        call = d["tool_calls"][0]
        assert call["id"] == "call_1"
        assert call["type"] == "function"
        assert call["function"]["name"] == "get_memories"
        assert json.loads(call["function"]["arguments"]) == {"character_id": "42"}

    def test_system_message_no_tool_fields(self):
        msg = Message.system("prompt")
        d = msg.to_dict()
        assert "tool_calls" not in d
        assert "tool_call_id" not in d


# -----------------------------------------------------------------------
# 5.3  BaseLLMClient._parse_tool_calls()
# -----------------------------------------------------------------------


class TestParseToolCalls:
    """Tests for BaseLLMClient._parse_tool_calls()."""

    def test_normal_openai_format(self):
        raw = [
            {
                "id": "call_abc",
                "type": "function",
                "function": {
                    "name": "get_memories",
                    "arguments": '{"character_id": "42", "tiers": ["events"]}',
                },
            }
        ]
        parsed = BaseLLMClient._parse_tool_calls(raw)
        assert len(parsed) == 1
        assert parsed[0].id == "call_abc"
        assert parsed[0].name == "get_memories"
        assert parsed[0].arguments == {"character_id": "42", "tiers": ["events"]}

    def test_missing_id_generates_synthetic(self):
        raw = [
            {
                "type": "function",
                "function": {
                    "name": "background",
                    "arguments": "{}",
                },
            }
        ]
        parsed = BaseLLMClient._parse_tool_calls(raw)
        assert len(parsed) == 1
        assert parsed[0].id.startswith("call_")
        assert len(parsed[0].id) == 13  # "call_" + 8 hex chars

    def test_empty_list(self):
        assert BaseLLMClient._parse_tool_calls([]) == []

    def test_arguments_already_dict(self):
        """Ollama may return arguments as a dict instead of JSON string."""
        raw = [
            {
                "id": "call_1",
                "function": {
                    "name": "get_memories",
                    "arguments": {"character_id": "10"},
                },
            }
        ]
        parsed = BaseLLMClient._parse_tool_calls(raw)
        assert parsed[0].arguments == {"character_id": "10"}

    def test_invalid_json_arguments(self):
        """Malformed JSON string falls back to empty dict."""
        raw = [
            {
                "id": "call_x",
                "function": {
                    "name": "foo",
                    "arguments": "{not valid json",
                },
            }
        ]
        parsed = BaseLLMClient._parse_tool_calls(raw)
        assert parsed[0].arguments == {}

    def test_multiple_tool_calls(self):
        raw = [
            {"id": "call_1", "function": {"name": "a", "arguments": "{}"}},
            {"id": "call_2", "function": {"name": "b", "arguments": "{}"}},
        ]
        parsed = BaseLLMClient._parse_tool_calls(raw)
        assert len(parsed) == 2
        assert parsed[0].name == "a"
        assert parsed[1].name == "b"


# -----------------------------------------------------------------------
# 5.4  BaseLLMClient._build_tool_response()
# -----------------------------------------------------------------------


class TestBuildToolResponse:
    """Tests for BaseLLMClient._build_tool_response()."""

    def test_text_only_openai(self):
        data = {
            "choices": [
                {"message": {"content": "Hello!", "role": "assistant"}}
            ]
        }
        r = BaseLLMClient._build_tool_response(data)
        assert r.text == "Hello!"
        assert r.tool_calls == []
        assert r.has_tool_calls is False

    def test_tool_calls_only_openai(self):
        data = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "get_memories",
                                    "arguments": '{"character_id": "1"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        r = BaseLLMClient._build_tool_response(data)
        assert r.text is None
        assert r.has_tool_calls is True
        assert r.tool_calls[0].name == "get_memories"

    def test_both_text_and_tool_calls_prioritizes_tools(self):
        """When both text and tool_calls are present, tool_calls win."""
        data = {
            "choices": [
                {
                    "message": {
                        "content": "some text",
                        "tool_calls": [
                            {
                                "id": "c1",
                                "function": {"name": "t", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ]
        }
        r = BaseLLMClient._build_tool_response(data)
        assert r.text is None
        assert r.has_tool_calls is True

    def test_ollama_format_text(self):
        data = {"message": {"content": "Ollama says hi", "role": "assistant"}}
        r = BaseLLMClient._build_tool_response(data)
        assert r.text == "Ollama says hi"
        assert r.tool_calls == []

    def test_ollama_format_tool_calls(self):
        data = {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "background",
                            "arguments": {"character_id": "5", "action": "read"},
                        },
                    }
                ],
            }
        }
        r = BaseLLMClient._build_tool_response(data)
        assert r.has_tool_calls is True
        assert r.tool_calls[0].arguments["action"] == "read"
        # Synthetic ID since Ollama didn't provide one
        assert r.tool_calls[0].id.startswith("call_")

    def test_empty_content_returns_empty_string(self):
        data = {"choices": [{"message": {"content": None}}]}
        r = BaseLLMClient._build_tool_response(data)
        assert r.text == ""
        assert r.has_tool_calls is False


# -----------------------------------------------------------------------
# 5.5  OpenAIClient.complete_with_tools()
# -----------------------------------------------------------------------


class TestOpenAICompleteWithTools:
    """Tests for OpenAIClient.complete_with_tools()."""

    @pytest.fixture
    def tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_memories",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    @pytest.fixture
    def sample_messages(self):
        return [Message.system("sys"), Message.user("hi")]

    @pytest.mark.asyncio
    async def test_tool_call_response(self, sample_messages, tools):
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        api_response = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "get_memories",
                                    "arguments": '{"character_id": "1", "tiers": ["events"]}',
                                },
                            }
                        ],
                    }
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = api_response

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await client.complete_with_tools(sample_messages, tools)

        assert result.has_tool_calls
        assert result.tool_calls[0].name == "get_memories"

        # Verify tools were in the request body
        call_kwargs = mock_post.call_args
        body = call_kwargs[1]["json"]
        assert "tools" in body
        assert body["tools"] == tools

    @pytest.mark.asyncio
    async def test_text_response(self, sample_messages, tools):
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        api_response = {
            "choices": [{"message": {"content": "[SPEAKER: npc1] Hello"}}]
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = api_response

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await client.complete_with_tools(sample_messages, tools)

        assert not result.has_tool_calls
        assert result.text == "[SPEAKER: npc1] Hello"

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, sample_messages, tools):
        client = OpenAIClient(api_key="test-key", timeout=10.0, max_retries=2)

        rate_resp = MagicMock()
        rate_resp.status_code = 429
        rate_resp.text = "Rate limited"

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [rate_resp, ok_resp]
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete_with_tools(sample_messages, tools)

        assert result.text == "ok"
        assert mock_post.call_count == 2


# -----------------------------------------------------------------------
# 5.6  OllamaClient.complete_with_tools() — synthetic ID generation
# -----------------------------------------------------------------------


class TestOllamaCompleteWithTools:
    """Tests for OllamaClient.complete_with_tools()."""

    @pytest.fixture
    def tools(self):
        return [{"type": "function", "function": {"name": "t", "parameters": {}}}]

    @pytest.fixture
    def sample_messages(self):
        return [Message.system("sys"), Message.user("hi")]

    @pytest.mark.asyncio
    async def test_tool_call_with_synthetic_id(self, sample_messages, tools):
        client = OllamaClient(timeout=10.0)

        api_response = {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_memories",
                            "arguments": {"character_id": "5"},
                        },
                    }
                ],
            }
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = api_response

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await client.complete_with_tools(sample_messages, tools)

        assert result.has_tool_calls
        assert result.tool_calls[0].id.startswith("call_")
        assert result.tool_calls[0].arguments == {"character_id": "5"}

        # Verify tools were in request body
        body = mock_post.call_args[1]["json"]
        assert "tools" in body

    @pytest.mark.asyncio
    async def test_text_only_model_no_tool_support(self, sample_messages, tools):
        """Model that doesn't support tools just returns text."""
        client = OllamaClient(timeout=10.0)

        api_response = {"message": {"content": "I cannot call tools", "role": "assistant"}}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = api_response

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await client.complete_with_tools(sample_messages, tools)

        assert not result.has_tool_calls
        assert result.text == "I cannot call tools"


# -----------------------------------------------------------------------
# 5.7  ConversationManager tool loop
# -----------------------------------------------------------------------


class TestConversationManagerToolLoop:
    """Tests for the ConversationManager tool-calling loop."""

    @pytest.fixture
    def mock_state_client(self):
        client = AsyncMock()
        # Default: execute_batch returns empty results
        mock_result = MagicMock()
        mock_result.ok.return_value = True
        mock_result.__getitem__ = MagicMock(return_value=[])
        client.execute_batch.return_value = mock_result
        client.mutate_batch.return_value = True
        return client

    @pytest.fixture
    def mock_llm_client(self):
        return AsyncMock()

    @pytest.fixture
    def manager(self, mock_llm_client, mock_state_client):
        return ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            max_tool_iterations=5,
        )

    @pytest.fixture
    def event_data(self):
        return {
            "type": "death",
            "context": {
                "actor": {"name": "Wolf", "faction": "stalker", "game_id": "wolf"},
                "victim": {"name": "Bandit", "faction": "bandit", "game_id": "bandit_1"},
            },
        }

    @pytest.fixture
    def candidates(self):
        return [
            {"game_id": "wolf", "name": "Wolf", "faction": "stalker"},
            {"game_id": "npc_2", "name": "Fanatic", "faction": "stalker"},
        ]

    @pytest.fixture
    def traits(self):
        return {
            "wolf": {"personality_id": "generic.1", "backstory_id": ""},
            "npc_2": {"personality_id": "generic.2", "backstory_id": ""},
        }

    @pytest.mark.asyncio
    async def test_direct_text_response_no_tools(self, manager, mock_llm_client, event_data, candidates, traits):
        """LLM returns text directly without calling any tools."""
        mock_llm_client.complete_with_tools.return_value = LLMToolResponse(
            text="[SPEAKER: wolf] That's what you get!",
            tool_calls=[],
        )

        speaker_id, dialogue = await manager.handle_event(event_data, candidates, "Rostok, afternoon", traits)

        assert speaker_id == "wolf"
        assert "That's what you get!" in dialogue
        mock_llm_client.complete_with_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_call_then_text(self, manager, mock_llm_client, event_data, candidates, traits):
        """LLM calls a tool, gets result, then produces text."""
        tool_call = ToolCall(id="call_1", name="get_memories", arguments={"character_id": "wolf", "tiers": ["events"]})

        # First call: tool request.  Second call: text response.
        mock_llm_client.complete_with_tools.side_effect = [
            LLMToolResponse(text=None, tool_calls=[tool_call]),
            LLMToolResponse(text="[SPEAKER: wolf] I remember that bastard.", tool_calls=[]),
        ]

        speaker_id, dialogue = await manager.handle_event(event_data, candidates, "Rostok", traits)

        assert speaker_id == "wolf"
        assert "I remember that bastard." in dialogue
        assert mock_llm_client.complete_with_tools.call_count == 2

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_single_response(self, manager, mock_llm_client, event_data, candidates, traits):
        """LLM requests multiple tools in one message."""
        tc1 = ToolCall(id="call_1", name="get_memories", arguments={"character_id": "wolf", "tiers": ["events"]})
        tc2 = ToolCall(id="call_2", name="background", arguments={"character_id": "wolf", "action": "read"})

        mock_llm_client.complete_with_tools.side_effect = [
            LLMToolResponse(text=None, tool_calls=[tc1, tc2]),
            LLMToolResponse(text="[SPEAKER: wolf] Die!", tool_calls=[]),
        ]

        speaker_id, dialogue = await manager.handle_event(event_data, candidates, "W", traits)

        assert dialogue == "Die!"
        assert mock_llm_client.complete_with_tools.call_count == 2

    @pytest.mark.asyncio
    async def test_max_iterations_exhausted(self, manager, mock_llm_client, event_data, candidates, traits):
        """Tool loop hits max iterations → returns empty dialogue."""
        forever_tc = ToolCall(id="call_loop", name="get_memories", arguments={"character_id": "wolf", "tiers": ["events"]})

        # Always return tool calls, never text
        mock_llm_client.complete_with_tools.return_value = LLMToolResponse(
            text=None, tool_calls=[forever_tc],
        )

        speaker_id, dialogue = await manager.handle_event(event_data, candidates, "W", traits)

        assert dialogue == ""
        assert mock_llm_client.complete_with_tools.call_count == manager.max_tool_iterations

    @pytest.mark.asyncio
    async def test_tool_calls_dispatched_for_character(self, manager, mock_llm_client, event_data, candidates, traits):
        """Tool calls with character_id are dispatched to handlers."""
        tc = ToolCall(id="c1", name="get_memories", arguments={"character_id": "npc_99", "tiers": ["events"]})

        mock_llm_client.complete_with_tools.side_effect = [
            LLMToolResponse(text=None, tool_calls=[tc]),
            LLMToolResponse(text="[SPEAKER: wolf] ok", tool_calls=[]),
        ]

        await manager.handle_event(event_data, candidates, "W", traits)

        # Tool call was dispatched — verify by checking the LLM received 2 calls
        assert mock_llm_client.complete_with_tools.call_count == 2


# -----------------------------------------------------------------------
# 5.8  _handle_background() handler
# -----------------------------------------------------------------------


class TestHandleBackground:
    """Tests for ConversationManager._handle_background()."""

    @pytest.fixture
    def mock_state_client(self):
        client = AsyncMock()
        mock_result = MagicMock()
        mock_result.ok.return_value = True
        mock_result.__getitem__ = MagicMock(return_value={"traits": ["brave"], "backstory": "A legend"})
        client.execute_batch.return_value = mock_result
        client.mutate_batch.return_value = True
        return client

    @pytest.fixture
    def manager(self, mock_state_client):
        mock_llm = AsyncMock()
        return ConversationManager(
            llm_client=mock_llm,
            state_client=mock_state_client,
        )

    @pytest.mark.asyncio
    async def test_read_action(self, manager, mock_state_client):
        result = await manager._handle_background(character_id="42", action="read")
        assert result == {"traits": ["brave"], "backstory": "A legend"}
        mock_state_client.execute_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_action(self, manager, mock_state_client):
        content = {"traits": ["cunning"], "backstory": "A survivor", "connections": []}
        result = await manager._handle_background(character_id="42", action="write", content=content)
        assert result["success"] is True
        assert result["action"] == "write"
        mock_state_client.mutate_batch.assert_called_once()

        # Verify mutation payload
        mutations = mock_state_client.mutate_batch.call_args[0][0]
        assert mutations[0]["verb"] == "set"
        assert mutations[0]["resource"] == "memory.background"
        assert mutations[0]["data"] == content

    @pytest.mark.asyncio
    async def test_update_action(self, manager, mock_state_client):
        result = await manager._handle_background(
            character_id="42", action="update", field="connections", value=["knows Sidorovich"],
        )
        assert result["success"] is True
        assert result["action"] == "update"
        assert result["field"] == "connections"

        mutations = mock_state_client.mutate_batch.call_args[0][0]
        assert mutations[0]["verb"] == "update"
        assert mutations[0]["data"] == {"connections": ["knows Sidorovich"]}

    @pytest.mark.asyncio
    async def test_write_without_content_returns_error(self, manager):
        result = await manager._handle_background(character_id="42", action="write")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_without_field_returns_error(self, manager):
        result = await manager._handle_background(character_id="42", action="update")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, manager):
        result = await manager._handle_background(character_id="42", action="delete")
        assert "error" in result


# -----------------------------------------------------------------------
# 5.9  Verify existing complete() tests still pass (backward compat)
#
# The actual existing tests are in test_llm_clients.py. Here we just
# verify the Message backward compatibility.
# -----------------------------------------------------------------------


class TestBackwardCompatibility:
    """Verify that existing patterns still work after tool-calling additions."""

    def test_message_role_literals_include_original(self):
        """system/user/assistant still work."""
        for role in ("system", "user", "assistant"):
            msg = Message(role=role, content="test")  # type: ignore[arg-type]
            assert msg.role == role

    def test_message_to_dict_without_tool_fields(self):
        """Old-style Message(role, content) serializes identically."""
        msg = Message(role="user", content="Hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "Hello"}
        assert len(d) == 2

    def test_factory_methods_unchanged(self):
        assert Message.system("s").role == "system"
        assert Message.user("u").content == "u"
        assert Message.assistant("a").role == "assistant"

    def test_llm_options_unchanged(self):
        from talker_service.llm.models import LLMOptions
        opts = LLMOptions(temperature=0.5)
        assert opts.temperature == 0.5

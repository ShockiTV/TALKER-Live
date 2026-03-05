"""Unit tests for LLM tool-calling infrastructure.

Covers:
- ToolCall, ToolResult, LLMToolResponse models (5.1)
- Message.tool_result() factory and Message.to_dict() with tool fields (5.2)
- BaseLLMClient._parse_tool_calls() (5.3)
- BaseLLMClient._build_tool_response() (5.4)
- OpenAIClient.complete_with_tools() via Responses API (5.5)
- OllamaClient.complete_with_tools() (5.6)
- OpenAIClient.complete_with_tool_loop() native Responses API tool loop (5.7)
- ConversationManager tool loop (5.8)
- _handle_background() handler (5.9)
"""

import json

import openai
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.llm.models import (
    LLMOptions,
    LLMToolResponse,
    Message,
    ReasoningOptions,
    ToolCall,
    ToolResult,
)
from talker_service.llm.base import BaseLLMClient, LLMError, RateLimitError
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


class TestReasoningOptionsModel:
    """Tests for the ReasoningOptions dataclass."""

    def test_defaults_are_none(self):
        r = ReasoningOptions()
        assert r.effort is None
        assert r.summary is None
        assert not r  # falsy when empty

    def test_effort_only(self):
        r = ReasoningOptions(effort="low")
        assert r.effort == "low"
        assert r.summary is None
        assert r  # truthy
        assert r.to_dict() == {"effort": "low"}

    def test_full(self):
        r = ReasoningOptions(effort="high", summary="auto")
        assert r.to_dict() == {"effort": "high", "summary": "auto"}
        assert r  # truthy

    def test_summary_only(self):
        r = ReasoningOptions(summary="concise")
        assert r.to_dict() == {"summary": "concise"}
        assert r

    def test_llm_options_with_reasoning(self):
        opts = LLMOptions(reasoning=ReasoningOptions(effort="medium", summary="auto"))
        assert opts.reasoning is not None
        assert opts.reasoning.effort == "medium"

    def test_llm_options_without_reasoning(self):
        opts = LLMOptions()
        assert opts.reasoning is None


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
# 5.5  OpenAIClient.complete_with_tools() — Responses API
# -----------------------------------------------------------------------


def _mock_function_call(call_id="call_abc", name="get_memories", arguments='{"character_id": "1", "tiers": ["events"]}'):
    """Build a mock ResponseFunctionToolCall object."""
    item = MagicMock()
    item.type = "function_call"
    item.call_id = call_id
    item.name = name
    item.arguments = arguments
    return item


def _mock_output_message(text="[SPEAKER: npc1] Hello"):
    """Build a mock ResponseOutputMessage object."""
    content_item = MagicMock()
    content_item.type = "output_text"
    content_item.text = text
    msg = MagicMock()
    msg.type = "message"
    msg.content = [content_item]
    return msg


def _mock_responses_api(response_id="resp_abc123", output=None):
    """Build a mock Responses API Response object."""
    resp = MagicMock()
    resp.id = response_id
    resp.output = output or []
    return resp


class TestOpenAICompleteWithTools:
    """Tests for OpenAIClient.complete_with_tools() via Responses API."""

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

        tool_call_item = _mock_function_call(
            call_id="call_abc",
            name="get_memories",
            arguments='{"character_id": "1", "tiers": ["events"]}',
        )
        mock_resp = _mock_responses_api(response_id="resp_1", output=[tool_call_item])
        client._client.responses.create = AsyncMock(return_value=mock_resp)

        result = await client.complete_with_tools(sample_messages, tools)

        assert result.has_tool_calls
        assert result.tool_calls[0].name == "get_memories"
        assert result.tool_calls[0].id == "call_abc"

        # Verify tools were converted and passed
        call_kwargs = client._client.responses.create.call_args[1]
        assert "tools" in call_kwargs
        # Converted to Responses format: no nested "function" key
        assert call_kwargs["tools"][0]["name"] == "get_memories"

    @pytest.mark.asyncio
    async def test_text_response(self, sample_messages, tools):
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        text_item = _mock_output_message("[SPEAKER: npc1] Hello")
        mock_resp = _mock_responses_api(response_id="resp_2", output=[text_item])
        client._client.responses.create = AsyncMock(return_value=mock_resp)

        result = await client.complete_with_tools(sample_messages, tools)

        assert not result.has_tool_calls
        assert result.text == "[SPEAKER: npc1] Hello"

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, sample_messages, tools):
        client = OpenAIClient(api_key="test-key", timeout=10.0, max_retries=2)

        text_item = _mock_output_message("ok")
        ok_resp = _mock_responses_api(response_id="resp_ok", output=[text_item])

        rate_err = openai.RateLimitError(
            message="Rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        client._client.responses.create = AsyncMock(side_effect=[rate_err, ok_resp])

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.complete_with_tools(sample_messages, tools)

        assert result.text == "ok"
        assert client._client.responses.create.call_count == 2


class TestConvertTools:
    """Tests for OpenAIClient._convert_tools()."""

    def test_converts_chat_completions_format(self):
        """Chat Completions tools are flattened for Responses API."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_memories",
                    "description": "Recall memories",
                    "parameters": {"type": "object", "properties": {"id": {"type": "string"}}},
                },
            }
        ]
        result = OpenAIClient._convert_tools(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["name"] == "get_memories"
        assert result[0]["description"] == "Recall memories"
        assert "function" not in result[0]

    def test_passthrough_already_flat(self):
        """Tools already in Responses format pass through."""
        tools = [{"type": "function", "name": "t", "parameters": {}}]
        result = OpenAIClient._convert_tools(tools)
        assert result == tools

    def test_empty_list(self):
        assert OpenAIClient._convert_tools([]) == []


class TestResponseIdThreading:
    """Tests for previous_response_id conversation threading."""

    @pytest.fixture
    def tools(self):
        return [{"type": "function", "function": {"name": "t", "parameters": {}}}]

    @pytest.fixture
    def sample_messages(self):
        return [Message.system("sys"), Message.user("hi")]

    @pytest.mark.asyncio
    async def test_first_call_has_no_previous_id(self, sample_messages, tools):
        client = OpenAIClient(api_key="test-key", timeout=10.0)
        assert client._last_response_id is None

        text_item = _mock_output_message("first")
        mock_resp = _mock_responses_api(response_id="resp_1", output=[text_item])
        client._client.responses.create = AsyncMock(return_value=mock_resp)

        await client.complete_with_tools(sample_messages, tools)

        call_kwargs = client._client.responses.create.call_args[1]
        assert "previous_response_id" not in call_kwargs
        assert client._last_response_id == "resp_1"

    @pytest.mark.asyncio
    async def test_second_call_threads_previous_id(self, sample_messages, tools):
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        resp1 = _mock_responses_api(response_id="resp_1", output=[_mock_output_message("first")])
        resp2 = _mock_responses_api(response_id="resp_2", output=[_mock_output_message("second")])
        client._client.responses.create = AsyncMock(side_effect=[resp1, resp2])

        await client.complete_with_tools(sample_messages, tools)
        await client.complete_with_tools(sample_messages, tools)

        second_call_kwargs = client._client.responses.create.call_args_list[1][1]
        assert second_call_kwargs["previous_response_id"] == "resp_1"
        assert client._last_response_id == "resp_2"


class TestNotFoundErrorRecovery:
    """Tests for NotFoundError recovery (expired/invalid previous_response_id)."""

    @pytest.fixture
    def tools(self):
        return [{"type": "function", "function": {"name": "t", "parameters": {}}}]

    @pytest.fixture
    def sample_messages(self):
        return [Message.system("sys"), Message.user("hi")]

    @pytest.mark.asyncio
    async def test_not_found_clears_thread_and_retries(self, sample_messages, tools):
        client = OpenAIClient(api_key="test-key", timeout=10.0, max_retries=3)
        client._last_response_id = "resp_expired"

        text_item = _mock_output_message("recovered")
        ok_resp = _mock_responses_api(response_id="resp_new", output=[text_item])

        not_found_err = openai.NotFoundError(
            message="Response not found",
            response=MagicMock(status_code=404, headers={}),
            body=None,
        )
        client._client.responses.create = AsyncMock(side_effect=[not_found_err, ok_resp])

        result = await client.complete_with_tools(sample_messages, tools)

        assert result.text == "recovered"
        assert client._last_response_id == "resp_new"
        # First call had previous_response_id, second did not
        first_call_kwargs = client._client.responses.create.call_args_list[0][1]
        second_call_kwargs = client._client.responses.create.call_args_list[1][1]
        assert first_call_kwargs["previous_response_id"] == "resp_expired"
        assert "previous_response_id" not in second_call_kwargs

    @pytest.mark.asyncio
    async def test_reset_conversation_clears_thread_id(self):
        client = OpenAIClient(api_key="test-key", timeout=10.0)
        client._last_response_id = "resp_123"
        client._conversation = [Message.system("sys")]

        client.reset_conversation()

        assert client._last_response_id is None
        assert client.get_conversation() == []

    @pytest.mark.asyncio
    async def test_bad_request_with_stale_thread_clears_and_retries(self, sample_messages, tools):
        """BadRequestError from stale previous_response_id clears state and retries."""
        client = OpenAIClient(api_key="test-key", timeout=10.0, max_retries=3)
        client._last_response_id = "resp_stale_with_unresolved_tools"

        text_item = _mock_output_message("recovered")
        ok_resp = _mock_responses_api(response_id="resp_fresh", output=[text_item])

        bad_request_err = openai.BadRequestError(
            message="No tool output found for function call call_abc",
            response=MagicMock(status_code=400, headers={}),
            body=None,
        )
        client._client.responses.create = AsyncMock(side_effect=[bad_request_err, ok_resp])

        result = await client.complete_with_tools(sample_messages, tools)

        assert result.text == "recovered"
        assert client._last_response_id == "resp_fresh"
        # First call had previous_response_id, second did not
        first_kwargs = client._client.responses.create.call_args_list[0][1]
        second_kwargs = client._client.responses.create.call_args_list[1][1]
        assert first_kwargs["previous_response_id"] == "resp_stale_with_unresolved_tools"
        assert "previous_response_id" not in second_kwargs

    @pytest.mark.asyncio
    async def test_bad_request_without_thread_raises(self, sample_messages, tools):
        """BadRequestError without an active thread is not recoverable."""
        client = OpenAIClient(api_key="test-key", timeout=10.0, max_retries=3)
        client._last_response_id = None  # No active thread

        bad_request_err = openai.BadRequestError(
            message="Invalid parameter",
            response=MagicMock(status_code=400, headers={}),
            body=None,
        )
        client._client.responses.create = AsyncMock(side_effect=bad_request_err)

        with pytest.raises(LLMError, match="OpenAI API error"):
            await client.complete_with_tools(sample_messages, tools)


# -----------------------------------------------------------------------
# 5.7  OpenAIClient.complete_with_tool_loop() — native Responses API
# -----------------------------------------------------------------------


class TestNativeToolLoop:
    """Tests for OpenAIClient.complete_with_tool_loop() native Responses API loop."""

    @pytest.fixture
    def tools(self):
        return [{"type": "function", "function": {"name": "get_memories", "parameters": {}}}]

    @pytest.fixture
    def sample_messages(self):
        return [Message.system("sys"), Message.user("event")]

    @staticmethod
    async def _dummy_executor(tc: ToolCall) -> str:
        return '{"events": []}'

    @pytest.mark.asyncio
    async def test_text_response_no_tools(self, sample_messages, tools):
        """LLM returns text directly without calling any tools."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)
        text_item = _mock_output_message("[SPEAKER: npc1] Hello")
        resp = _mock_responses_api(response_id="resp_1", output=[text_item])
        client._client.responses.create = AsyncMock(return_value=resp)

        result = await client.complete_with_tool_loop(
            sample_messages, tools, tool_executor=self._dummy_executor,
        )

        assert result.text == "[SPEAKER: npc1] Hello"
        assert not result.has_tool_calls
        assert client._last_response_id == "resp_1"
        assert client._client.responses.create.call_count == 1

    @pytest.mark.asyncio
    async def test_tool_call_then_text(self, sample_messages, tools):
        """LLM calls a tool, gets result, then produces text."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        tool_item = _mock_function_call(call_id="call_1", name="get_memories", arguments='{}')
        resp1 = _mock_responses_api(response_id="resp_1", output=[tool_item])
        text_item = _mock_output_message("[SPEAKER: npc1] Done")
        resp2 = _mock_responses_api(response_id="resp_2", output=[text_item])
        client._client.responses.create = AsyncMock(side_effect=[resp1, resp2])

        result = await client.complete_with_tool_loop(
            sample_messages, tools, tool_executor=self._dummy_executor,
        )

        assert result.text == "[SPEAKER: npc1] Done"
        assert client._last_response_id == "resp_2"
        assert client._client.responses.create.call_count == 2

    @pytest.mark.asyncio
    async def test_function_call_output_sent_natively(self, sample_messages, tools):
        """Tool results are sent as native function_call_output items."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        tool_item = _mock_function_call(call_id="call_abc", name="get_memories", arguments='{}')
        resp1 = _mock_responses_api(response_id="resp_1", output=[tool_item])
        text_item = _mock_output_message("ok")
        resp2 = _mock_responses_api(response_id="resp_2", output=[text_item])
        client._client.responses.create = AsyncMock(side_effect=[resp1, resp2])

        async def executor(tc: ToolCall) -> str:
            return '{"events": ["saw wolf"]}'

        await client.complete_with_tool_loop(
            sample_messages, tools, tool_executor=executor,
        )

        # Second call should have full input: messages + response.output + function_call_output
        second_kwargs = client._client.responses.create.call_args_list[1][1]
        assert "previous_response_id" not in second_kwargs
        second_input = second_kwargs["input"]
        # Original messages (2) + tool_item from response.output (1) + function_call_output (1)
        assert len(second_input) == 4
        # Last item is the function_call_output
        assert second_input[-1] == {
            "type": "function_call_output",
            "call_id": "call_abc",
            "output": '{"events": ["saw wolf"]}',
        }
        # response.output item is included before the function_call_output
        assert second_input[-2] is tool_item

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_all_outputs_sent(self, sample_messages, tools):
        """Multiple tool calls in one response produce multiple function_call_output items."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        tc1 = _mock_function_call(call_id="call_1", name="get_memories", arguments='{}')
        tc2 = _mock_function_call(call_id="call_2", name="background", arguments='{}')
        resp1 = _mock_responses_api(response_id="resp_1", output=[tc1, tc2])
        text_item = _mock_output_message("done")
        resp2 = _mock_responses_api(response_id="resp_2", output=[text_item])
        client._client.responses.create = AsyncMock(side_effect=[resp1, resp2])

        called_ids = []
        async def executor(tc: ToolCall) -> str:
            called_ids.append(tc.id)
            return f'result_{tc.id}'

        await client.complete_with_tool_loop(
            sample_messages, tools, tool_executor=executor,
        )

        assert called_ids == ["call_1", "call_2"]
        second_input = client._client.responses.create.call_args_list[1][1]["input"]
        # Original messages (2) + response.output items (2) + function_call_output items (2)
        assert len(second_input) == 6
        # Last two items are the function_call_output dicts
        assert second_input[-2]["call_id"] == "call_1"
        assert second_input[-1]["call_id"] == "call_2"

    @pytest.mark.asyncio
    async def test_max_iterations_returns_empty(self, sample_messages, tools):
        """Exhausting max iterations returns empty text."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        tool_item = _mock_function_call(call_id="call_1", name="t", arguments='{}')
        # Always return tool calls
        client._client.responses.create = AsyncMock(
            return_value=_mock_responses_api(response_id="resp_loop", output=[tool_item])
        )

        result = await client.complete_with_tool_loop(
            sample_messages, tools, tool_executor=self._dummy_executor,
            max_iterations=2,
        )

        assert result.text == ""
        assert client._client.responses.create.call_count == 2

    @pytest.mark.asyncio
    async def test_no_cross_event_threading(self, tools):
        """First call never uses cross-event previous_response_id.

        Memory tools provide cross-event context instead.  This prevents
        413 "tokens_limit_reached" from accumulated server-side history.
        """
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        # Simulate a previous event having set _last_response_id
        client._last_response_id = "resp_prev_event"

        text_item = _mock_output_message("reply")
        resp = _mock_responses_api(response_id="resp_new", output=[text_item])
        client._client.responses.create = AsyncMock(return_value=resp)

        await client.complete_with_tool_loop(
            [Message.system("sys"), Message.user("new_event")],
            tools, tool_executor=self._dummy_executor,
        )

        first_kwargs = client._client.responses.create.call_args_list[0][1]
        assert "previous_response_id" not in first_kwargs
        # _last_response_id is still updated for other callers (complete_with_tools)
        assert client._last_response_id == "resp_new"

    @pytest.mark.asyncio
    async def test_not_found_recovery_on_first_call(self, sample_messages, tools):
        """NotFoundError on first call recovers by clearing stale state."""
        client = OpenAIClient(api_key="test-key", timeout=10.0, max_retries=3)
        client._last_response_id = "resp_expired"

        not_found_err = openai.NotFoundError(
            message="Not found", response=MagicMock(status_code=404, headers={}), body=None,
        )
        text_item = _mock_output_message("recovered")
        ok_resp = _mock_responses_api(response_id="resp_fresh", output=[text_item])
        client._client.responses.create = AsyncMock(side_effect=[not_found_err, ok_resp])

        result = await client.complete_with_tool_loop(
            sample_messages, tools, tool_executor=self._dummy_executor,
        )

        assert result.text == "recovered"
        assert client._last_response_id == "resp_fresh"

    @pytest.mark.asyncio
    async def test_rate_limit_retry_in_loop(self, sample_messages, tools):
        """Rate limit on continuation call is retried."""
        client = OpenAIClient(api_key="test-key", timeout=10.0, max_retries=3)

        tool_item = _mock_function_call(call_id="call_1", name="t", arguments='{}')
        resp1 = _mock_responses_api(response_id="resp_1", output=[tool_item])
        rate_err = openai.RateLimitError(
            message="Rate limited", response=MagicMock(status_code=429, headers={}), body=None,
        )
        text_item = _mock_output_message("done")
        resp3 = _mock_responses_api(response_id="resp_2", output=[text_item])
        client._client.responses.create = AsyncMock(side_effect=[resp1, rate_err, resp3])

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.complete_with_tool_loop(
                sample_messages, tools, tool_executor=self._dummy_executor,
            )

        assert result.text == "done"
        assert client._client.responses.create.call_count == 3

    @pytest.mark.asyncio
    async def test_response_output_items_included_in_continuation(self, sample_messages, tools):
        """Model response.output items (function_call + reasoning) are passed back in input."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        tool_item = _mock_function_call(call_id="call_1", name="get_memories", arguments='{}')
        resp1 = _mock_responses_api(response_id="resp_1", output=[reasoning_item, tool_item])
        text_item = _mock_output_message("done")
        resp2 = _mock_responses_api(response_id="resp_2", output=[text_item])
        client._client.responses.create = AsyncMock(side_effect=[resp1, resp2])

        await client.complete_with_tool_loop(
            sample_messages, tools, tool_executor=self._dummy_executor,
        )

        second_input = client._client.responses.create.call_args_list[1][1]["input"]
        # messages (2) + reasoning_item (1) + tool_item (1) + function_call_output (1) = 5
        assert len(second_input) == 5
        # Reasoning item is carried through
        assert second_input[2] is reasoning_item
        # function_call item is carried through
        assert second_input[3] is tool_item
        # function_call_output is last
        assert second_input[4]["type"] == "function_call_output"

    @pytest.mark.asyncio
    async def test_empty_tool_output_guard(self, sample_messages, tools):
        """Empty tool executor returns are replaced with '(no data)'."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        tool_item = _mock_function_call(call_id="call_e", name="get_memories", arguments='{}')
        resp1 = _mock_responses_api(response_id="resp_1", output=[tool_item])
        text_item = _mock_output_message("ok")
        resp2 = _mock_responses_api(response_id="resp_2", output=[text_item])
        client._client.responses.create = AsyncMock(side_effect=[resp1, resp2])

        async def empty_executor(tc: ToolCall) -> str:
            return ""

        await client.complete_with_tool_loop(
            sample_messages, tools, tool_executor=empty_executor,
        )

        second_kwargs = client._client.responses.create.call_args_list[1][1]
        # Last item in full input list is the function_call_output
        assert second_kwargs["input"][-1]["output"] == "(no data)"

    @pytest.mark.asyncio
    async def test_reasoning_opts_passed_to_api(self, sample_messages, tools):
        """Reasoning options are forwarded to responses.create() on all calls."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        tool_item = _mock_function_call(call_id="call_r", name="get_memories", arguments='{}')
        resp1 = _mock_responses_api(response_id="resp_1", output=[tool_item])
        text_item = _mock_output_message("reasoning done")
        resp2 = _mock_responses_api(response_id="resp_2", output=[text_item])
        client._client.responses.create = AsyncMock(side_effect=[resp1, resp2])

        opts = LLMOptions(reasoning=ReasoningOptions(effort="low", summary="auto"))
        await client.complete_with_tool_loop(
            sample_messages, tools, tool_executor=self._dummy_executor, opts=opts,
        )

        # Both first and continuation calls should include reasoning
        first_kwargs = client._client.responses.create.call_args_list[0][1]
        assert first_kwargs["reasoning"] == {"effort": "low", "summary": "auto"}

        second_kwargs = client._client.responses.create.call_args_list[1][1]
        assert second_kwargs["reasoning"] == {"effort": "low", "summary": "auto"}

    @pytest.mark.asyncio
    async def test_no_reasoning_when_none(self, sample_messages, tools):
        """No reasoning key in kwargs when opts.reasoning is None."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)

        text_item = _mock_output_message("no reasoning")
        resp = _mock_responses_api(response_id="resp_1", output=[text_item])
        client._client.responses.create = AsyncMock(return_value=resp)

        await client.complete_with_tool_loop(
            sample_messages, tools, tool_executor=self._dummy_executor,
        )

        call_kwargs = client._client.responses.create.call_args[1]
        assert "reasoning" not in call_kwargs

    @pytest.mark.asyncio
    async def test_reasoning_in_complete_with_tools(self):
        """Reasoning options are forwarded by complete_with_tools() too."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)
        tools = [{"type": "function", "function": {"name": "t", "parameters": {}}}]
        msgs = [Message.system("sys"), Message.user("hi")]

        text_item = _mock_output_message("ok")
        resp = _mock_responses_api(response_id="resp_1", output=[text_item])
        client._client.responses.create = AsyncMock(return_value=resp)

        opts = LLMOptions(reasoning=ReasoningOptions(effort="high"))
        await client.complete_with_tools(msgs, tools, opts=opts)

        call_kwargs = client._client.responses.create.call_args[1]
        assert call_kwargs["reasoning"] == {"effort": "high"}


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
# 5.8  ConversationManager tool loop
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
        mock_llm_client.complete_with_tool_loop.return_value = LLMToolResponse(
            text="[SPEAKER: wolf] That's what you get!",
            tool_calls=[],
        )

        speaker_id, dialogue = await manager.handle_event(event_data, candidates, "Rostok, afternoon", traits)

        assert speaker_id == "wolf"
        assert "That's what you get!" in dialogue
        mock_llm_client.complete_with_tool_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_call_then_text(self, manager, mock_llm_client, event_data, candidates, traits):
        """LLM tool loop returns final text (loop handled inside client)."""
        mock_llm_client.complete_with_tool_loop.return_value = LLMToolResponse(
            text="[SPEAKER: wolf] I remember that bastard.",
            tool_calls=[],
        )

        speaker_id, dialogue = await manager.handle_event(event_data, candidates, "Rostok", traits)

        assert speaker_id == "wolf"
        assert "I remember that bastard." in dialogue
        mock_llm_client.complete_with_tool_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_single_response(self, manager, mock_llm_client, event_data, candidates, traits):
        """LLM tool loop handles multiple tools and returns final text."""
        mock_llm_client.complete_with_tool_loop.return_value = LLMToolResponse(
            text="[SPEAKER: wolf] Die!",
            tool_calls=[],
        )

        speaker_id, dialogue = await manager.handle_event(event_data, candidates, "W", traits)

        assert dialogue == "Die!"
        mock_llm_client.complete_with_tool_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_iterations_exhausted(self, manager, mock_llm_client, event_data, candidates, traits):
        """Tool loop hits max iterations → returns empty dialogue."""
        # complete_with_tool_loop returns empty text on exhaustion
        mock_llm_client.complete_with_tool_loop.return_value = LLMToolResponse(
            text="", tool_calls=[],
        )

        speaker_id, dialogue = await manager.handle_event(event_data, candidates, "W", traits)

        assert dialogue == ""
        mock_llm_client.complete_with_tool_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_executor_callback_passed(self, manager, mock_llm_client, event_data, candidates, traits):
        """Tool executor callback is passed to complete_with_tool_loop."""
        mock_llm_client.complete_with_tool_loop.return_value = LLMToolResponse(
            text="[SPEAKER: wolf] ok", tool_calls=[],
        )

        await manager.handle_event(event_data, candidates, "W", traits)

        # Verify tool_executor was passed as a keyword argument
        call_kwargs = mock_llm_client.complete_with_tool_loop.call_args
        assert "tool_executor" in call_kwargs.kwargs
        assert callable(call_kwargs.kwargs["tool_executor"])


# -----------------------------------------------------------------------
# 5.9  _handle_background() handler
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
        # Batch handler returns {char_id: data}
        assert "42" in result
        assert result["42"] == {"traits": ["brave"], "backstory": "A legend"}
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
        assert mutations[0]["op"] == "set"
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
        assert mutations[0]["op"] == "update"
        assert mutations[0]["ops"] == {"$set": {"connections": ["knows Sidorovich"]}}

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
# 5.10  Verify existing complete() tests still pass (backward compat)
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

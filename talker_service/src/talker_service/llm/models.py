"""Data models for LLM client."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Tool-calling models
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """A tool/function call returned by an LLM.

    Attributes:
        id: Unique identifier for this call (provider-assigned or synthetic).
        name: Tool/function name the LLM wants to invoke.
        arguments: Parsed argument dict (not a JSON string).
    """

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result of executing a tool call, ready to send back to the LLM.

    Attributes:
        tool_call_id: The ``ToolCall.id`` this result corresponds to.
        name: Tool/function name (echoed for clarity).
        content: JSON-serialized result string.
    """

    tool_call_id: str
    name: str
    content: str


@dataclass
class LLMToolResponse:
    """Structured response from ``complete_with_tools()``.

    Exactly one of ``text`` / ``tool_calls`` is populated:
    - If the LLM wants to call tools → ``tool_calls`` is non-empty, ``text`` is ``None``.
    - If the LLM produced a final answer → ``text`` is set, ``tool_calls`` is empty.
    """

    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.text is not None and self.tool_calls:
            # Spec: prioritise tool_calls when both are present.
            self.text = None

    @property
    def has_tool_calls(self) -> bool:
        """Return ``True`` when this response requests tool execution."""
        return len(self.tool_calls) > 0


# ---------------------------------------------------------------------------
# Message model
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A message in a conversation.

    Attributes:
        role: Message role (system, user, assistant, or tool).
        content: Message text content.
        tool_calls: Tool calls attached to an assistant message (OpenAI format).
        tool_call_id: Identifies which tool call this result answers (role="tool").
        name: Tool/function name (role="tool" messages).
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for API requests.

        Standard ``{role, content}`` for regular messages.  When tool-related
        fields are present the dict includes them in OpenAI wire format.
        """
        d: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }

        # Assistant message carrying tool calls
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]

        # Tool-result message
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name

        return d

    # -- Factory helpers -----------------------------------------------------

    @classmethod
    def system(cls, content: str) -> "Message":
        """Create a system message."""
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        """Create a user message."""
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        """Create an assistant message."""
        return cls(role="assistant", content=content)

    @classmethod
    def tool_result(cls, tool_call_id: str, name: str, content: str) -> "Message":
        """Create a tool-result message (role='tool').

        Args:
            tool_call_id: The ``ToolCall.id`` this result answers.
            name: Tool/function name.
            content: JSON-serialized result string.
        """
        return cls(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        )


@dataclass
class ReasoningOptions:
    """Reasoning configuration for models that support extended thinking.

    See https://platform.openai.com/docs/guides/reasoning

    Attributes:
        effort: How much reasoning effort the model should use.
            ``"low"`` → fastest / cheapest, ``"medium"`` → balanced,
            ``"high"`` → deepest reasoning.  ``None`` → provider default.
        summary: Whether to include a reasoning summary in the response.
            ``"auto"`` → include when useful, ``"concise"`` → short summary,
            ``"detailed"`` → full summary, ``None`` → omit.
    """

    effort: Literal["low", "medium", "high"] | None = None
    summary: Literal["auto", "concise", "detailed"] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the format expected by the OpenAI Responses API."""
        d: dict[str, Any] = {}
        if self.effort is not None:
            d["effort"] = self.effort
        if self.summary is not None:
            d["summary"] = self.summary
        return d

    def __bool__(self) -> bool:
        """Return ``True`` when at least one field is set."""
        return self.effort is not None or self.summary is not None


@dataclass
class LLMOptions:
    """Configuration options for LLM requests.
    
    Attributes:
        model: Model identifier to use (provider-specific)
        temperature: Sampling temperature (0.0 to 2.0)
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
        reasoning: Reasoning options for models that support extended thinking
    """
    model: str | None = None
    temperature: float | None = None #0.7 before
    max_tokens: int | None = None
    timeout: float | None = None
    reasoning: ReasoningOptions | None = None
    
    # Provider-specific options
    extra: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Response from an LLM completion request.
    
    Attributes:
        text: Generated text
        model: Model that generated the response
        usage: Token usage information
        finish_reason: Why generation stopped
    """
    text: str
    model: str | None = None
    usage: dict | None = None
    finish_reason: str | None = None

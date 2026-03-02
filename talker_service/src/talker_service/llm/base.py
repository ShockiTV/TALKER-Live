"""Base LLM client protocol and abstract interface."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from .models import LLMOptions, LLMToolResponse, Message, ToolCall


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM client implementations.
    
    All LLM providers must implement this interface.
    """
    
    async def complete(
        self,
        messages: list[Message],
        opts: LLMOptions | None = None,
    ) -> str:
        """Generate a completion from the LLM.
        
        Args:
            messages: List of conversation messages
            opts: Optional configuration for this request
            
        Returns:
            Generated text response
            
        Raises:
            TimeoutError: If request exceeds timeout
            LLMError: If API returns an error
        """
        ...

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        opts: LLMOptions | None = None,
    ) -> LLMToolResponse:
        """Generate a completion that may include tool/function calls.

        Args:
            messages: Conversation messages (may include tool-result messages).
            tools: Tool definitions in OpenAI-compatible format.
            opts: Optional configuration for this request.

        Returns:
            ``LLMToolResponse`` with either ``text`` or ``tool_calls`` populated.
        """
        ...


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients with common functionality."""
    
    def __init__(self, timeout: float = 60.0):
        """Initialize client.
        
        Args:
            timeout: Default request timeout in seconds
        """
        self.timeout = timeout
    
    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        opts: LLMOptions | None = None,
    ) -> str:
        """Generate a completion from the LLM."""
        pass

    @abstractmethod
    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        opts: LLMOptions | None = None,
    ) -> LLMToolResponse:
        """Generate a completion that may include tool/function calls."""
        pass
    
    def _get_timeout(self, opts: LLMOptions | None) -> float:
        """Get effective timeout from opts or default."""
        if opts and opts.timeout is not None:
            return opts.timeout
        return self.timeout

    # ------------------------------------------------------------------
    # Shared helpers for tool-calling response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_tool_calls(raw_tool_calls: list[dict[str, Any]]) -> list[ToolCall]:
        """Parse raw API tool-call objects into ``ToolCall`` list.

        Handles the standard OpenAI format::

            {"id": "call_abc", "type": "function",
             "function": {"name": "get_memories", "arguments": "{...}"}}

        If ``id`` is missing a synthetic one is generated.

        Args:
            raw_tool_calls: List of raw tool-call dicts from the API.

        Returns:
            Parsed ``ToolCall`` objects.
        """
        parsed: list[ToolCall] = []
        for raw in raw_tool_calls:
            call_id = raw.get("id") or f"call_{uuid4().hex[:8]}"
            func = raw.get("function", raw)
            name = func.get("name", "unknown")

            raw_args = func.get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError:
                    arguments = {}
            else:
                arguments = raw_args  # already a dict (e.g. Ollama)

            parsed.append(ToolCall(id=call_id, name=name, arguments=arguments))
        return parsed

    @staticmethod
    def _build_tool_response(data: dict[str, Any]) -> LLMToolResponse:
        """Build ``LLMToolResponse`` from a raw API response dict.

        Determines whether the response is a text completion or a tool-call
        request by inspecting the ``choices[0].message`` payload (OpenAI
        format) or ``message`` (Ollama format).

        Args:
            data: Parsed JSON response body from the provider.

        Returns:
            ``LLMToolResponse`` with either ``text`` or ``tool_calls`` set.
        """
        # OpenAI / OpenRouter style
        if "choices" in data:
            message = data["choices"][0]["message"]
        # Ollama style
        elif "message" in data:
            message = data["message"]
        else:
            # Fallback — treat entire data as the message
            message = data

        raw_calls = message.get("tool_calls") or []
        if raw_calls:
            return LLMToolResponse(
                text=None,
                tool_calls=BaseLLMClient._parse_tool_calls(raw_calls),
            )

        content = message.get("content") or ""
        return LLMToolResponse(text=content, tool_calls=[])


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class RateLimitError(LLMError):
    """Raised when API rate limit is hit."""
    pass


class AuthenticationError(LLMError):
    """Raised when API authentication fails."""
    pass


class ConnectionError(LLMError):
    """Raised when connection to API fails."""
    pass

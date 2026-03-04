"""OpenAI GPT client implementation.

Uses the official ``openai`` SDK:
- ``complete()`` → ``client.chat.completions.create()`` (Chat Completions API)
- ``complete_with_tools()`` → ``client.responses.create()`` (Responses API)
- ``complete_with_tool_loop()`` → native Responses API tool loop with
  ``previous_response_id`` threading and ``function_call_output`` items.

The Responses API manages conversation state server-side.  Within a tool
loop, only ``function_call_output`` items are sent — the server already
has the full conversation context from the previous response.
"""

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import openai
from loguru import logger

from .base import BaseLLMClient, LLMError, RateLimitError, AuthenticationError
from .models import LLMOptions, LLMToolResponse, Message, ToolCall


class OpenAIClient(BaseLLMClient):
    """OpenAI API client for GPT models.

    All HTTP communication goes through the ``openai.AsyncOpenAI`` SDK.
    """

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (falls back to file/env).
            model: Default model to use (falls back to DEFAULT_MODEL).
            endpoint: Custom API base URL (Azure Copilot, etc.).
            timeout: Request timeout in seconds.
            max_retries: Max retries on rate limit.
        """
        super().__init__(timeout=timeout)
        self.api_key = api_key or self._load_api_key()
        self.default_model = model or self.DEFAULT_MODEL
        self.max_retries = max_retries
        self._conversation: list[Message] = []
        self._last_response_id: str | None = None

        # Resolve base_url: explicit param > env var > SDK default
        resolved_endpoint = endpoint or os.environ.get("OPENAI_ENDPOINT", "") or None

        # Build SDK client kwargs
        client_kwargs: dict[str, Any] = {
            "api_key": self.api_key or "missing",
            "max_retries": 0,  # We handle retries ourselves
            "timeout": timeout,
        }
        if resolved_endpoint:
            client_kwargs["base_url"] = resolved_endpoint

        self._client = openai.AsyncOpenAI(**client_kwargs)

        # Expose resolved URL for tests / logging
        self.api_url = resolved_endpoint or "https://api.openai.com/v1"

        if not self.api_key:
            logger.warning("OpenAI API key not found - client will fail on requests")
        if resolved_endpoint:
            logger.info("OpenAI client using custom endpoint: {}", resolved_endpoint)

    def _load_api_key(self) -> str | None:
        """Load API key from file or environment."""
        # Try environment variable first
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key:
            logger.debug("Using OpenAI API key from environment")
            return env_key

        # Try file (relative to game directory)
        key_paths = [
            Path("openai_api_key.txt"),
            Path("./openai_api_key.txt"),
        ]

        for path in key_paths:
            if path.exists():
                key = path.read_text().strip()
                if key:
                    logger.debug(f"Using OpenAI API key from {path}")
                    return key

        return None

    # ------------------------------------------------------------------
    # Tool definition format conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert Chat Completions tool format to Responses API format.

        Chat Completions::

            {"type": "function",
             "function": {"name": "...", "description": "...", "parameters": {...}}}

        Responses API::

            {"type": "function",
             "name": "...", "description": "...", "parameters": {...}}
        """
        converted: list[dict[str, Any]] = []
        for tool in tools:
            if "function" in tool:
                func = tool["function"]
                converted.append({
                    "type": "function",
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                })
            else:
                # Already in Responses format or unknown — pass through
                converted.append(tool)
        return converted

    # ------------------------------------------------------------------
    # Responses API output parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_responses_output(output: list[Any]) -> LLMToolResponse:
        """Parse ``Response.output`` items into ``LLMToolResponse``.

        Handles ``ResponseFunctionToolCall`` and ``ResponseOutputMessage``.
        """
        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []

        for item in output:
            item_type = getattr(item, "type", None)

            if item_type == "function_call":
                # ResponseFunctionToolCall
                raw_args = getattr(item, "arguments", "{}")
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    arguments = {}
                tool_calls.append(ToolCall(
                    id=getattr(item, "call_id", "") or getattr(item, "id", ""),
                    name=getattr(item, "name", "unknown"),
                    arguments=arguments,
                ))

            elif item_type == "message":
                # ResponseOutputMessage — extract text from content list
                content_list = getattr(item, "content", [])
                for content_item in content_list:
                    ct = getattr(content_item, "type", None)
                    if ct == "output_text":
                        text_parts.append(getattr(content_item, "text", ""))

        if tool_calls:
            return LLMToolResponse(text=None, tool_calls=tool_calls)

        return LLMToolResponse(text="".join(text_parts) or "", tool_calls=[])

    # ------------------------------------------------------------------
    # complete() — Chat Completions SDK
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        opts: LLMOptions | None = None,
    ) -> str:
        """Generate completion using the Chat Completions API (SDK).

        Args:
            messages: Conversation messages.
            opts: Request options.

        Returns:
            Generated text.
        """
        if not self.api_key:
            raise AuthenticationError("OpenAI API key not configured")

        opts = opts or LLMOptions()

        kwargs: dict[str, Any] = {
            "model": opts.model or self.default_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": opts.temperature,
        }
        if opts.max_tokens:
            kwargs["max_tokens"] = opts.max_tokens

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await self._client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""

            except openai.RateLimitError as e:
                wait_time = 2 ** attempt
                logger.warning(
                    f"OpenAI rate limited, retry {attempt + 1}/{self.max_retries} after {wait_time}s"
                )
                await asyncio.sleep(wait_time)
                last_error = RateLimitError(f"Rate limited: {e}")
                continue

            except openai.AuthenticationError as e:
                raise AuthenticationError(f"Invalid API key: {e}") from e

            except openai.APITimeoutError as e:
                raise TimeoutError(
                    f"OpenAI request timed out after {self._get_timeout(opts)}s"
                ) from e

            except openai.APIError as e:
                raise LLMError(f"OpenAI API error: {e}") from e

        raise last_error or LLMError("Max retries exceeded")

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset_conversation(self) -> None:
        """Clear conversation history and server-side thread reference."""
        self._conversation.clear()
        self._last_response_id = None

    def get_conversation(self) -> list[Message]:
        """Return a copy of current conversation (for debugging/testing)."""
        return self._conversation.copy()

    # ------------------------------------------------------------------
    # Responses API — retry / recovery helper
    # ------------------------------------------------------------------

    async def _responses_create_with_retry(
        self,
        kwargs: dict[str, Any],
        all_messages: list[Message] | None = None,
    ) -> Any:
        """Call ``responses.create()`` with retry and state-recovery logic.

        Args:
            kwargs: Arguments for ``responses.create()``.
            all_messages: Full message list for rebuilding ``input`` on
                stale-state recovery (NotFoundError / BadRequestError).
                When ``None``, recovery is skipped and errors propagate.
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return await self._client.responses.create(**kwargs)

            except openai.NotFoundError:
                if all_messages is not None:
                    logger.warning(
                        "previous_response_id invalid, starting fresh"
                    )
                    self._last_response_id = None
                    kwargs.pop("previous_response_id", None)
                    kwargs["input"] = [m.to_dict() for m in all_messages]
                    continue
                raise LLMError(
                    "Response not found during tool loop continuation"
                )

            except openai.BadRequestError as e:
                if all_messages is not None and kwargs.get("previous_response_id"):
                    logger.warning(
                        "BadRequestError with active thread, "
                        "retrying fresh: {}", str(e)[:200]
                    )
                    self._last_response_id = None
                    kwargs.pop("previous_response_id", None)
                    kwargs["input"] = [m.to_dict() for m in all_messages]
                    continue
                raise LLMError(f"OpenAI API error: {e}") from e

            except openai.RateLimitError as e:
                wait_time = 2 ** attempt
                logger.warning(
                    "Rate limited, retry {}/{} after {}s",
                    attempt + 1, self.max_retries, wait_time,
                )
                await asyncio.sleep(wait_time)
                last_error = RateLimitError(f"Rate limited: {e}")
                continue

            except openai.AuthenticationError as e:
                raise AuthenticationError(f"Invalid API key: {e}") from e

            except openai.APITimeoutError as e:
                raise TimeoutError(
                    f"OpenAI request timed out after {self.timeout}s"
                ) from e

            except openai.APIError as e:
                raise LLMError(f"OpenAI API error: {e}") from e

        raise last_error or LLMError("Max retries exceeded")

    # ------------------------------------------------------------------
    # complete_with_tools() — single-turn Responses API
    # ------------------------------------------------------------------

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        opts: LLMOptions | None = None,
    ) -> LLMToolResponse:
        """Single-turn completion via Responses API.

        For multi-turn tool loops, prefer ``complete_with_tool_loop()``
        which uses native ``function_call_output`` items with
        ``previous_response_id`` threading.
        """
        if not self.api_key:
            raise AuthenticationError("OpenAI API key not configured")

        for msg in messages:
            if msg not in self._conversation:
                self._conversation.append(msg)

        opts = opts or LLMOptions()
        converted_tools = self._convert_tools(tools)

        kwargs: dict[str, Any] = {
            "model": opts.model or self.default_model,
            "input": [m.to_dict() for m in messages],
            "temperature": opts.temperature,
            "tools": converted_tools,
            "truncation": "auto",
        }
        if opts.max_tokens:
            kwargs["max_output_tokens"] = opts.max_tokens
        if self._last_response_id:
            kwargs["previous_response_id"] = self._last_response_id

        response = await self._responses_create_with_retry(kwargs, messages)

        self._last_response_id = response.id
        tool_response = self._parse_responses_output(response.output)

        self._conversation.append(Message(
            role="assistant",
            content=tool_response.text or "",
            tool_calls=tool_response.tool_calls if tool_response.has_tool_calls else None,
        ))
        return tool_response

    # ------------------------------------------------------------------
    # complete_with_tool_loop() — native Responses API tool loop
    # ------------------------------------------------------------------

    async def complete_with_tool_loop(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        tool_executor: Callable[[ToolCall], Awaitable[str]],
        opts: LLMOptions | None = None,
        max_iterations: int = 5,
    ) -> LLMToolResponse:
        """Run the full tool-calling loop using native Responses API threading.

        On each iteration the server keeps full conversation state via
        ``previous_response_id``.  Tool outputs are sent as native
        ``function_call_output`` items — no Chat-Completions-style message
        conversion needed.

        Args:
            messages: Initial conversation messages (system + user).
            tools: Tool definitions in OpenAI-compatible format.
            tool_executor: Async callback ``(ToolCall) -> str`` that runs
                a tool and returns the formatted result.
            opts: Optional LLM configuration.
            max_iterations: Maximum tool-call round-trips.

        Returns:
            ``LLMToolResponse`` with ``text`` populated (or empty on exhaustion).
        """
        if not self.api_key:
            raise AuthenticationError("OpenAI API key not configured")

        for msg in messages:
            if msg not in self._conversation:
                self._conversation.append(msg)

        opts = opts or LLMOptions()
        converted_tools = self._convert_tools(tools)
        model = opts.model or self.default_model
        temperature = opts.temperature
        max_output_tokens = opts.max_tokens

        # First call: send full messages, optionally thread cross-event
        kwargs: dict[str, Any] = {
            "model": model,
            "input": [m.to_dict() for m in messages],
            "temperature": temperature,
            "tools": converted_tools,
            "truncation": "auto",
        }
        if max_output_tokens:
            kwargs["max_output_tokens"] = max_output_tokens
        if self._last_response_id:
            kwargs["previous_response_id"] = self._last_response_id

        for iteration in range(max_iterations):
            # First iteration gets full recovery; continuations are simpler
            if iteration == 0:
                response = await self._responses_create_with_retry(
                    kwargs, messages
                )
            else:
                response = await self._responses_create_with_retry(kwargs)

            self._last_response_id = response.id
            tool_response = self._parse_responses_output(response.output)

            if not tool_response.has_tool_calls:
                self._conversation.append(Message(
                    role="assistant",
                    content=tool_response.text or "",
                ))
                return tool_response

            # Execute tools and build native function_call_output items
            outputs: list[dict[str, Any]] = []
            for tc in tool_response.tool_calls:
                result = await tool_executor(tc)
                outputs.append({
                    "type": "function_call_output",
                    "call_id": tc.id,
                    "output": result,
                })

            # Continue: server has full context, send only the outputs
            kwargs = {
                "model": model,
                "input": outputs,
                "previous_response_id": response.id,
                "tools": converted_tools,
                "truncation": "auto",
                "temperature": temperature,
            }
            if max_output_tokens:
                kwargs["max_output_tokens"] = max_output_tokens

        logger.error(f"Tool loop exhausted after {max_iterations} iterations")
        return LLMToolResponse(text="", tool_calls=[])

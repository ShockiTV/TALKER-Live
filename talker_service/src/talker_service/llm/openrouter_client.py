"""OpenRouter API client implementation."""

import asyncio
import os
from typing import Any

import httpx
from loguru import logger

from .base import BaseLLMClient, LLMError, RateLimitError, AuthenticationError
from .models import LLMOptions, LLMToolResponse, Message


class OpenRouterClient(BaseLLMClient):
    """OpenRouter API client for multiple LLM providers."""
    
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODEL = "openai/gpt-4o-mini"
    
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key
            model: Default model to use
            timeout: Request timeout in seconds
            max_retries: Max retries on rate limit
        """
        super().__init__(timeout=timeout)
        self.api_key = api_key or self._load_api_key()
        self.default_model = model or self.DEFAULT_MODEL
        self.max_retries = max_retries
        
        if not self.api_key:
            logger.warning("OpenRouter API key not found - client will fail on requests")
    
    def _load_api_key(self) -> str | None:
        """Load API key from environment."""
        return os.environ.get("OPENROUTER_API_KEY")
    
    async def complete(
        self,
        messages: list[Message],
        opts: LLMOptions | None = None,
    ) -> str:
        """Generate completion using OpenRouter API.
        
        Args:
            messages: Conversation messages
            opts: Request options
            
        Returns:
            Generated text
        """
        if not self.api_key:
            raise AuthenticationError("OpenRouter API key not configured")
        
        opts = opts or LLMOptions()
        timeout = self._get_timeout(opts)
        
        request_body = {
            "model": opts.model or self.default_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": opts.temperature,
        }
        
        if opts.max_tokens:
            request_body["max_tokens"] = opts.max_tokens
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/TALKER-Expanded",
            "X-Title": "TALKER Expanded",
        }
        
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self.API_URL,
                        json=request_body,
                        headers=headers,
                    )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                
                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"OpenRouter rate limited, retry {attempt + 1}/{self.max_retries} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                    last_error = RateLimitError(f"Rate limited: {response.text}")
                    continue
                
                elif response.status_code == 401:
                    raise AuthenticationError(f"Invalid API key: {response.text}")
                
                else:
                    raise LLMError(f"OpenRouter API error {response.status_code}: {response.text}")
                    
            except httpx.TimeoutException as e:
                raise TimeoutError(f"OpenRouter request timed out after {timeout}s") from e
            except httpx.RequestError as e:
                raise LLMError(f"OpenRouter request failed: {e}") from e
        
        raise last_error or LLMError("Max retries exceeded")

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        opts: LLMOptions | None = None,
    ) -> LLMToolResponse:
        """Generate completion with tool/function calling support.

        Uses the same OpenAI-compatible format as ``complete()``.
        """
        if not self.api_key:
            raise AuthenticationError("OpenRouter API key not configured")

        opts = opts or LLMOptions()
        timeout = self._get_timeout(opts)

        request_body: dict[str, Any] = {
            "model": opts.model or self.default_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": opts.temperature,
            "tools": tools,
        }

        if opts.max_tokens:
            request_body["max_tokens"] = opts.max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/TALKER-Expanded",
            "X-Title": "TALKER Expanded",
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self.API_URL,
                        json=request_body,
                        headers=headers,
                    )

                if response.status_code == 200:
                    data = response.json()
                    return self._build_tool_response(data)

                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"OpenRouter rate limited, retry {attempt + 1}/{self.max_retries} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                    last_error = RateLimitError(f"Rate limited: {response.text}")
                    continue

                elif response.status_code == 401:
                    raise AuthenticationError(f"Invalid API key: {response.text}")

                else:
                    raise LLMError(f"OpenRouter API error {response.status_code}: {response.text}")

            except httpx.TimeoutException as e:
                raise TimeoutError(f"OpenRouter request timed out after {timeout}s") from e
            except httpx.RequestError as e:
                raise LLMError(f"OpenRouter request failed: {e}") from e

        raise last_error or LLMError("Max retries exceeded")

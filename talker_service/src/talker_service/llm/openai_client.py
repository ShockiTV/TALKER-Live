"""OpenAI GPT client implementation."""

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from .base import BaseLLMClient, LLMError, RateLimitError, AuthenticationError
from .models import LLMOptions, LLMToolResponse, Message


class OpenAIClient(BaseLLMClient):
    """OpenAI API client for GPT models."""
    
    DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"
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
            api_key: OpenAI API key (falls back to file/env)
            model: Default model to use (falls back to DEFAULT_MODEL)
            endpoint: Custom API endpoint (falls back to OPENAI_ENDPOINT env, then default)
            timeout: Request timeout in seconds
            max_retries: Max retries on rate limit
        """
        super().__init__(timeout=timeout)
        self.api_key = api_key or self._load_api_key()
        self.default_model = model or self.DEFAULT_MODEL
        self.api_url = endpoint or os.environ.get("OPENAI_ENDPOINT", "") or self.DEFAULT_API_URL
        self.max_retries = max_retries
        
        if not self.api_key:
            logger.warning("OpenAI API key not found - client will fail on requests")
        if self.api_url != self.DEFAULT_API_URL:
            logger.info("OpenAI client using custom endpoint: {}", self.api_url)
    
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
    
    async def complete(
        self,
        messages: list[Message],
        opts: LLMOptions | None = None,
    ) -> str:
        """Generate completion using OpenAI API.
        
        Args:
            messages: Conversation messages
            opts: Request options
            
        Returns:
            Generated text
        """
        if not self.api_key:
            raise AuthenticationError("OpenAI API key not configured")
        
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
        }
        
        # Retry loop for rate limiting
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self.api_url,
                        json=request_body,
                        headers=headers,
                    )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"OpenAI rate limited, retry {attempt + 1}/{self.max_retries} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                    last_error = RateLimitError(f"Rate limited: {response.text}")
                    continue
                
                elif response.status_code == 401:
                    raise AuthenticationError(f"Invalid API key: {response.text}")
                
                else:
                    raise LLMError(f"OpenAI API error {response.status_code}: {response.text}")
                    
            except httpx.TimeoutException as e:
                raise TimeoutError(f"OpenAI request timed out after {timeout}s") from e
            except httpx.RequestError as e:
                raise LLMError(f"OpenAI request failed: {e}") from e
        
        # Exhausted retries
        raise last_error or LLMError("Max retries exceeded")

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        opts: LLMOptions | None = None,
    ) -> LLMToolResponse:
        """Generate completion with tool/function calling support.

        Adds ``tools`` to the request body and parses tool-call responses.
        Reuses the same retry logic as ``complete()``.
        """
        if not self.api_key:
            raise AuthenticationError("OpenAI API key not configured")

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
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self.api_url,
                        json=request_body,
                        headers=headers,
                    )

                if response.status_code == 200:
                    data = response.json()
                    return self._build_tool_response(data)

                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"OpenAI rate limited, retry {attempt + 1}/{self.max_retries} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                    last_error = RateLimitError(f"Rate limited: {response.text}")
                    continue

                elif response.status_code == 401:
                    raise AuthenticationError(f"Invalid API key: {response.text}")

                else:
                    raise LLMError(f"OpenAI API error {response.status_code}: {response.text}")

            except httpx.TimeoutException as e:
                raise TimeoutError(f"OpenAI request timed out after {timeout}s") from e
            except httpx.RequestError as e:
                raise LLMError(f"OpenAI request failed: {e}") from e

        raise last_error or LLMError("Max retries exceeded")

"""Proxy client for custom OpenAI-compatible endpoints."""

import os
from typing import Any

import httpx
from loguru import logger

from .base import BaseLLMClient, LLMError, AuthenticationError
from .models import LLMOptions, LLMToolResponse, Message


class ProxyClient(BaseLLMClient):
    """Proxy client for custom OpenAI-compatible API endpoints.
    
    Useful for:
    - Self-hosted LLM inference servers
    - Corporate proxies
    - Custom routing/load balancing
    """
    
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ):
        """Initialize proxy client.
        
        Args:
            endpoint: Proxy API endpoint URL
            api_key: Optional API key for proxy
            model: Default model to use
            timeout: Request timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.endpoint = endpoint or os.environ.get("TALKER_PROXY_ENDPOINT", "")
        self.api_key = api_key or os.environ.get("TALKER_PROXY_API_KEY", "")
        self.default_model = model or os.environ.get("TALKER_PROXY_MODEL", "default")
        
        if not self.endpoint:
            logger.warning("Proxy endpoint not configured - client will fail on requests")
    
    async def complete(
        self,
        messages: list[Message],
        opts: LLMOptions | None = None,
    ) -> str:
        """Generate completion using proxy endpoint.
        
        Args:
            messages: Conversation messages
            opts: Request options
            
        Returns:
            Generated text
        """
        if not self.endpoint:
            raise LLMError("Proxy endpoint not configured")
        
        opts = opts or LLMOptions()
        timeout = self._get_timeout(opts)
        
        # Use OpenAI-compatible request format
        request_body = {
            "model": opts.model or self.default_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": opts.temperature,
        }
        
        if opts.max_tokens:
            request_body["max_tokens"] = opts.max_tokens
        
        headers = {
            "Content-Type": "application/json",
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.endpoint,
                    json=request_body,
                    headers=headers,
                )
            
            if response.status_code == 200:
                data = response.json()
                # Support both OpenAI format and simple text response
                if "choices" in data:
                    return data["choices"][0]["message"]["content"]
                elif "text" in data:
                    return data["text"]
                elif "content" in data:
                    return data["content"]
                else:
                    raise LLMError(f"Unknown response format: {data}")
            
            elif response.status_code == 401:
                raise AuthenticationError(f"Proxy authentication failed: {response.text}")
            
            else:
                raise LLMError(f"Proxy API error {response.status_code}: {response.text}")
                
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Proxy request timed out after {timeout}s") from e
        except httpx.RequestError as e:
            raise LLMError(f"Proxy request failed: {e}") from e

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        opts: LLMOptions | None = None,
    ) -> LLMToolResponse:
        """Generate completion with tool/function calling support.

        Uses OpenAI-compatible format.  Falls back to text-only if the
        endpoint doesn't return ``tool_calls``.
        """
        if not self.endpoint:
            raise LLMError("Proxy endpoint not configured")

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

        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.endpoint,
                    json=request_body,
                    headers=headers,
                )

            if response.status_code == 200:
                data = response.json()
                return self._build_tool_response(data)

            elif response.status_code == 401:
                raise AuthenticationError(f"Proxy authentication failed: {response.text}")

            else:
                raise LLMError(f"Proxy API error {response.status_code}: {response.text}")

        except httpx.TimeoutException as e:
            raise TimeoutError(f"Proxy request timed out after {timeout}s") from e
        except httpx.RequestError as e:
            raise LLMError(f"Proxy request failed: {e}") from e

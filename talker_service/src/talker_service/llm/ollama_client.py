"""Ollama local LLM client implementation."""

import os

import httpx
from loguru import logger

from .base import BaseLLMClient, LLMError, ConnectionError as LLMConnectionError
from .models import Message, LLMOptions


class OllamaClient(BaseLLMClient):
    """Ollama client for local LLM inference."""
    
    DEFAULT_ENDPOINT = "http://localhost:11434"
    DEFAULT_MODEL = "llama3.2"
    
    def __init__(
        self,
        endpoint: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ):
        """Initialize Ollama client.
        
        Args:
            endpoint: Ollama API endpoint (default localhost:11434)
            model: Default model to use
            timeout: Request timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.endpoint = endpoint or os.environ.get("OLLAMA_ENDPOINT", self.DEFAULT_ENDPOINT)
        self.default_model = model or self.DEFAULT_MODEL
    
    async def complete(
        self,
        messages: list[Message],
        opts: LLMOptions | None = None,
    ) -> str:
        """Generate completion using Ollama API.
        
        Args:
            messages: Conversation messages
            opts: Request options
            
        Returns:
            Generated text
        """
        opts = opts or LLMOptions()
        timeout = self._get_timeout(opts)
        
        # Ollama uses /api/chat endpoint
        url = f"{self.endpoint}/api/chat"
        
        request_body = {
            "model": opts.model or self.default_model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,  # Get full response at once
            "options": {
                "temperature": opts.temperature,
            },
        }
        
        if opts.max_tokens:
            request_body["options"]["num_predict"] = opts.max_tokens
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=request_body)
            
            if response.status_code == 200:
                data = response.json()
                return data["message"]["content"]
            
            else:
                raise LLMError(f"Ollama API error {response.status_code}: {response.text}")
                
        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Failed to connect to Ollama at {self.endpoint}. "
                "Is Ollama running? Start with: ollama serve"
            ) from e
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Ollama request timed out after {timeout}s") from e
        except httpx.RequestError as e:
            raise LLMError(f"Ollama request failed: {e}") from e
    
    async def is_available(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.endpoint}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

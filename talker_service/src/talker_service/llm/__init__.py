"""LLM client module for TALKER Service.

Provides abstract LLM interface with provider-specific implementations:
- OpenAI (GPT models)
- OpenRouter (multiple providers)
- Ollama (local models)
- Proxy (custom endpoints)
"""

from .base import LLMClient
from .models import Message, LLMOptions
from .factory import get_llm_client

__all__ = [
    "LLMClient",
    "Message",
    "LLMOptions",
    "get_llm_client",
]

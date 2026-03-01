"""LLM client factory."""

from typing import TYPE_CHECKING

from loguru import logger

from .base import LLMClient

if TYPE_CHECKING:
    from .openai_client import OpenAIClient
    from .openrouter_client import OpenRouterClient
    from .ollama_client import OllamaClient
    from .proxy_client import ProxyClient


# Provider enum values (match Lua MCM modelmethod)
PROVIDER_OPENAI = 0
PROVIDER_OPENROUTER = 1
PROVIDER_OLLAMA = 2
PROVIDER_PROXY = 3

# String to int mapping for convenience
PROVIDER_NAMES = {
    "openai": PROVIDER_OPENAI,
    "openrouter": PROVIDER_OPENROUTER,
    "ollama": PROVIDER_OLLAMA,
    "proxy": PROVIDER_PROXY,
}

# Cache for client instances
_client_cache: dict[int, LLMClient] = {}


def get_llm_client(
    provider: int | str,
    timeout: float = 60.0,
    force_new: bool = False,
    **kwargs,
) -> LLMClient:
    """Get an LLM client for the specified provider.
    
    Args:
        provider: Provider ID (0=GPT, 1=OpenRouter, 2=Ollama, 3=Proxy)
                  or name ("openai", "openrouter", "ollama", "proxy")
        timeout: Default request timeout
        force_new: If True, create new instance even if cached
        **kwargs: Additional arguments for client constructor
        
    Returns:
        LLM client instance
        
    Raises:
        ValueError: If provider is unknown
    """
    # Convert string provider to int
    if isinstance(provider, str):
        provider_lower = provider.lower()
        if provider_lower not in PROVIDER_NAMES:
            raise ValueError(f"Unknown LLM provider: {provider}")
        provider = PROVIDER_NAMES[provider_lower]
    
    # Return cached client if available
    if not force_new and provider in _client_cache:
        return _client_cache[provider]
    
    # Create new client based on provider
    client: LLMClient
    
    if provider == PROVIDER_OPENAI:
        from .openai_client import OpenAIClient
        from ..config import settings as _settings
        endpoint = kwargs.pop("endpoint", None) or getattr(_settings, "openai_endpoint", "") or None
        client = OpenAIClient(endpoint=endpoint, timeout=timeout, **kwargs)
        logger.info("Created OpenAI client")
        
    elif provider == PROVIDER_OPENROUTER:
        from .openrouter_client import OpenRouterClient
        client = OpenRouterClient(timeout=timeout, **kwargs)
        logger.info("Created OpenRouter client")
        
    elif provider == PROVIDER_OLLAMA:
        from .ollama_client import OllamaClient
        client = OllamaClient(timeout=timeout, **kwargs)
        logger.info("Created Ollama client")
        
    elif provider == PROVIDER_PROXY:
        from .proxy_client import ProxyClient
        from ..config import settings
        # Get proxy settings from config or kwargs
        endpoint = kwargs.pop("endpoint", None) or settings.proxy_endpoint
        api_key = kwargs.pop("api_key", None) or settings.proxy_api_key
        model = kwargs.pop("model", None) or getattr(settings, "proxy_model", None)
        client = ProxyClient(endpoint=endpoint, api_key=api_key, model=model, timeout=timeout, **kwargs)
        logger.info(f"Created Proxy client with endpoint: {endpoint}, model: {model}")
        
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
    
    # Cache the client
    _client_cache[provider] = client
    return client


def clear_client_cache() -> None:
    """Clear the client cache (useful for testing or config changes)."""
    _client_cache.clear()
    logger.debug("Cleared LLM client cache")

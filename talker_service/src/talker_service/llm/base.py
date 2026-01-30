"""Base LLM client protocol and abstract interface."""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from .models import Message, LLMOptions


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
    
    def _get_timeout(self, opts: LLMOptions | None) -> float:
        """Get effective timeout from opts or default."""
        if opts and opts.timeout is not None:
            return opts.timeout
        return self.timeout


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

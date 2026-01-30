"""Data models for LLM client."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Message:
    """A message in a conversation.
    
    Attributes:
        role: Message role (system, user, or assistant)
        content: Message text content
    """
    role: Literal["system", "user", "assistant"]
    content: str
    
    def to_dict(self) -> dict[str, str]:
        """Convert to dict for API requests."""
        return {
            "role": self.role,
            "content": self.content,
        }
    
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


@dataclass
class LLMOptions:
    """Configuration options for LLM requests.
    
    Attributes:
        model: Model identifier to use (provider-specific)
        temperature: Sampling temperature (0.0 to 2.0)
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
    """
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    timeout: float | None = None
    
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

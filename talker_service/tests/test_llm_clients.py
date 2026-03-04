"""Unit tests for LLM clients."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import openai

from talker_service.llm.models import Message, LLMOptions
from talker_service.llm.openai_client import OpenAIClient
from talker_service.llm.openrouter_client import OpenRouterClient
from talker_service.llm.ollama_client import OllamaClient
from talker_service.llm.proxy_client import ProxyClient
from talker_service.llm.factory import get_llm_client, clear_client_cache, PROVIDER_OPENAI, PROVIDER_OPENROUTER, PROVIDER_OLLAMA, PROVIDER_PROXY
from talker_service.llm.base import LLMError, RateLimitError, AuthenticationError


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    return [
        Message.system("You are a helpful assistant."),
        Message.user("Hello!"),
    ]


@pytest.fixture
def mock_openai_response():
    """Mock successful OpenAI response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "Hello! How can I help you?"
                }
            }
        ]
    }


def _mock_chat_completion(content="Hello! How can I help you?"):
    """Build a mock ChatCompletion response object."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


class TestOpenAIClient:
    """Tests for OpenAI client (SDK-based)."""

    @pytest.mark.asyncio
    async def test_complete_success(self, sample_messages):
        """Test successful completion via SDK."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)
        mock_resp = _mock_chat_completion("Hello! How can I help you?")

        client._client.chat.completions.create = AsyncMock(return_value=mock_resp)
        result = await client.complete(sample_messages)

        assert result == "Hello! How can I help you?"
        client._client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_api_key_raises(self, sample_messages):
        """Test that missing API key raises error."""
        client = OpenAIClient(api_key=None, timeout=10.0)
        client.api_key = None

        with pytest.raises(AuthenticationError):
            await client.complete(sample_messages)

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, sample_messages):
        """Test rate limit triggers retry via SDK exception."""
        client = OpenAIClient(api_key="test-key", timeout=10.0, max_retries=2)
        mock_resp = _mock_chat_completion("Hello! How can I help you?")

        # First call raises RateLimitError, second succeeds
        mock_request = MagicMock()
        mock_request.url = "https://api.openai.com"
        rate_err = openai.RateLimitError(
            message="Rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        client._client.chat.completions.create = AsyncMock(
            side_effect=[rate_err, mock_resp]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.complete(sample_messages)

        assert result == "Hello! How can I help you?"
        assert client._client.chat.completions.create.call_count == 2

    def test_default_endpoint(self):
        """Client uses default URL when no endpoint given."""
        client = OpenAIClient(api_key="k", endpoint=None)
        assert client.api_url == "https://api.openai.com/v1"

    def test_custom_endpoint_param(self):
        """Explicit endpoint param is used."""
        url = "https://my-azure.openai.azure.com/v1"
        client = OpenAIClient(api_key="k", endpoint=url)
        assert client.api_url == url

    def test_endpoint_from_env(self):
        """Falls back to OPENAI_ENDPOINT env var when no param."""
        url = "https://env-endpoint.example.com/v1"
        with patch.dict("os.environ", {"OPENAI_ENDPOINT": url}):
            client = OpenAIClient(api_key="k", endpoint=None)
            assert client.api_url == url

    def test_param_beats_env(self):
        """Explicit endpoint param takes priority over env var."""
        with patch.dict("os.environ", {"OPENAI_ENDPOINT": "https://env.example.com"}):
            client = OpenAIClient(api_key="k", endpoint="https://param.example.com")
            assert client.api_url == "https://param.example.com"

    @pytest.mark.asyncio
    async def test_sdk_client_uses_custom_endpoint(self):
        """SDK client is initialized with custom base_url."""
        url = "https://custom.example.com/v1"
        client = OpenAIClient(api_key="test-key", endpoint=url, timeout=10.0)
        assert client._client.base_url == url or str(client._client.base_url).startswith(url)

    @pytest.mark.asyncio
    async def test_authentication_error(self, sample_messages):
        """Test that AuthenticationError from SDK maps correctly."""
        client = OpenAIClient(api_key="bad-key", timeout=10.0)
        auth_err = openai.AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )
        client._client.chat.completions.create = AsyncMock(side_effect=auth_err)

        with pytest.raises(AuthenticationError):
            await client.complete(sample_messages)

    @pytest.mark.asyncio
    async def test_timeout_error(self, sample_messages):
        """Test that APITimeoutError from SDK maps correctly."""
        client = OpenAIClient(api_key="test-key", timeout=10.0)
        timeout_err = openai.APITimeoutError(request=MagicMock())
        client._client.chat.completions.create = AsyncMock(side_effect=timeout_err)

        with pytest.raises(TimeoutError):
            await client.complete(sample_messages)


class TestOpenRouterClient:
    """Tests for OpenRouter client."""
    
    @pytest.mark.asyncio
    async def test_complete_success(self, sample_messages, mock_openai_response):
        """Test successful completion."""
        client = OpenRouterClient(api_key="test-key", timeout=10.0)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_openai_response
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await client.complete(sample_messages)
            
            assert result == "Hello! How can I help you?"
    
    @pytest.mark.asyncio
    async def test_custom_model(self, sample_messages, mock_openai_response):
        """Test using custom model."""
        client = OpenRouterClient(
            api_key="test-key",
            model="anthropic/claude-3-opus",
            timeout=10.0,
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_openai_response
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            await client.complete(sample_messages)
            
            # Check that custom model was used
            call_args = mock_post.call_args
            assert call_args[1]["json"]["model"] == "anthropic/claude-3-opus"


class TestOllamaClient:
    """Tests for Ollama client."""
    
    @pytest.mark.asyncio
    async def test_complete_success(self, sample_messages):
        """Test successful completion."""
        client = OllamaClient(timeout=10.0)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "content": "Hello from Ollama!"
            }
        }
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await client.complete(sample_messages)
            
            assert result == "Hello from Ollama!"
    
    @pytest.mark.asyncio
    async def test_connection_error(self, sample_messages):
        """Test connection error when Ollama not running."""
        client = OllamaClient(timeout=10.0)
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            
            with pytest.raises(Exception) as exc_info:
                await client.complete(sample_messages)
            
            assert "Failed to connect to Ollama" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_is_available(self):
        """Test availability check."""
        client = OllamaClient(timeout=5.0)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await client.is_available()
            
            assert result is True


class TestProxyClient:
    """Tests for Proxy client."""
    
    @pytest.mark.asyncio
    async def test_complete_openai_format(self, sample_messages, mock_openai_response):
        """Test completion with OpenAI response format."""
        client = ProxyClient(
            endpoint="http://proxy.example.com/v1/chat/completions",
            timeout=10.0,
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_openai_response
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await client.complete(sample_messages)
            
            assert result == "Hello! How can I help you?"
    
    @pytest.mark.asyncio
    async def test_complete_simple_format(self, sample_messages):
        """Test completion with simple text response format."""
        client = ProxyClient(
            endpoint="http://proxy.example.com/complete",
            timeout=10.0,
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "Simple response"}
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await client.complete(sample_messages)
            
            assert result == "Simple response"
    
    @pytest.mark.asyncio
    async def test_no_endpoint_raises(self, sample_messages):
        """Test that missing endpoint raises error."""
        client = ProxyClient(endpoint=None, timeout=10.0)
        client.endpoint = ""
        
        with pytest.raises(LLMError):
            await client.complete(sample_messages)


class TestFactory:
    """Tests for client factory."""
    
    def setup_method(self):
        """Clear cache before each test."""
        clear_client_cache()
    
    def test_get_openai_client(self):
        """Test creating OpenAI client."""
        client = get_llm_client(PROVIDER_OPENAI)
        assert isinstance(client, OpenAIClient)
    
    def test_get_openrouter_client(self):
        """Test creating OpenRouter client."""
        client = get_llm_client(PROVIDER_OPENROUTER)
        assert isinstance(client, OpenRouterClient)
    
    def test_get_ollama_client(self):
        """Test creating Ollama client."""
        client = get_llm_client(PROVIDER_OLLAMA)
        assert isinstance(client, OllamaClient)
    
    def test_get_proxy_client(self):
        """Test creating Proxy client."""
        client = get_llm_client(PROVIDER_PROXY)
        assert isinstance(client, ProxyClient)

    def test_get_proxy_client_with_model_override(self):
        """Test creating Proxy client with model override in kwargs."""
        client = get_llm_client(PROVIDER_PROXY, model="test-super-model")
        assert client.default_model == "test-super-model"
    
    def test_client_caching(self):
        """Test that clients are cached."""
        client1 = get_llm_client(PROVIDER_OPENAI)
        client2 = get_llm_client(PROVIDER_OPENAI)
        assert client1 is client2
    
    def test_force_new_client(self):
        """Test force_new bypasses cache."""
        client1 = get_llm_client(PROVIDER_OPENAI)
        client2 = get_llm_client(PROVIDER_OPENAI, force_new=True)
        assert client1 is not client2
    
    def test_unknown_provider_raises(self):
        """Test that unknown provider raises error."""
        with pytest.raises(ValueError):
            get_llm_client(999)


class TestMessage:
    """Tests for Message model."""
    
    def test_system_message(self):
        """Test creating system message."""
        msg = Message.system("System prompt")
        assert msg.role == "system"
        assert msg.content == "System prompt"
    
    def test_user_message(self):
        """Test creating user message."""
        msg = Message.user("Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
    
    def test_to_dict(self):
        """Test converting to dict."""
        msg = Message.user("Hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "Hello"}


class TestLLMOptions:
    """Tests for LLMOptions model."""
    
    def test_defaults(self):
        """Test default values."""
        opts = LLMOptions()
        assert opts.temperature == 0.7
        assert opts.model is None
        assert opts.max_tokens is None
        assert opts.timeout is None
    
    def test_custom_values(self):
        """Test custom values."""
        opts = LLMOptions(
            model="gpt-4",
            temperature=0.5,
            max_tokens=1000,
            timeout=30.0,
        )
        assert opts.model == "gpt-4"
        assert opts.temperature == 0.5
        assert opts.max_tokens == 1000
        assert opts.timeout == 30.0

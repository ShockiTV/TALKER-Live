"""Tests for ZMQ router message parsing."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.transport.router import ZMQRouter


class TestZMQRouter:
    """Tests for ZMQRouter class."""

    def test_router_initialization(self):
        """Test router initializes with correct endpoints."""
        sub_endpoint = "tcp://127.0.0.1:5555"
        router = ZMQRouter(sub_endpoint)
        
        assert router.sub_endpoint == sub_endpoint
        assert router.pub_endpoint is None
        assert router.handlers == {}
        assert router.running is False
        assert router.is_connected is False
    
    def test_router_initialization_with_pub(self):
        """Test router initializes with both SUB and PUB endpoints."""
        sub_endpoint = "tcp://127.0.0.1:5555"
        pub_endpoint = "tcp://*:5556"
        router = ZMQRouter(sub_endpoint, pub_endpoint)
        
        assert router.sub_endpoint == sub_endpoint
        assert router.pub_endpoint == pub_endpoint
        assert router.pub_socket is not None

    def test_handler_registration(self):
        """Test registering handlers for topics."""
        router = ZMQRouter("tcp://127.0.0.1:5555")
        
        async def dummy_handler(payload):
            pass
        
        router.on("game.event", dummy_handler)
        
        assert "game.event" in router.handlers
        assert router.handlers["game.event"] == dummy_handler

    def test_multiple_handler_registration(self):
        """Test registering multiple handlers for different topics."""
        router = ZMQRouter("tcp://127.0.0.1:5555")
        
        async def event_handler(payload):
            pass
        
        async def config_handler(payload):
            pass
        
        router.on("game.event", event_handler)
        router.on("config.sync", config_handler)
        
        assert len(router.handlers) == 2
        assert router.handlers["game.event"] == event_handler
        assert router.handlers["config.sync"] == config_handler


class TestMessageParsing:
    """Tests for message parsing functionality."""

    @pytest.mark.asyncio
    async def test_process_valid_message(self, sample_game_event_payload):
        """Test processing a valid message with topic and JSON payload."""
        router = ZMQRouter("tcp://127.0.0.1:5555")
        
        received_payload = None
        
        async def capture_handler(payload):
            nonlocal received_payload
            received_payload = payload
        
        router.on("game.event", capture_handler)
        
        # Simulate raw message format: "<topic> <json>"
        raw_message = f"game.event {json.dumps(sample_game_event_payload)}"
        
        await router._process_message(raw_message)
        
        assert received_payload is not None
        assert "event" in received_payload
        assert received_payload["event"]["type"] == "DEATH"

    @pytest.mark.asyncio
    async def test_process_message_no_handler(self, caplog):
        """Test processing message with no registered handler."""
        router = ZMQRouter("tcp://127.0.0.1:5555")
        
        raw_message = 'unknown.topic {"data": "test"}'
        
        # Should not raise, just log warning
        await router._process_message(raw_message)

    @pytest.mark.asyncio
    async def test_process_malformed_message_no_space(self, caplog):
        """Test processing malformed message without space separator."""
        router = ZMQRouter("tcp://127.0.0.1:5555")
        
        raw_message = "malformed_message_no_space"
        
        # Should not raise, just log warning
        await router._process_message(raw_message)

    @pytest.mark.asyncio
    async def test_process_message_invalid_json(self, caplog):
        """Test processing message with invalid JSON payload."""
        router = ZMQRouter("tcp://127.0.0.1:5555")
        
        handler_called = False
        
        async def dummy_handler(payload):
            nonlocal handler_called
            handler_called = True
        
        router.on("game.event", dummy_handler)
        
        raw_message = "game.event {invalid json}"
        
        # Should not raise, just log error
        await router._process_message(raw_message)
        
        # Handler should not be called for invalid JSON
        assert handler_called is False

    @pytest.mark.asyncio
    async def test_process_nested_payload(self):
        """Test that nested 'payload' key is extracted correctly."""
        router = ZMQRouter("tcp://127.0.0.1:5555")
        
        received_payload = None
        
        async def capture_handler(payload):
            nonlocal received_payload
            received_payload = payload
        
        router.on("test.topic", capture_handler)
        
        # Message with nested payload structure
        message_data = {
            "payload": {
                "inner_key": "inner_value"
            }
        }
        raw_message = f"test.topic {json.dumps(message_data)}"
        
        await router._process_message(raw_message)
        
        # Should extract the inner payload
        assert received_payload == {"inner_key": "inner_value"}

    @pytest.mark.asyncio
    async def test_process_direct_payload(self):
        """Test that direct payload (no 'payload' wrapper) works."""
        router = ZMQRouter("tcp://127.0.0.1:5555")
        
        received_payload = None
        
        async def capture_handler(payload):
            nonlocal received_payload
            received_payload = payload
        
        router.on("test.topic", capture_handler)
        
        # Message without nested payload structure
        message_data = {"direct_key": "direct_value"}
        raw_message = f"test.topic {json.dumps(message_data)}"
        
        await router._process_message(raw_message)
        
        assert received_payload == {"direct_key": "direct_value"}


class TestRouterLifecycle:
    """Tests for router lifecycle management."""

    @pytest.mark.asyncio
    async def test_shutdown_sets_flags(self):
        """Test that shutdown sets appropriate flags."""
        router = ZMQRouter("tcp://127.0.0.1:5555")
        router.running = True
        router.is_connected = True
        
        # Mock the socket and context to avoid actual ZMQ operations
        router.sub_socket = MagicMock()
        router.context = MagicMock()
        
        await router.shutdown()
        
        assert router.running is False
        assert router.is_connected is False
    
    @pytest.mark.asyncio
    async def test_shutdown_with_pub_socket(self):
        """Test that shutdown closes both sockets."""
        router = ZMQRouter("tcp://127.0.0.1:5555", "tcp://*:5556")
        router.running = True
        router.is_connected = True
        
        # Mock sockets
        router.sub_socket = MagicMock()
        router.pub_socket = MagicMock()
        router.context = MagicMock()
        
        await router.shutdown()
        
        assert router.running is False
        router.sub_socket.close.assert_called_once()
        router.pub_socket.close.assert_called_once()


class TestPublishFunctionality:
    """Tests for PUB socket functionality."""
    
    @pytest.mark.asyncio
    async def test_publish_without_pub_socket(self):
        """Test publish fails gracefully without PUB socket."""
        router = ZMQRouter("tcp://127.0.0.1:5555")  # No pub_endpoint
        
        result = await router.publish("test.topic", {"data": "test"})
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_when_not_connected(self):
        """Test publish fails gracefully when not connected."""
        router = ZMQRouter("tcp://127.0.0.1:5555", "tcp://*:5556")
        router.is_connected = False
        
        result = await router.publish("test.topic", {"data": "test"})
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_success(self):
        """Test successful publish."""
        router = ZMQRouter("tcp://127.0.0.1:5555", "tcp://*:5556")
        router.is_connected = True
        
        # Mock the pub socket
        mock_pub = AsyncMock()
        router.pub_socket = mock_pub
        
        result = await router.publish("test.topic", {"key": "value"})
        
        assert result is True
        mock_pub.send_string.assert_called_once()
        call_arg = mock_pub.send_string.call_args[0][0]
        assert call_arg.startswith("test.topic ")
        assert '"key": "value"' in call_arg


class TestRequestResponsePattern:
    """Tests for request/response pattern with request_id correlation."""
    
    @pytest.fixture
    def mock_router(self):
        """Create a router with mocked ZMQ sockets."""
        with patch('talker_service.transport.router.zmq.asyncio.Context') as mock_ctx_class:
            mock_ctx = MagicMock()
            mock_socket = MagicMock()
            mock_ctx.socket.return_value = mock_socket
            mock_ctx_class.return_value = mock_ctx
            
            router = ZMQRouter("tcp://127.0.0.1:5555")
            yield router
    
    @pytest.mark.asyncio
    async def test_create_request(self, mock_router):
        """Test creating a pending request."""
        import asyncio
        router = mock_router
        
        future = router.create_request("req-123", timeout=0.1)  # Very short timeout for test
        
        assert "req-123" in router._pending_requests
        assert isinstance(future, asyncio.Future)
        
        # Wait for timeout to clean up
        await asyncio.sleep(0.15)
    
    @pytest.mark.asyncio
    async def test_handle_state_response_success(self, mock_router):
        """Test state response resolves pending future."""
        router = mock_router
        
        future = router.create_request("req-456", timeout=5.0)
        
        # Simulate receiving response
        response_payload = {
            "request_id": "req-456",
            "response_type": "memories.get",
            "data": {"narrative": "test narrative"}
        }
        
        await router._handle_state_response(response_payload)
        
        # Future should be resolved
        assert future.done()
        result = await future
        assert result["data"]["narrative"] == "test narrative"
    
    @pytest.mark.asyncio
    async def test_handle_state_response_error(self, mock_router):
        """Test state response with error raises exception."""
        router = mock_router
        
        future = router.create_request("req-789", timeout=5.0)
        
        # Simulate receiving error response
        error_payload = {
            "request_id": "req-789",
            "response_type": "memories.get",
            "error": "Character not found"
        }
        
        await router._handle_state_response(error_payload)
        
        # Future should have exception
        assert future.done()
        with pytest.raises(Exception, match="Character not found"):
            await future
    
    @pytest.mark.asyncio
    async def test_handle_state_response_no_request_id(self, mock_router):
        """Test state response without request_id is handled gracefully."""
        router = mock_router
        
        # Should not raise
        await router._handle_state_response({"data": "orphan"})
    
    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_requests(self, mock_router):
        """Test that shutdown cancels pending request futures."""
        router = mock_router
        router.running = True
        router.is_connected = True
        
        future = router.create_request("req-cancel", timeout=0.1)  # Very short timeout
        
        await router.shutdown()
        
        assert future.cancelled() or future.done()
        assert len(router._pending_requests) == 0

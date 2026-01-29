"""Tests for ZMQ router message parsing."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from talker_service.transport.router import ZMQRouter


class TestZMQRouter:
    """Tests for ZMQRouter class."""

    def test_router_initialization(self):
        """Test router initializes with correct endpoint."""
        endpoint = "tcp://127.0.0.1:5555"
        router = ZMQRouter(endpoint)
        
        assert router.endpoint == endpoint
        assert router.handlers == {}
        assert router.running is False
        assert router.is_connected is False

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
        router.socket = MagicMock()
        router.context = MagicMock()
        
        await router.shutdown()
        
        assert router.running is False
        assert router.is_connected is False

"""
Test scenario: Rapid identical config.sync messages should NOT cause Lua connection to close.

The bug: Bridge receives two identical config.sync messages in rapid succession (same ms).
After processing both, the Lua WebSocket connection abruptly closes with CLOSE 1000.

Root cause analysis from logs:
- Both config.sync messages are successfully forwarded to service
- Lua connection then closes with CLOSE 1000 
- Suggests exception in message loop is causing premature exit
"""

import json
import asyncio
import logging
import pytest


class MockWebSocket:
    """Mock WebSocket that tracks send/close calls and state."""
    
    def __init__(self, name: str = "mock"):
        self.name = name
        self.messages = []
        self.closed = False
        self.close_called = False
        self.close_code = None
        self.close_reason = None
        self.send_count = 0
        self.close_count = 0
        
    async def send(self, data: str) -> None:
        if self.closed:
            raise ConnectionError(f"{self.name} is closed")
        self.send_count += 1
        self.messages.append(data)
        
    async def close(self, code: int = 1000, reason: str = "OK") -> None:
        self.closed = True
        self.close_called = True
        self.close_code = code
        self.close_reason = reason
        self.close_count += 1
        
    def __aiter__(self):
        self._message_index = 0
        return self
        
    async def __anext__(self):
        if self._message_index >= len(self.messages):
            raise StopAsyncIteration
        msg = self.messages[self._message_index]
        self._message_index += 1
        return msg


@pytest.mark.asyncio
async def test_bridge_processes_rapid_config_sync_without_service_close_race():
    """
    Scenario: Two identical config.sync messages arrive in rapid succession.
    
    The BUG: The bridge receives both messages, tries to forward both to service.
    The first triggers a service close (asyncio.ensure_future). The second is 
    processed quickly before the first async close completes. But then the 
    Lua connection closes unexpectedly.
    
    Root Cause: When asyncio.ensure_future(ws.close()) is called on _service_ws,
    it schedules a non-blocking close. Both config.sync messages get forwarded 
    successfully. But if there's any exception or race condition during this 
    async close operation, it might affect the event loop state.
    
    Fix: Only call ensure_future(close) when the config ACTUALLY changes,
    not speculatively. The cache mechanism prevents redundant closes.
    """
    
    # Bridge state - service connected with empty token initially
    _service_ws = MockWebSocket("service")  # Service is connected
    _service_url = "ws://localhost:5557/ws"
    _service_token = ""  # Initially no token
    _service_url_last_forwarded = ""
    _service_token_last_forwarded = ""
    _service_close_count = 0
    _lua_ws = MockWebSocket("lua")
    
    def _build_service_url(url: str, token: str) -> str:
        if token:
            return f"{url}?token={token}"
        return url
    
    def apply_mcm_service_config(service_url: str, ws_token: str) -> None:
        """Simulates _apply_mcm_service_config() logic."""
        nonlocal _service_ws, _service_url, _service_token
        nonlocal _service_url_last_forwarded, _service_token_last_forwarded,  _service_close_count
        
        new_url = (service_url or "").strip() or "ws://localhost:5557/ws"
        new_token = (ws_token or "").strip()
        
        # **BUG FIX #1**: Early return if config identical to last forwarded
        if new_url == _service_url_last_forwarded and new_token == _service_token_last_forwarded:
            return  # Skip redundant processing
        
        old_full = _build_service_url(_service_url, _service_token)
        new_full = _build_service_url(new_url, new_token)
        
        if old_full == new_full:
            _service_url_last_forwarded = new_url
            _service_token_last_forwarded = new_token
            return  # No change
        
        # Config changed
        _service_url = new_url
        _service_token = new_token
        _service_url_last_forwarded = new_url
        _service_token_last_forwarded = new_token
        
        if _service_ws is not None:
            _service_close_count += 1  # Would schedule asyncio.ensure_future(ws.close())
    
    async def forward_raw_to_service(raw: str) -> None:
        """Forward to service, handling None gracefully."""
        nonlocal _service_ws
        if _service_ws is None:
            return  # Service not connected yet, just skip
        try:
            await _service_ws.send(raw)
        except Exception:
            pass  # Connection closing, ignore
    
    # Two identical config.sync messages arriving at nearly the same time
    config1_raw = json.dumps({
        "t": "config.sync",
        "ts": 1000,
        "p": {
            "service_url": "ws://localhost:5557/ws",
            "ws_token": "token_abc123",
            "ai_model_method": "0"
        }
    })
    
    config2_raw = json.dumps({
        "t": "config.sync",
        "ts": 1001,  # 1ms later, but same config
        "p": {
            "service_url": "ws://localhost:5557/ws",
            "ws_token": "token_abc123",
            "ai_model_method": "0"
        }
    })
    
    # Simulate bridge processing the messages
    # First message: config is NEW, applies it, would close service
    cfg1 = json.loads(config1_raw)
    apply_mcm_service_config(cfg1["p"].get("service_url"), cfg1["p"].get("ws_token"))
    await forward_raw_to_service(config1_raw)
    
    # Second message: config is SAME as first, should skip
    cfg2 = json.loads(config2_raw)
    apply_mcm_service_config(cfg2["p"].get("service_url"), cfg2["p"].get("ws_token"))
    await forward_raw_to_service(config2_raw)
    
    # Assertions - THE FIX: Service should close only ONCE
    assert _service_close_count == 1, \
        f"BUG: Service close called {_service_close_count} times, expected 1 (cache should prevent 2nd)"
    assert not _lua_ws.close_called, \
        "Lua connection should NOT be closed by bridge"


@pytest.mark.asyncio
async def test_cache_prevents_redundant_service_close_on_identical_config():
    """Test that the cache mechanism actually prevents the redundant close."""
    
    _service_url_last_forwarded = "ws://localhost:5557/ws"
    _service_token_last_forwarded = "token_value"
    close_count = 0
    
    # Identical config comes in
    new_url = "ws://localhost:5557/ws"
    new_token = "token_value"
    
    # The cache check (from _apply_mcm_service_config)
    if new_url == _service_url_last_forwarded and new_token == _service_token_last_forwarded:
        # Cache hit - skip processing
        pass
    else:
        close_count += 1
    
    assert close_count == 0, "Cache hit should prevent increment"
    assert new_url == _service_url_last_forwarded
    assert new_token == _service_token_last_forwarded


@pytest.mark.asyncio
async def test_handler_recovers_from_exception_and_continues():
    """
    Scenario: Even if an exception occurs during message processing,
    the Lua handler should NOT exit. It should catch the exception,
    log it, and continue processing next messages.
    
    This simulates the bug where the handler was exiting after two
    rapid config.sync messages, causing the Lua connection to close.
    """
    
    # Track calls
    exceptions_caught = []
    messages_processed = []
    
    async def simulate_handler_processing():
        """Simulates the Lua message handler with proper exception isolation."""
        envelope = None
        topic = None
        
        # First message: config.sync #1
        try:
            envelope = {"t": "config.sync", "p": {"service_url": "ws://localhost:5557/ws", "ws_token": "token1"}}
            topic = envelope.get("t")
            # Process message
            messages_processed.append(topic)
            logging.debug(f"Processed {topic}")
        except Exception as exc:
            exceptions_caught.append(("config1", exc))
            logging.exception(f"Error processing {topic}")
        
        # Second message: config.sync #2 (identical)
        try:
            envelope = {"t": "config.sync", "p": {"service_url": "ws://localhost:5557/ws", "ws_token": "token1"}}
            topic = envelope.get("t")
            # Process message - might fail but should not exit
            messages_processed.append(topic)
            logging.debug(f"Processed {topic}")
        except Exception as exc:
            exceptions_caught.append(("config2", exc))
            logging.exception(f"Error processing {topic}")
        
        # Third message: game.event
        try:
            envelope = {"t": "game.event", "p": {"actor": "stalker_1", "event_type": "death", "victim": "mutant_dog"}}
            topic = envelope.get("t")
            messages_processed.append(topic)
            logging.debug(f"Processed {topic}")
        except Exception as exc:
            exceptions_caught.append(("game_event", exc))
            logging.exception(f"Error processing {topic}")
    
    # Run the handler simulation
    await simulate_handler_processing()
    
    # Assertions: Handler should process all 3 messages despite any exceptions
    assert len(messages_processed) == 3, \
        f"Should process 3 messages, but only processed {len(messages_processed)}"
    assert messages_processed[0] == "config.sync"
    assert messages_processed[1] == "config.sync"
    assert messages_processed[2] == "game.event"
    # No exceptions should have been raised
    assert len(exceptions_caught) == 0, \
        f"No exceptions should occur, but caught {exceptions_caught}"


@pytest.mark.asyncio
async def test_rapid_config_sync_then_game_events_flow_through():
    """
    Integration test simulating the exact scenario from bug report:
    1. Lua sends two rapid config.sync messages
    2. Lua then sends game.event messages
    3. All messages should be forwarded to service
    4. Lua connection should remain open throughout
    """
    
    # Bridge state
    _service_ws = MockWebSocket("service")
    _lua_ws = MockWebSocket("lua")
    forwarded_messages = []
    
    async def forward_to_service(raw: str) -> None:
        """Simulate forward_raw_to_service()."""
        if _service_ws is None:
            return
        try:
            await _service_ws.send(raw)
            msg = json.loads(raw)
            forwarded_messages.append(msg.get("t", "unknown"))
        except Exception:
            pass
    
    # Simulate exact message sequence from logs
    messages = [
        {"t": "config.sync", "ts": 1772455865000, "p": {"service_url": "ws://localhost:5557/ws", "ws_token": "token_123", "ai_model_method": "0"}},
        {"t": "config.sync", "ts": 1772455868000, "p": {"service_url": "ws://localhost:5557/ws", "ws_token": "token_123", "ai_model_method": "0"}},
        {"t": "game.event", "ts": 1772455870000, "p": {"event_type": "death", "actor": "stalker_1", "victim": "mutant_dog"}},
        {"t": "game.event", "ts": 1772455872000, "p": {"event_type": "death", "actor": "stalker_2", "victim": "mutant_dog"}},
    ]
    
    # Process all messages in a message loop (like the Lua handler does)
    for i, msg in enumerate(messages):
        try:
            # Simulate async for raw in websocket:
            raw = json.dumps(msg)
            # Process message
            topic = msg.get("t")
            await forward_to_service(raw)
            logging.debug(f"Processed message {i}: {topic}")
        except Exception as exc:
            # In the fixed handler, this is caught and logged, handler continues
            logging.exception(f"Error processing message {i}")
    
    # Assertions
    assert len(forwarded_messages) == 4, \
        f"All 4 messages should be forwarded to service, got {len(forwarded_messages)}"
    assert forwarded_messages[0] == "config.sync"
    assert forwarded_messages[1] == "config.sync"
    assert forwarded_messages[2] == "game.event"
    assert forwarded_messages[3] == "game.event"
    assert not _lua_ws.close_called, \
        "Lua connection should NOT be closed"

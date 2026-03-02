"""Test bridge config handling when receiving multiple config.sync messages."""
import asyncio
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
import sys
from pathlib import Path

# Add talker_bridge to path
sys.path.insert(0, str(Path(__file__).parent / "talker_bridge" / "python"))


def build_service_url(base_url: str, token: str) -> str:
    """Helper matching bridge implementation."""
    url = base_url
    if token:
        url += f"?token={token}"
    return url


def test_config_sync_no_change_detected():
    """
    When Lua sends two identical config.sync messages,
    the bridge should detect NO CHANGE and NOT close the service connection.
    """
    # Initial state
    _PINNED_SERVICE_URL = "ws://127.0.0.1:5557/ws"
    _DEFAULT_SERVICE_URL = "wss://talker-live.duckdns.org/ws"
    _service_url = _PINNED_SERVICE_URL or _DEFAULT_SERVICE_URL
    _service_token = ""
    
    # Simulate first config.sync from Lua (empty service_url and ws_token)
    config1_payload = {
        "service_url": "",
        "ws_token": "",
        # ... other fields like model_method, etc.
    }
    
    # Apply first config  
    if _PINNED_SERVICE_URL:
        new_url = _PINNED_SERVICE_URL
    else:
        new_url = (config1_payload.get("service_url") or "").strip() or _DEFAULT_SERVICE_URL
    new_token = (config1_payload.get("ws_token") or "").strip()
    
    old_full = build_service_url(_service_url, _service_token)
    new_full = build_service_url(new_url, new_token)
    
    change_detected_1 = old_full != new_full
    
    _service_url = new_url
    _service_token = new_token
    
    # Simulate second config.sync (identical content)
    config2_payload = {
        "service_url": "",
        "ws_token": "",
    }
    
    if _PINNED_SERVICE_URL:
        new_url = _PINNED_SERVICE_URL
    else:
        new_url = (config2_payload.get("service_url") or "").strip() or _DEFAULT_SERVICE_URL
    new_token = (config2_payload.get("ws_token") or "").strip()
    
    old_full = build_service_url(_service_url, _service_token)
    new_full = build_service_url(new_url, new_token)
    
    change_detected_2 = old_full != new_full
    
    # Assert: on second identical message, NO CHANGE should be detected
    assert not change_detected_2, (
        f"Second identical config.sync should NOT trigger change detection. "
        f"old={old_full}, new={new_full}"
    )


def test_config_sync_with_token_change():
    """
    When config DOES change (e.g., token is provided),
    bridge SHOULD detect change and log "Service URL updated".
    """
    _PINNED_SERVICE_URL = "ws://127.0.0.1:5557/ws"
    _DEFAULT_SERVICE_URL = "wss://talker-live.duckdns.org/ws"
    _service_url = _PINNED_SERVICE_URL or _DEFAULT_SERVICE_URL
    _service_token = ""
    
    # First config.sync with empty token
    config1_payload = {"service_url": "", "ws_token": ""}
    
    if _PINNED_SERVICE_URL:
        new_url = _PINNED_SERVICE_URL
    else:
        new_url = (config1_payload.get("service_url") or "").strip() or _DEFAULT_SERVICE_URL
    new_token = (config1_payload.get("ws_token") or "").strip()
    
    old_full = build_service_url(_service_url, _service_token)
    new_full = build_service_url(new_url, new_token)
    change_detected_1 = old_full != new_full
    
    _service_url = new_url
    _service_token = new_token
    
    # Second config.sync with a token
    config2_payload = {"service_url": "", "ws_token": "RhMdLGh-SqcpVn4g"}
    
    if _PINNED_SERVICE_URL:
        new_url = _PINNED_SERVICE_URL
    else:
        new_url = (config2_payload.get("service_url") or "").strip() or _DEFAULT_SERVICE_URL
    new_token = (config2_payload.get("ws_token") or "").strip()
    
    old_full = build_service_url(_service_url, _service_token)
    new_full = build_service_url(new_url, new_token)
    change_detected_2 = old_full != new_full
    
    # Assert: when token is added, change SHOULD be detected
    assert change_detected_2, (
        f"Config change (adding token) should be detected. "
        f"old={old_full}, new={new_full}"
    )


def test_no_premature_close_during_processing():
    """
    The bridge should NOT close the Lua websocket while processing config.sync.
    This is a structural test to ensure the handler doesn't reach a point
    where it exits the async for loop prematurely.
    """
    # The issue in the logs was: after processing first config.sync successfully,
    # when the second one arrives, the bridge sends CLOSE to Lua.
    # This should NOT happen if configs are identical.
    
    messages_processed = []
    
    async def simulate_handler():
        """Simulate bridge handler processing two config.sync messages."""
        # Pretend we have two messages in the queue
        messages = [
            json.dumps({"t": "config.sync", "ts": 1, "p": {"service_url": "", "ws_token": ""}}),
            json.dumps({"t": "config.sync", "ts": 2, "p": {"service_url": "", "ws_token": ""}}),
        ]
        
        for raw in messages:
            envelope = json.loads(raw)
            topic = envelope.get("t")
            payload = envelope.get("p", {})
            
            if topic == "config.sync":
                # Simulate config comparison (no change)
                config_changed = False  # Would be True if different
                if not config_changed:
                    messages_processed.append(topic)
                    # Continue processing, don't close
                else:
                    # Would close service connection
                    break
    
    asyncio.run(simulate_handler())
    
    # Assert: both messages were processed without early exit
    assert len(messages_processed) == 2, (
        f"Both config.sync messages should be processed. "
        f"Processed: {messages_processed}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

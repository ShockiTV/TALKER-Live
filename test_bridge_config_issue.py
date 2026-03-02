#!/usr/bin/env python3
"""Test script to reproduce and debug the bridge config issue."""

import asyncio
import json
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Simulate the issue
def test_config_comparison():
    """Test what values Lua is actually sending in config.sync."""
    
    # Simulate two config.sync payloads from Lua (from the logs)
    config1 = {
        "t": "config.sync",
        "ts": 1772455029000,
        "p": {
            "service_url": "",  # empty?
            "ws_token": "",     # empty?
            # ... other fields
        }
    }
    
    config2 = {
        "t": "config.sync",
        "ts": 1772455032000,
        "p": {
            "service_url": "",
            "ws_token": "",
            # ... other fields
        }
    }
    
    # The bridge code does this comparison
    def _build_service_url(base_url, token):
        url = base_url
        if token:
            url += f"?token={token}"
        return url
    
    # First message - what would happen?
    _PINNED_SERVICE_URL = "ws://127.0.0.1:5557/ws"
    _DEFAULT_SERVICE_URL = "wss://talker-live.duckdns.org/ws"
    _service_url = _PINNED_SERVICE_URL or _DEFAULT_SERVICE_URL
    _service_token = ""
    
    print(f"Initial state: url={_service_url}, token={_service_token}")
    
    # Process first config.sync
    service_url = config1["p"].get("service_url", "").strip() or _DEFAULT_SERVICE_URL
    ws_token = config1["p"].get("ws_token", "").strip()
    
    print(f"\nFirst config.sync:")
    print(f"  Received: service_url={repr(service_url)}, ws_token={repr(ws_token)}")
    
    # Since SERVICE_WS_URL is pinned, use that
    if _PINNED_SERVICE_URL:
        new_url = _PINNED_SERVICE_URL
    else:
        new_url = service_url or _DEFAULT_SERVICE_URL
    new_token = ws_token
    
    old_full = _build_service_url(_service_url, _service_token)
    new_full = _build_service_url(new_url, new_token)
    
    print(f"  Comparison: old={old_full} vs new={new_full}")
    print(f"  Change detected: {old_full != new_full}")
    
    _service_url = new_url
    _service_token = new_token
    
    # Process second config.sync
    service_url = config2["p"].get("service_url", "").strip() or _DEFAULT_SERVICE_URL
    ws_token = config2["p"].get("ws_token", "").strip()
    
    print(f"\nSecond config.sync:")
    print(f"  Received: service_url={repr(service_url)}, ws_token={repr(ws_token)}")
    
    if _PINNED_SERVICE_URL:
        new_url = _PINNED_SERVICE_URL
    else:
        new_url = service_url or _DEFAULT_SERVICE_URL
    new_token = ws_token
    
    old_full = _build_service_url(_service_url, _service_token)
    new_full = _build_service_url(new_url, new_token)
    
    print(f"  Comparison: old={old_full} vs new={new_full}")
    print(f"  Change detected: {old_full != new_full}")

if __name__ == "__main__":
    test_config_comparison()

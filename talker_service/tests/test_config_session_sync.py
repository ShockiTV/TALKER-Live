"""Tests for config.sync -> session sync orchestration."""

import asyncio

import pytest

from talker_service.handlers import config as config_handlers
from talker_service.transport.session_registry import SessionRegistry


class _SyncService:
    def __init__(self):
        self.calls = []

    async def sync_if_needed(self, **kwargs):
        self.calls.append(kwargs)
        return {"skipped": False}


@pytest.mark.asyncio
async def test_config_sync_triggers_session_sync_once_for_new_session():
    registry = SessionRegistry()
    sync_service = _SyncService()

    config_handlers.set_session_registry(registry)
    config_handlers.set_session_sync_service(sync_service)

    try:
        await config_handlers.handle_config_sync({"session_id": "lua-1"}, session_id="conn-1", req_id=1)
        await asyncio.sleep(0)

        ctx = registry.get_session("conn-1")
        assert ctx.game_session_id == "lua-1"
        assert len(sync_service.calls) == 1
        assert sync_service.calls[0]["previous_lua_session_id"] is None

        # Same-session reconnect should not re-trigger sync.
        await config_handlers.handle_config_sync({"session_id": "lua-1"}, session_id="conn-1", req_id=2)
        await asyncio.sleep(0)
        assert len(sync_service.calls) == 1
    finally:
        config_handlers.set_session_sync_service(None)
        config_handlers.set_session_registry(None)

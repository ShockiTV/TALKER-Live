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
        client = config_handlers.get_shared_http_client("conn-1")
        if client is not None:
            await client.aclose()

        config_handlers.set_session_sync_service(None)
        config_handlers.set_session_registry(None)


@pytest.mark.asyncio
async def test_config_sync_mcm_hub_url_overrides_env_hub_url():
    registry = SessionRegistry()

    config_handlers.set_session_registry(registry)
    config_handlers.set_session_sync_service(None)

    old_hub = config_handlers.settings.service_hub_url
    old_tts = config_handlers.settings.tts_service_url
    old_stt = config_handlers.settings.stt_endpoint
    old_ollama = config_handlers.settings.ollama_base_url
    old_fields = set(config_handlers.settings.model_fields_set)

    config_handlers.settings.service_hub_url = "https://default.example.com"
    config_handlers.settings.tts_service_url = ""
    config_handlers.settings.stt_endpoint = ""
    config_handlers.settings.ollama_base_url = ""

    config_handlers.settings.model_fields_set.discard("tts_service_url")
    config_handlers.settings.model_fields_set.discard("stt_endpoint")
    config_handlers.settings.model_fields_set.discard("ollama_base_url")
    config_handlers.settings.model_fields_set.add("service_hub_url")

    try:
        await config_handlers.handle_config_sync(
            {
                "service_type": 1,
                "service_hub_url": "https://custom.example.com",
            },
            session_id="conn-2",
            req_id=3,
        )

        urls = config_handlers.get_effective_service_urls("conn-2")
        assert urls["tts_service_url"] == "https://custom.example.com/api/tts"
        assert urls["stt_endpoint"] == "https://custom.example.com/api/stt/v1"
        assert urls["ollama_base_url"] == "https://custom.example.com/api/embed"
    finally:
        client = config_handlers.get_shared_http_client("conn-2")
        if client is not None:
            await client.aclose()

        config_handlers.settings.service_hub_url = old_hub
        config_handlers.settings.tts_service_url = old_tts
        config_handlers.settings.stt_endpoint = old_stt
        config_handlers.settings.ollama_base_url = old_ollama
        config_handlers.settings.model_fields_set.clear()
        config_handlers.settings.model_fields_set.update(old_fields)

        config_handlers.set_session_sync_service(None)
        config_handlers.set_session_registry(None)

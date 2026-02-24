"""Tests for WSRouter — connection, envelope parse, dispatch, publish, auth."""

import asyncio
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.transport.ws_router import WSRouter, parse_tokens


# ── Token parsing ─────────────────────────────────────────────────────────────


class TestParseTokens:
    """Tests for TALKER_TOKENS env var parsing."""

    def test_valid_tokens(self):
        tokens = parse_tokens("alice:token-abc, bob:token-xyz")
        assert tokens == {"alice": "token-abc", "bob": "token-xyz"}

    def test_none_returns_empty(self):
        assert parse_tokens(None) == {}

    def test_empty_string_returns_empty(self):
        assert parse_tokens("") == {}

    def test_whitespace_only_returns_empty(self):
        assert parse_tokens("   ") == {}

    def test_malformed_entry_skipped(self):
        tokens = parse_tokens("alice:token-abc,badentry")
        assert tokens == {"alice": "token-abc"}

    def test_strips_whitespace(self):
        tokens = parse_tokens("  alice : abc ,  bob : xyz  ")
        assert tokens == {"alice": "abc", "bob": "xyz"}

    def test_colon_in_token_value(self):
        tokens = parse_tokens("alice:token:with:colons")
        assert tokens == {"alice": "token:with:colons"}


# ── WSRouter unit tests ──────────────────────────────────────────────────────


def _make_mock_ws(query_params=None, accepted=True):
    """Create a mock WebSocket with configurable query params."""
    ws = AsyncMock()
    ws.query_params = query_params or {}
    ws.client_state = MagicMock()
    # Make close a no-op coroutine
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestWSRouterInit:
    def test_default_no_auth(self):
        with patch.dict("os.environ", {}, clear=True):
            router = WSRouter(tokens={})
        assert not router._auth_enabled

    def test_auth_enabled_with_tokens(self):
        router = WSRouter(tokens={"alice": "abc"})
        assert router._auth_enabled

    def test_reads_env_when_tokens_none(self):
        with patch.dict("os.environ", {"TALKER_TOKENS": "alice:abc"}):
            router = WSRouter(tokens=None)
        assert router._auth_enabled
        assert router._tokens == {"alice": "abc"}


class TestWSRouterHandlers:
    def test_register_handler(self):
        router = WSRouter(tokens={})
        handler = AsyncMock()
        router.on("game.event", handler)
        assert "game.event" in router.handlers

    def test_register_handler_alias(self):
        router = WSRouter(tokens={})
        handler = AsyncMock()
        router.register_handler("game.event", handler)
        assert "game.event" in router.handlers


class TestWSRouterProcessMessage:
    @pytest.mark.asyncio
    async def test_valid_envelope_dispatches_handler(self):
        router = WSRouter(tokens={})
        handler = AsyncMock()
        router.on("game.event", handler)

        raw = json.dumps({"t": "game.event", "p": {"type": "DEATH"}})
        await router._process_message(raw)

        # Handler is called via create_task; let event loop run
        await asyncio.sleep(0)
        handler.assert_awaited_once_with({"type": "DEATH"})

    @pytest.mark.asyncio
    async def test_malformed_json_discarded(self):
        router = WSRouter(tokens={})
        handler = AsyncMock()
        router.on("game.event", handler)

        await router._process_message("not json {{{")
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_t_field_discarded(self):
        router = WSRouter(tokens={})
        handler = AsyncMock()
        router.on("game.event", handler)

        raw = json.dumps({"p": {"type": "DEATH"}})
        await router._process_message(raw)
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_r_field_resolves_pending_future(self):
        router = WSRouter(tokens={})
        future = router.create_request("req-1", timeout=10.0)

        raw = json.dumps({"t": "state.response", "p": {"answer": 42}, "r": "req-1"})
        await router._process_message(raw)

        result = await asyncio.wait_for(future, timeout=1.0)
        assert result == {"answer": 42}

    @pytest.mark.asyncio
    async def test_r_field_bypasses_topic_handler(self):
        router = WSRouter(tokens={})
        handler = AsyncMock()
        router.on("state.response", handler)
        router.create_request("req-1", timeout=10.0)

        raw = json.dumps({"t": "state.response", "p": {}, "r": "req-1"})
        await router._process_message(raw)
        await asyncio.sleep(0)

        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_r_field_discarded(self):
        router = WSRouter(tokens={})
        handler = AsyncMock()
        router.on("state.response", handler)

        raw = json.dumps({"t": "state.response", "p": {}, "r": "unknown-id"})
        await router._process_message(raw)
        await asyncio.sleep(0)

        # Neither handler nor pending request should fire
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_r_field_error_sets_exception(self):
        router = WSRouter(tokens={})
        future = router.create_request("req-err", timeout=10.0)

        raw = json.dumps({"t": "state.response", "p": {"error": "boom"}, "r": "req-err"})
        await router._process_message(raw)

        with pytest.raises(Exception, match="boom"):
            await asyncio.wait_for(future, timeout=1.0)

    @pytest.mark.asyncio
    async def test_no_handler_for_topic_is_noop(self):
        router = WSRouter(tokens={})
        # No handler registered — should not raise
        raw = json.dumps({"t": "unknown.topic", "p": {}})
        await router._process_message(raw)  # no exception


class TestWSRouterPublish:
    @pytest.mark.asyncio
    async def test_publish_sends_to_connected_client(self):
        router = WSRouter(tokens={})
        ws = _make_mock_ws()
        router._connections.append(ws)

        await router.publish("dialogue.display", {"speaker_id": "5"})

        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["t"] == "dialogue.display"
        assert sent["p"]["speaker_id"] == "5"
        assert "ts" in sent

    @pytest.mark.asyncio
    async def test_publish_with_r_field(self):
        router = WSRouter(tokens={})
        ws = _make_mock_ws()
        router._connections.append(ws)

        await router.publish("state.query.batch", {"queries": []}, r="req-99")

        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["r"] == "req-99"

    @pytest.mark.asyncio
    async def test_publish_no_clients_is_noop(self):
        router = WSRouter(tokens={})
        result = await router.publish("test", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_publish_to_multiple_clients(self):
        router = WSRouter(tokens={})
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        router._connections.extend([ws1, ws2])

        await router.publish("test", {})

        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()


class TestWSRouterLifecycle:
    @pytest.mark.asyncio
    async def test_stop_clears_connections(self):
        router = WSRouter(tokens={})
        ws = _make_mock_ws()
        router._connections.append(ws)
        router.is_connected = True

        await router.stop()

        assert len(router._connections) == 0
        assert router.is_connected is False
        ws.close.assert_awaited_once_with(code=1001)

    @pytest.mark.asyncio
    async def test_stop_cancels_pending_requests(self):
        router = WSRouter(tokens={})
        future = router.create_request("req-1", timeout=60.0)

        await router.stop()

        assert future.cancelled()
        assert len(router._pending_requests) == 0

    @pytest.mark.asyncio
    async def test_shutdown_alias(self):
        router = WSRouter(tokens={})
        assert router.shutdown == router.stop


class TestWSRouterAuth:
    @pytest.mark.asyncio
    async def test_no_auth_accepts_all(self):
        router = WSRouter(tokens={})
        ws = _make_mock_ws()
        # Simulate disconnect after accept so the loop exits
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await router.websocket_endpoint(ws)

        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_valid_token_accepted(self):
        router = WSRouter(tokens={"alice": "secret-token"})
        ws = _make_mock_ws(query_params={"token": "secret-token"})
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await router.websocket_endpoint(ws)

        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self):
        router = WSRouter(tokens={"alice": "secret-token"})
        ws = _make_mock_ws(query_params={"token": "wrong-token"})

        await router.websocket_endpoint(ws)

        ws.close.assert_awaited_once_with(code=4001)
        ws.accept.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_token_rejected_when_auth_enabled(self):
        router = WSRouter(tokens={"alice": "secret-token"})
        ws = _make_mock_ws(query_params={})

        await router.websocket_endpoint(ws)

        ws.close.assert_awaited_once_with(code=4001)
        ws.accept.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_token_required_in_local_mode(self):
        router = WSRouter(tokens={})
        ws = _make_mock_ws(query_params={})
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await router.websocket_endpoint(ws)

        ws.accept.assert_awaited_once()

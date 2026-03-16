"""Tests for WSRouter — connection, envelope parse, dispatch, publish, auth."""

import asyncio
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.transport.ws_router import WSRouter, parse_tokens, _decode_jwt_claims
from talker_service.transport.session_registry import SessionRegistry


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
    ws.headers = {}
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
        handler.assert_awaited_once()
        call_args = handler.await_args
        assert call_args[0][0] == {"type": "DEATH"}
        assert call_args[0][1] == "__default__"
        assert isinstance(call_args[0][2], int)  # req_id

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


class TestWSRouterHeaders:
    @pytest.mark.asyncio
    async def test_header_extraction_sets_session_context(self):
        router = WSRouter(tokens={})
        registry = SessionRegistry()
        router.set_session_registry(registry)

        ws = _make_mock_ws(query_params={})
        ws.headers = {"x-player-id": "player1", "x-branch": "dev"}
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await router.websocket_endpoint(ws)

        ctx = registry.get_session("player1")
        assert ctx.player_id == "player1"
        assert ctx.branch == "dev"

    @pytest.mark.asyncio
    async def test_missing_headers_use_defaults(self):
        router = WSRouter(tokens={})
        registry = SessionRegistry()
        router.set_session_registry(registry)

        ws = _make_mock_ws(query_params={})
        ws.headers = {}
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await router.websocket_endpoint(ws)

        ctx = registry.get_session("__default__")
        assert ctx.player_id == "local"
        assert ctx.branch == "main"


# ── JWT decode ────────────────────────────────────────────────────────────────

import base64


def _make_jwt(payload: dict) -> str:
    """Build a fake JWT (header.payload.signature) with the given claims."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fake-signature").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


class TestDecodeJwtClaims:
    def test_valid_jwt(self):
        token = _make_jwt({"sub": "user-123", "preferred_username": "alice"})
        claims = _decode_jwt_claims(token)
        assert claims is not None
        assert claims["sub"] == "user-123"
        assert claims["preferred_username"] == "alice"

    def test_not_a_jwt(self):
        assert _decode_jwt_claims("plain-token") is None
        assert _decode_jwt_claims("only.two") is None

    def test_invalid_base64(self):
        assert _decode_jwt_claims("a.!!!.c") is None

    def test_invalid_json_payload(self):
        bad_payload = base64.urlsafe_b64encode(b"not-json").rstrip(b"=").decode()
        assert _decode_jwt_claims(f"a.{bad_payload}.c") is None


class TestJwtAuth:
    @pytest.mark.asyncio
    async def test_jwt_query_param_sets_player_id(self):
        """JWT ?token= should set player_id and session_id from sub claim."""
        jwt = _make_jwt({"sub": "keycloak-uuid-42"})
        router = WSRouter(tokens={})
        registry = SessionRegistry()
        router.set_session_registry(registry)

        ws = _make_mock_ws(query_params={"token": jwt})
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await router.websocket_endpoint(ws)

        ctx = registry.get_session("keycloak-uuid-42")
        assert ctx.player_id == "keycloak-uuid-42"

    @pytest.mark.asyncio
    async def test_jwt_preferred_username_fallback(self):
        """When sub is absent, preferred_username is used."""
        jwt = _make_jwt({"preferred_username": "alice"})
        router = WSRouter(tokens={})
        registry = SessionRegistry()
        router.set_session_registry(registry)

        ws = _make_mock_ws(query_params={"token": jwt})
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await router.websocket_endpoint(ws)

        ctx = registry.get_session("alice")
        assert ctx.player_id == "alice"

    @pytest.mark.asyncio
    async def test_proxy_headers_override_jwt(self):
        """Caddy X-Player-ID header takes priority over JWT sub."""
        jwt = _make_jwt({"sub": "from-jwt"})
        router = WSRouter(tokens={})
        registry = SessionRegistry()
        router.set_session_registry(registry)

        ws = _make_mock_ws(query_params={"token": jwt})
        ws.headers = {"x-player-id": "from-caddy", "x-branch": "dev"}
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await router.websocket_endpoint(ws)

        # session_id comes from JWT sub (set before headers), but player_id
        # is overridden by the trusted proxy header
        ctx = registry.get_session("from-jwt")
        assert ctx.player_id == "from-caddy"
        assert ctx.branch == "dev"

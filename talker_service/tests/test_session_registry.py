"""Tests for transport.session_registry — per-session state management."""

import pytest

from talker_service.transport.session_registry import SessionRegistry
from talker_service.handlers.config import ConfigMirror


class TestSessionRegistryConfig:
    def test_get_config_creates_default(self):
        reg = SessionRegistry()
        cfg = reg.get_config("alice")
        assert isinstance(cfg, ConfigMirror)

    def test_get_config_returns_same_instance(self):
        reg = SessionRegistry()
        cfg1 = reg.get_config("alice")
        cfg2 = reg.get_config("alice")
        assert cfg1 is cfg2

    def test_different_sessions_independent_configs(self):
        reg = SessionRegistry()
        alice_cfg = reg.get_config("alice")
        bob_cfg = reg.get_config("bob")
        assert alice_cfg is not bob_cfg

    def test_config_update_isolation(self):
        reg = SessionRegistry()
        alice_cfg = reg.get_config("alice")
        bob_cfg = reg.get_config("bob")
        alice_cfg.sync({"ai_model_method": 1, "custom_ai_model": "gpt-4o"})
        assert alice_cfg.get("model_method") == 1
        assert bob_cfg.get("model_method") == 0  # default


class TestSessionRegistrySession:
    def test_get_session_creates_context(self):
        reg = SessionRegistry()
        ctx = reg.get_session("alice")
        assert ctx.session_id == "alice"
        assert not ctx.is_connected
        assert ctx.outbox.is_empty

    def test_get_session_returns_same_instance(self):
        reg = SessionRegistry()
        s1 = reg.get_session("alice")
        s2 = reg.get_session("alice")
        assert s1 is s2

    def test_outbox_ttl_propagated(self):
        reg = SessionRegistry(outbox_ttl_seconds=120, outbox_max_size=10)
        ctx = reg.get_session("alice")
        assert ctx.outbox._ttl_seconds == 120
        assert ctx.outbox._max_size == 10


class TestSessionRegistryRemove:
    def test_remove_session_clears_all_state(self):
        reg = SessionRegistry()
        reg.get_config("alice")
        reg.get_session("alice")
        assert "alice" in reg.session_ids
        reg.remove_session("alice")
        assert "alice" not in reg.session_ids

    def test_remove_nonexistent_is_noop(self):
        reg = SessionRegistry()
        reg.remove_session("ghost")  # should not raise

    def test_reaccess_after_remove_creates_fresh(self):
        reg = SessionRegistry()
        cfg1 = reg.get_config("alice")
        reg.remove_session("alice")
        cfg2 = reg.get_config("alice")
        assert cfg1 is not cfg2


class TestSessionRegistryIntrospection:
    def test_session_ids(self):
        reg = SessionRegistry()
        reg.get_config("alice")
        reg.get_session("bob")
        ids = reg.session_ids
        assert "alice" in ids
        assert "bob" in ids

    def test_active_session_count_zero_when_disconnected(self):
        reg = SessionRegistry()
        reg.get_session("alice")
        assert reg.active_session_count == 0

    def test_repr(self):
        reg = SessionRegistry()
        assert "SessionRegistry" in repr(reg)


class TestSessionRegistryGlobalCallbacks:
    """Tests for on_any_config_change() — global callback propagation."""

    def test_global_callback_fires_on_session_sync(self):
        """Task 1.3: Global callback fires when per-session mirror is synced."""
        reg = SessionRegistry()
        received = []
        reg.on_any_config_change(lambda cfg: received.append(cfg))

        mirror = reg.get_config("__default__")
        mirror.sync({"ai_model_method": 1, "custom_ai_model": "gpt-4o"})

        assert len(received) == 1
        assert received[0].model_method == 1

    def test_global_callback_fires_from_multiple_sessions(self):
        """Task 1.4: Global callback fires from multiple different sessions."""
        reg = SessionRegistry()
        calls = []
        reg.on_any_config_change(lambda cfg: calls.append(cfg))

        reg.get_config("alice").sync({"ai_model_method": 1})
        reg.get_config("bob").sync({"ai_model_method": 2})

        assert len(calls) == 2
        assert calls[0].model_method == 1
        assert calls[1].model_method == 2

    def test_late_session_inherits_global_callbacks(self):
        """Task 1.5: Late session inherits global callbacks registered at startup."""
        reg = SessionRegistry()
        calls = []
        reg.on_any_config_change(lambda cfg: calls.append("fired"))

        # First session triggers callback
        reg.get_config("early").sync({})
        assert len(calls) == 1

        # Late session also triggers callback
        reg.get_config("late").sync({})
        assert len(calls) == 2

    def test_multiple_global_callbacks_all_fire(self):
        """Multiple global callbacks all fire on config sync."""
        reg = SessionRegistry()
        a_calls, b_calls = [], []
        reg.on_any_config_change(lambda cfg: a_calls.append(1))
        reg.on_any_config_change(lambda cfg: b_calls.append(1))

        reg.get_config("s1").sync({})
        assert len(a_calls) == 1
        assert len(b_calls) == 1

    def test_existing_mirror_not_affected_by_later_registration(self):
        """Callbacks registered after mirror creation don't propagate to it."""
        reg = SessionRegistry()
        calls = []

        # Create a mirror first, before any callbacks registered
        early_mirror = reg.get_config("early")

        # Now register a callback
        reg.on_any_config_change(lambda cfg: calls.append(1))

        # The early mirror should NOT have the callback
        early_mirror.sync({})
        assert len(calls) == 0

        # But a new mirror should
        reg.get_config("late").sync({})
        assert len(calls) == 1

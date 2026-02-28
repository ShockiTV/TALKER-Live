"""Tests for transport.session_registry — per-session state management."""

import pytest

from talker_service.transport.session_registry import SessionRegistry
from talker_service.handlers.config import ConfigMirror
from talker_service.dialogue.speaker import SpeakerSelector


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


class TestSessionRegistrySpeaker:
    def test_get_speaker_selector_creates_default(self):
        reg = SessionRegistry()
        ss = reg.get_speaker_selector("alice")
        assert isinstance(ss, SpeakerSelector)

    def test_get_speaker_selector_returns_same_instance(self):
        reg = SessionRegistry()
        s1 = reg.get_speaker_selector("alice")
        s2 = reg.get_speaker_selector("alice")
        assert s1 is s2

    def test_different_sessions_independent_selectors(self):
        reg = SessionRegistry()
        alice_ss = reg.get_speaker_selector("alice")
        bob_ss = reg.get_speaker_selector("bob")
        assert alice_ss is not bob_ss

    def test_cooldown_isolation(self):
        reg = SessionRegistry()
        alice_ss = reg.get_speaker_selector("alice")
        bob_ss = reg.get_speaker_selector("bob")
        alice_ss.set_spoke("npc_1", 1000)
        assert alice_ss.is_on_cooldown("npc_1", 1500)
        assert not bob_ss.is_on_cooldown("npc_1", 1500)


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
        reg.get_speaker_selector("alice")
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
        reg.get_speaker_selector("bob")
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

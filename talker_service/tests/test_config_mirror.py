"""Tests for config mirror functionality."""

import pytest
from unittest.mock import MagicMock, patch

from talker_service.handlers.config import ConfigMirror, config_mirror


class TestConfigMirror:
    """Tests for ConfigMirror class."""

    def test_initialization_with_defaults(self):
        """Test ConfigMirror initializes with default config."""
        mirror = ConfigMirror()
        
        assert mirror.is_synced is False
        assert mirror.config is not None

    def test_update_sets_synced_flag(self, sample_config_payload):
        """Test that update sets the synced flag."""
        mirror = ConfigMirror()
        
        assert mirror.is_synced is False
        
        mirror.update(sample_config_payload)
        
        assert mirror.is_synced is True

    def test_update_stores_config_values(self, sample_config_payload):
        """Test that update stores config values correctly."""
        mirror = ConfigMirror()
        
        mirror.update(sample_config_payload)
        
        assert mirror.config.zmq_port == 5555
        assert mirror.config.zmq_heartbeat_interval == 5

    def test_get_existing_key(self, sample_config_payload):
        """Test get() returns correct value for existing key."""
        mirror = ConfigMirror()
        mirror.update(sample_config_payload)
        
        assert mirror.get("zmq_port") == 5555

    def test_get_nonexistent_key_returns_default(self):
        """Test get() returns default for non-existent key."""
        mirror = ConfigMirror()
        
        result = mirror.get("nonexistent_key", "default_value")
        
        assert result == "default_value"

    def test_get_nonexistent_key_returns_none_by_default(self):
        """Test get() returns None when no default provided."""
        mirror = ConfigMirror()
        
        result = mirror.get("nonexistent_key")
        
        assert result is None

    def test_dump_returns_dict(self, sample_config_payload):
        """Test dump() returns dictionary with config data."""
        mirror = ConfigMirror()
        mirror.update(sample_config_payload)
        
        dumped = mirror.dump()
        
        assert isinstance(dumped, dict)
        assert "received_sync" in dumped
        assert "config" in dumped
        assert dumped["received_sync"] is True

    def test_on_change_callback_registration(self):
        """Test callback registration for config changes."""
        mirror = ConfigMirror()
        
        callback_called = False
        received_config = None
        
        def my_callback(config):
            nonlocal callback_called, received_config
            callback_called = True
            received_config = config
        
        mirror.on_change(my_callback)
        mirror.update({"zmq_port": 5555})
        
        assert callback_called is True
        assert received_config is not None

    def test_multiple_callbacks(self, sample_config_payload):
        """Test multiple callbacks are all called."""
        mirror = ConfigMirror()
        
        call_count = 0
        
        def callback1(config):
            nonlocal call_count
            call_count += 1
        
        def callback2(config):
            nonlocal call_count
            call_count += 1
        
        mirror.on_change(callback1)
        mirror.on_change(callback2)
        mirror.update(sample_config_payload)
        
        assert call_count == 2

    def test_callback_error_does_not_stop_others(self, sample_config_payload):
        """Test that error in one callback doesn't prevent others."""
        mirror = ConfigMirror()
        
        second_callback_called = False
        
        def failing_callback(config):
            raise Exception("Intentional test error")
        
        def working_callback(config):
            nonlocal second_callback_called
            second_callback_called = True
        
        mirror.on_change(failing_callback)
        mirror.on_change(working_callback)
        
        # Should not raise, should continue to second callback
        mirror.update(sample_config_payload)
        
        assert second_callback_called is True


class TestPinMechanism:
    """Tests for ConfigMirror pin() / get() override behaviour (task 7.1)."""

    def test_pin_overrides_get(self, sample_config_payload):
        """Pinned field returns pinned value, not MCM value."""
        mirror = ConfigMirror()
        mirror.update(sample_config_payload)

        # MCM says model_method=1
        assert mirror.get("model_method") == 1

        mirror.pin("model_method", 0)
        assert mirror.get("model_method") == 0

    def test_unpinned_field_passthrough(self, sample_config_payload):
        """Unpinned fields still return MCM config values."""
        mirror = ConfigMirror()
        mirror.pin("model_method", 3)
        mirror.update(sample_config_payload)

        # model_name is not pinned — MCM value should pass through
        assert mirror.get("model_name") == "gpt-4"

    def test_pin_overrides_model_name(self, sample_config_payload):
        """Pinning model_name overrides the MCM model_name."""
        mirror = ConfigMirror()
        mirror.update(sample_config_payload)
        mirror.pin("model_name", "claude-opus-4")

        assert mirror.get("model_name") == "claude-opus-4"

    def test_pin_appears_in_dump(self):
        """dump() includes the pins dict."""
        mirror = ConfigMirror()
        mirror.pin("model_method", 2)
        mirror.pin("model_name", "llama3")

        dumped = mirror.dump()
        assert "pins" in dumped
        assert dumped["pins"]["model_method"] == 2
        assert dumped["pins"]["model_name"] == "llama3"

    def test_get_returns_default_when_no_pin_and_no_config(self):
        """get() falls back to default when field is neither pinned nor in config."""
        mirror = ConfigMirror()
        assert mirror.get("nonexistent", "fallback") == "fallback"

    def test_audit_log_on_pin_mismatch(self, sample_config_payload):
        """_audit_pins logs when MCM disagrees with pin."""
        mirror = ConfigMirror()
        mirror.pin("model_method", 0)  # pin to openai

        # MCM sends model_method=1 (openrouter)
        with patch("talker_service.handlers.config.logger") as mock_logger:
            mirror.update(sample_config_payload)
            # Verify audit log was emitted for the mismatch
            audit_calls = [
                c for c in mock_logger.info.call_args_list
                if "pinned" in str(c).lower()
            ]
            assert len(audit_calls) >= 1, "Expected audit log for pinned field mismatch"


class TestCacheClearingWithPins:
    """Tests for LLM cache clearing around pinned fields (task 7.2)."""

    def test_cache_not_cleared_when_pinned_values_unchanged(self, sample_config_payload):
        """Cache stays intact when MCM changes a pinned field."""
        mirror = ConfigMirror()
        mirror.pin("model_method", 0)
        mirror.pin("model_name", "pinned-model")

        # First sync to set baseline
        mirror.sync(sample_config_payload)

        # Second sync with different MCM values — but pins unchanged
        payload2 = dict(sample_config_payload, model_method=2, model_name="different")
        with patch("talker_service.llm.factory.clear_client_cache") as mock_clear:
            mirror.sync(payload2)
            mock_clear.assert_not_called()

    def test_cache_cleared_when_effective_values_actually_change(self):
        """Cache cleared when unpinned effective values change."""
        mirror = ConfigMirror()

        # First update: method=0, model=""
        mirror.update({"model_method": 0, "model_name": ""})

        # Second update: method=1 — not pinned, effective value changes
        with patch("talker_service.llm.factory.clear_client_cache") as mock_clear:
            mirror.update({"model_method": 1, "model_name": "gpt-4"})
            mock_clear.assert_called_once()

    def test_sync_clears_cache_on_first_sync_when_values_differ(self, sample_config_payload):
        """First sync clears cache because defaults differ from MCM."""
        mirror = ConfigMirror()
        # defaults: model_method=0, model_name=""
        # fixture: model_method=1, model_name="gpt-4"
        with patch("talker_service.llm.factory.clear_client_cache") as mock_clear:
            mirror.sync(sample_config_payload)
            mock_clear.assert_called_once()


class TestGlobalConfigMirror:
    """Tests for the global config_mirror instance."""

    def test_global_instance_exists(self):
        """Test that global config_mirror instance exists."""
        assert config_mirror is not None
        assert isinstance(config_mirror, ConfigMirror)

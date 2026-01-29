"""Tests for config mirror functionality."""

import pytest
from unittest.mock import MagicMock

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
        
        assert mirror.config.zmq_enabled is True
        assert mirror.config.zmq_port == 5555
        assert mirror.config.zmq_heartbeat_interval == 5

    def test_get_existing_key(self, sample_config_payload):
        """Test get() returns correct value for existing key."""
        mirror = ConfigMirror()
        mirror.update(sample_config_payload)
        
        assert mirror.get("zmq_enabled") is True
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
        mirror.update({"zmq_enabled": True, "zmq_port": 5555})
        
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


class TestGlobalConfigMirror:
    """Tests for the global config_mirror instance."""

    def test_global_instance_exists(self):
        """Test that global config_mirror instance exists."""
        assert config_mirror is not None
        assert isinstance(config_mirror, ConfigMirror)

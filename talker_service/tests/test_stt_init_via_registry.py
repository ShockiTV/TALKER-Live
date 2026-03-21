"""Integration test: config.sync triggers STT provider init via session registry.

Validates that the STT-init callback fires when config is synced through
a per-session ConfigMirror created by SessionRegistry, rather than through
the module-level config_mirror singleton.  This is the exact bug fixed by
the stt-init change.
"""

from unittest.mock import MagicMock, patch

import pytest

from talker_service.transport.session_registry import SessionRegistry
from talker_service.handlers.config import ConfigMirror


class TestSttInitViaRegistry:
    """Integration: config.sync → SessionRegistry → global callback → STT init."""

    def test_stt_init_fires_on_config_sync(self):
        """config.sync on per-session mirror triggers the STT init callback."""
        registry = SessionRegistry()

        # Simulate the _init_stt_on_config pattern from __main__.py
        _stt_initialised = False
        stt_provider_ref = [None]

        def _init_stt_on_config(cfg):
            nonlocal _stt_initialised
            if _stt_initialised:
                return
            _stt_initialised = True
            stt_provider_ref[0] = "mock_stt_provider"

        registry.on_any_config_change(_init_stt_on_config)

        # A client connects and sends config.sync
        mirror = registry.get_config("__default__")
        mirror.sync({"stt_method": 1})

        assert _stt_initialised is True
        assert stt_provider_ref[0] == "mock_stt_provider"

    def test_stt_init_does_not_repeat(self):
        """Once _stt_initialised=True, subsequent config syncs don't re-init."""
        registry = SessionRegistry()

        call_count = [0]
        _stt_initialised = False

        def _init_stt_on_config(cfg):
            nonlocal _stt_initialised
            if _stt_initialised:
                return
            _stt_initialised = True
            call_count[0] += 1

        registry.on_any_config_change(_init_stt_on_config)

        # First sync triggers init
        registry.get_config("alice").sync({"stt_method": 1})
        assert call_count[0] == 1

        # Second sync from different session does not re-init
        registry.get_config("bob").sync({"stt_method": 2})
        assert call_count[0] == 1

    def test_tts_volume_callback_fires_via_registry(self):
        """TTS volume callback fires through session registry wiring."""
        registry = SessionRegistry()
        volume_updates = []

        def _on_config_change(cfg):
            vol = getattr(cfg, "tts_volume_boost", None)
            if vol is not None:
                volume_updates.append(float(vol))

        registry.on_any_config_change(_on_config_change)

        mirror = registry.get_config("player1")
        mirror.sync({"tts_volume_boost": 1.5})

        assert len(volume_updates) == 1
        assert volume_updates[0] == 1.5

    def test_old_global_mirror_would_not_fire(self):
        """Demonstrates the bug: callbacks on a standalone mirror don't fire
        when a separate per-session mirror is synced."""
        global_mirror = ConfigMirror()  # The old pattern
        calls = []
        global_mirror.on_change(lambda cfg: calls.append(1))

        # Per-session mirror is a different instance
        session_mirror = ConfigMirror()
        session_mirror.sync({"stt_method": 1})

        # The global callback never fires — this was the bug
        assert len(calls) == 0

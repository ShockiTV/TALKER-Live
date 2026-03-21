"""Tests for Settings server-authority-pin fields and backward compat (task 7.3)."""

import pytest
from unittest.mock import patch


class TestSettingsBackwardCompat:
    """FORCE_PROXY_LLM / FORCE_LOCAL_WHISPER → new pin fields."""

    def _make_settings(self, env_overrides: dict):
        """Create a fresh Settings instance with env overrides.

        We patch ``os.environ`` so pydantic-settings picks up the
        overrides without touching real env vars.
        """
        import os

        env = {**os.environ, **env_overrides}
        with patch.dict(os.environ, env, clear=True):
            from talker_service.config import Settings

            return Settings(
                _env_file=None,  # don't read .env file during tests
                **{k.lower(): v for k, v in env_overrides.items()
                   if k.lower() in Settings.model_fields},
            )

    def test_force_proxy_llm_sets_llm_provider(self):
        """FORCE_PROXY_LLM=true → llm_provider='proxy' when llm_provider absent."""
        s = self._make_settings({"FORCE_PROXY_LLM": "true"})
        assert s.llm_provider == "proxy"

    def test_explicit_llm_provider_wins_over_force_flag(self):
        """Explicit LLM_PROVIDER takes precedence over FORCE_PROXY_LLM."""
        s = self._make_settings({
            "FORCE_PROXY_LLM": "true",
            "LLM_PROVIDER": "openai",
        })
        assert s.llm_provider == "openai"

    def test_force_local_whisper_sets_stt_method(self):
        """FORCE_LOCAL_WHISPER=true → stt_method='local' when stt_method absent."""
        s = self._make_settings({"FORCE_LOCAL_WHISPER": "true"})
        assert s.stt_method == "local"

    def test_explicit_stt_method_wins_over_force_flag(self):
        """Explicit STT_METHOD takes precedence over FORCE_LOCAL_WHISPER."""
        s = self._make_settings({
            "FORCE_LOCAL_WHISPER": "true",
            "STT_METHOD": "api",
        })
        assert s.stt_method == "api"

    def test_no_flags_leaves_fields_none(self):
        """When no force flags and no new fields, pin fields stay None."""
        s = self._make_settings({})
        assert s.llm_provider is None
        assert s.stt_method is None

    def test_openai_endpoint_default_empty(self):
        """openai_endpoint defaults to empty string."""
        s = self._make_settings({})
        assert s.openai_endpoint == ""

    def test_openai_endpoint_set(self):
        """openai_endpoint can be set via env."""
        s = self._make_settings({"OPENAI_ENDPOINT": "https://my-azure.openai.azure.com/v1/chat/completions"})
        assert "azure" in s.openai_endpoint


class TestServiceHubDerivation:
    """SERVICE_HUB_URL derives per-service endpoints unless explicitly overridden."""

    def _make_settings(self, env_overrides: dict):
        import os

        env = {**os.environ, **env_overrides}
        with patch.dict(os.environ, env, clear=True):
            from talker_service.config import Settings

            return Settings(
                _env_file=None,
                **{
                    k.lower(): v
                    for k, v in env_overrides.items()
                    if k.lower() in Settings.model_fields
                },
            )

    def test_service_hub_derives_all_service_urls(self):
        s = self._make_settings({"SERVICE_HUB_URL": "https://talker-live.duckdns.org"})
        assert s.tts_service_url == "https://talker-live.duckdns.org/api/tts"
        assert s.stt_endpoint == "https://talker-live.duckdns.org/api/stt/v1"
        assert s.ollama_base_url == "https://talker-live.duckdns.org/api/embed"

    def test_explicit_urls_override_hub_derivation(self):
        s = self._make_settings(
            {
                "SERVICE_HUB_URL": "https://talker-live.duckdns.org",
                "TTS_SERVICE_URL": "http://127.0.0.1:8100",
                "STT_ENDPOINT": "http://127.0.0.1:8200/v1",
                "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
            }
        )
        assert s.tts_service_url == "http://127.0.0.1:8100"
        assert s.stt_endpoint == "http://127.0.0.1:8200/v1"
        assert s.ollama_base_url == "http://127.0.0.1:11434"

    def test_empty_hub_leaves_service_urls_unset(self):
        s = self._make_settings({})
        assert s.service_hub_url == ""
        assert s.tts_service_url == ""
        assert s.stt_endpoint == ""
        assert s.ollama_base_url == ""

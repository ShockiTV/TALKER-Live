"""Service configuration using pydantic-settings."""

import os
from typing import Optional
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE_OVERRIDE = os.getenv("TALKER_SERVICE_ENV_FILE", "").strip()
_ENV_FILES = _ENV_FILE_OVERRIDE or (".env.local", ".env")


class Settings(BaseSettings):
    """TALKER Service configuration."""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # WebSocket Settings
    ws_host: str = "127.0.0.1"
    ws_port: int = 5557  # Service WS + HTTP endpoint (game client connects here)
    talker_tokens: str = ""  # TALKER_TOKENS override (name:token,...)
    
    # Logging
    log_level: str = "INFO"
    log_file: Path = Path("logs/talker_service.log")
    log_heartbeat: bool = False  # If True, log heartbeat messages (verbose)
    
    # LLM Settings
    default_llm_provider: str = "openai"  # openai, openrouter, ollama, proxy
    llm_timeout: float = 60.0  # seconds
    
    # Server authority pins — when set, MCM cannot override these
    llm_provider: Optional[str] = None  # openai | openrouter | ollama | proxy
    llm_model: Optional[str] = None  # pins model_name
    llm_model_fast: Optional[str] = None  # pins model_name_fast
    stt_method: Optional[str] = None  # local | api | proxy
    
    # OpenAI settings
    openai_endpoint: str = ""  # Custom endpoint (e.g. Azure); empty = default api.openai.com

    # Proxy settings (for model_method = 3)
    force_proxy_llm: bool = False  # Backward compat alias for llm_provider=proxy
    proxy_endpoint: str = "http://127.0.0.1:8000/v1/chat/completions"
    proxy_api_key: str = "VerysecretKey"
    proxy_model: str = ""
    
    # State Query Settings
    state_query_timeout: float = 30.0  # seconds
    
    # STT Settings (local Whisper)
    force_local_whisper: bool = False  # Backward compat alias for stt_method=local
    whisper_model: str = "base.en"  # faster-whisper model name (e.g. tiny.en, base.en, small.en, distil-large-v3)
    whisper_beam_size: int = 1  # Beam search width (1 = greedy/fast, 5 = higher quality)

    # TTS Settings
    tts_enabled: bool = False  # Enable in-engine TTS audio generation
    voices_dir: Path = Path("./voices")  # Directory containing .safetensors voice files (flat layout)
    tts_service_url: str = ""  # Remote TTS service URL (e.g. http://tts-service:8100); empty = embedded engine

    # Remote STT endpoint (for use with faster-whisper-server or compatible)
    stt_endpoint: str = ""  # Custom STT base_url (e.g. http://whisper:8200/v1); empty = OpenAI cloud

    # Reasoning options (for models that support extended thinking)
    reasoning_effort: Optional[str] = None  # "low", "medium", "high" — None = provider default
    reasoning_summary: Optional[str] = None  # "auto", "concise", "detailed" — None = omit

    # Provider Optimization Layers
    enable_conversation_persistence: bool = True  # Keep conversation history across events (OpenAI)
    enable_context_pruning: bool = True  # Auto-prune long conversations to stay within context window

    @model_validator(mode="after")
    def _resolve_backward_compat(self) -> "Settings":
        """Resolve backward-compat aliases.

        ``FORCE_PROXY_LLM=true`` → ``llm_provider="proxy"`` (if llm_provider not set).
        ``FORCE_LOCAL_WHISPER=true`` → ``stt_method="local"`` (if stt_method not set).
        """
        if self.llm_provider is None and self.force_proxy_llm:
            self.llm_provider = "proxy"
        if self.stt_method is None and self.force_local_whisper:
            self.stt_method = "local"
        return self


# Global settings instance
settings = Settings()

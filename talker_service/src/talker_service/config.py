"""Service configuration using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """TALKER Service configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
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
    
    # Proxy settings (for model_method = 3)
    force_proxy_llm: bool = False
    proxy_endpoint: str = "http://127.0.0.1:8000/v1/chat/completions"
    proxy_api_key: str = "VerysecretKey"
    proxy_model: str = ""
    
    # State Query Settings
    state_query_timeout: float = 30.0  # seconds
    
    # TTS Settings
    tts_enabled: bool = False  # Enable in-engine TTS audio generation
    voices_dir: Path = Path("./voices")  # Directory containing .safetensors voice files (flat layout)


# Global settings instance
settings = Settings()

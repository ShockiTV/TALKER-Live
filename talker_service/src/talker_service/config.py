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
    
    # ZMQ Settings
    lua_pub_endpoint: str = "tcp://127.0.0.1:5555"  # Lua PUB -> Python SUB
    service_pub_endpoint: str = "tcp://*:5556"     # Python PUB -> Lua SUB
    
    # FastAPI Settings
    http_host: str = "127.0.0.1"
    http_port: int = 8080
    
    # Logging
    log_level: str = "INFO"
    log_file: Path = Path("logs/talker_service.log")
    
    # LLM Settings
    default_llm_provider: str = "openai"  # openai, openrouter, ollama, proxy
    llm_timeout: float = 60.0  # seconds
    
    # Proxy settings (for model_method = 3)
    proxy_endpoint: str = "http://127.0.0.1:8000/v1/chat/completions"
    proxy_api_key: str = "VerysecretKey"
    
    # State Query Settings
    state_query_timeout: float = 30.0  # seconds


# Global settings instance
settings = Settings()

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
    lua_pub_endpoint: str = "tcp://127.0.0.1:5555"
    # service_pub_endpoint: str = "tcp://*:5556"  # Phase 2
    
    # FastAPI Settings
    http_host: str = "127.0.0.1"
    http_port: int = 8080
    
    # Logging
    log_level: str = "INFO"
    log_file: Path = Path("logs/talker_service.log")


# Global settings instance
settings = Settings()

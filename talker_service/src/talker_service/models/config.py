"""MCM configuration mirror schema."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class MCMConfig(BaseModel):
    """Mirror of MCM settings from the game.
    
    This model defines expected fields with defaults.
    Unknown fields are allowed to support future MCM additions.
    """
    
    model_config = {"extra": "allow"}
    
    # Model settings
    model_method: int = 0  # 0=GPT, 1=OpenRouter, 2=Ollama, 3=Proxy
    api_key: str = ""
    model_name: str = ""
    model_name_fast: str = ""  # Fast model for speaker selection
    
    # Behavior settings
    witness_distance: int = 30
    
    # ZMQ settings
    zmq_port: int = 5555
    zmq_heartbeat_interval: int = 5
    
    # TTS settings
    tts_volume_boost: float = 8.0  # Volume multiplier for TTS audio (1.0-15.0)

    # Timeout settings (Phase 2)
    llm_timeout: int = 60  # LLM request timeout in seconds
    state_query_timeout: int = 30  # State query timeout in seconds
    
    # Other common settings
    action_descriptions: bool = False
    female_gender: bool = False
    language: str = "any"
    time_gap: int = 12  # Hours for time gap injection
    
    @classmethod
    def from_lua_payload(cls, payload: dict[str, Any]) -> "MCMConfig":
        """Create config from Lua payload, handling type coercion.
        
        Lua sends config as {config: {key: value, ...}} from get_all_config().
        Field name mapping: ai_model_method -> model_method
        """
        # Extract from nested 'config' key if present
        if "config" in payload and isinstance(payload["config"], dict):
            raw_config = payload["config"]
        else:
            raw_config = payload
        
        # Map Lua field names to Python field names
        field_mapping = {
            "ai_model_method": "model_method",
            "custom_ai_model": "model_name",
            "custom_ai_model_fast": "model_name_fast",
        }
        
        processed = {}
        for key, value in raw_config.items():
            # Apply field name mapping
            mapped_key = field_mapping.get(key, key)
            
            # Convert 0/1 to bool for boolean fields
            if mapped_key in ("zmq_enabled", "action_descriptions", "female_gender", "python_ai_enabled"):
                processed[mapped_key] = bool(value) if isinstance(value, int) else value
            else:
                processed[mapped_key] = value
        
        return cls(**processed)

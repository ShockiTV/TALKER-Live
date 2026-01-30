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
    idle_conversation_cooldown: int = 300
    base_dialogue_chance: float = 0.25
    
    # Feature flags (triggers)
    enable_trigger_death: int = 0
    enable_trigger_injury: int = 0
    enable_trigger_artifact_pickup: int = 0
    enable_trigger_artifact_use: int = 0
    enable_trigger_artifact_equip: int = 0
    enable_trigger_callout: int = 0
    enable_trigger_emission: int = 0
    enable_trigger_map_transition: int = 0
    enable_trigger_sleep: int = 0
    enable_trigger_task: int = 0
    enable_trigger_taunt: int = 0
    enable_trigger_weapon_jam: int = 0
    enable_trigger_reload: int = 0
    enable_trigger_anomalies: int = 0
    enable_trigger_idle_conversation: int = 0
    
    # ZMQ settings (Phase 1)
    zmq_enabled: bool = True
    zmq_port: int = 5555
    
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

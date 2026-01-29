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
    
    # Other common settings
    action_descriptions: bool = False
    female_gender: bool = False
    language: str = "any"
    time_gap: int = 12  # Hours for time gap injection
    
    @classmethod
    def from_lua_payload(cls, payload: dict[str, Any]) -> "MCMConfig":
        """Create config from Lua payload, handling type coercion."""
        # Lua may send booleans as 0/1 integers
        processed = {}
        for key, value in payload.items():
            if key in ("zmq_enabled", "action_descriptions", "female_gender"):
                # Convert 0/1 to bool
                processed[key] = bool(value) if isinstance(value, int) else value
            else:
                processed[key] = value
        return cls(**processed)

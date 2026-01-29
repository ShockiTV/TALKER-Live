"""Pytest configuration and fixtures for TALKER Service tests."""

import pytest


@pytest.fixture
def sample_game_event_payload():
    """Sample game event payload as sent from Lua."""
    return {
        "event": {
            "type": "DEATH",
            "context": {
                "victim": {
                    "game_id": "12345",
                    "name": "Bandit",
                    "faction": "Bandit",
                    "experience": "Experienced",
                    "reputation": "Neutral",
                    "personality": "aggressive",
                    "backstory": None,
                    "weapon": "AK-74",
                    "visual_faction": None,
                },
                "killer": {
                    "game_id": "0",
                    "name": "Player",
                    "faction": "stalker",
                    "experience": "Veteran",
                    "reputation": "Good",
                    "personality": None,
                    "backstory": None,
                    "weapon": "VSS Vintorez",
                    "visual_faction": None,
                },
            },
            "game_time_ms": 123456789,
            "world_context": "In Cordon at morning during clear weather.",
            "witnesses": [
                {
                    "game_id": "0",
                    "name": "Player",
                    "faction": "stalker",
                    "experience": "Veteran",
                    "reputation": "Good",
                    "personality": None,
                    "backstory": None,
                    "weapon": "VSS Vintorez",
                    "visual_faction": None,
                },
                {
                    "game_id": "67890",
                    "name": "Wolf",
                    "faction": "stalker",
                    "experience": "Expert",
                    "reputation": "Great",
                    "personality": "friendly",
                    "backstory": "Veteran of many Zone expeditions",
                    "weapon": "AK-74",
                    "visual_faction": None,
                },
            ],
            "flags": {},
        },
        "is_important": True,
    }


@pytest.fixture
def sample_config_payload():
    """Sample config sync payload as sent from Lua."""
    return {
        "model_method": 1,
        "model_name": "gpt-4",
        "fast_model_name": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 150,
        "zmq_enabled": True,
        "zmq_port": 5555,
        "zmq_heartbeat_interval": 5,
        "language": "English",
        "player_speaks": True,
        "action_descriptions": False,
    }


@pytest.fixture
def sample_heartbeat_payload():
    """Sample heartbeat payload."""
    return {
        "game_time_ms": 123456789,
        "timestamp": "2026-01-29T12:00:00",
    }

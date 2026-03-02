"""Tests for SceneContext faction fields in state/models.py."""

import pytest

from talker_service.state.models import SceneContext


class TestSceneContextFactionFields:
    """Tests for SceneContext faction_standings and player_goodwill fields."""

    def test_from_dict_with_faction_standings(self):
        data = {
            "loc": "l01_escape",
            "faction_standings": {"dolg_freedom": -1500, "army_stalker": 0},
        }
        ctx = SceneContext.from_dict(data)
        assert ctx.faction_standings == {"dolg_freedom": -1500, "army_stalker": 0}

    def test_from_dict_with_player_goodwill(self):
        data = {
            "loc": "l01_escape",
            "player_goodwill": {"dolg": 1200, "freedom": -300},
        }
        ctx = SceneContext.from_dict(data)
        assert ctx.player_goodwill == {"dolg": 1200, "freedom": -300}

    def test_from_dict_without_faction_data(self):
        data = {"loc": "l01_escape"}
        ctx = SceneContext.from_dict(data)
        assert ctx.faction_standings is None
        assert ctx.player_goodwill is None

    def test_from_dict_with_both_faction_fields(self):
        data = {
            "loc": "l03_agroprom",
            "weather": "rain",
            "faction_standings": {"dolg_freedom": -1500},
            "player_goodwill": {"dolg": 1200},
        }
        ctx = SceneContext.from_dict(data)
        assert ctx.faction_standings == {"dolg_freedom": -1500}
        assert ctx.player_goodwill == {"dolg": 1200}
        assert ctx.loc == "l03_agroprom"
        assert ctx.weather == "rain"

    def test_default_values(self):
        ctx = SceneContext()
        assert ctx.faction_standings is None
        assert ctx.player_goodwill is None

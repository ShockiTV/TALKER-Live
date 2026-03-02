"""Tests for dynamic faction relation labels and formatters in prompts/factions.py."""

import pytest

from talker_service.prompts.factions import (
    label_faction_relation,
    label_goodwill,
    format_faction_standings,
    format_player_goodwill,
    COMPANION_FACTION_TENSION_NOTE,
    FACTION_RELATION_THRESHOLDS,
    GOODWILL_TIERS,
)


# ---------------------------------------------------------------------------
# label_faction_relation
# ---------------------------------------------------------------------------

class TestLabelFactionRelation:
    """Tests for label_faction_relation() boundary values."""

    def test_allied_above_threshold(self):
        assert label_faction_relation(1500) == "Allied"

    def test_allied_at_boundary(self):
        assert label_faction_relation(1000) == "Allied"

    def test_hostile_below_threshold(self):
        assert label_faction_relation(-1500) == "Hostile"

    def test_hostile_at_boundary(self):
        assert label_faction_relation(-1000) == "Hostile"

    def test_neutral_positive(self):
        assert label_faction_relation(999) == "Neutral"

    def test_neutral_negative(self):
        assert label_faction_relation(-999) == "Neutral"

    def test_neutral_zero(self):
        assert label_faction_relation(0) == "Neutral"


# ---------------------------------------------------------------------------
# label_goodwill
# ---------------------------------------------------------------------------

class TestLabelGoodwill:
    """Tests for label_goodwill() — all PDA tier boundaries."""

    def test_excellent(self):
        assert label_goodwill(2500) == "Excellent"

    def test_excellent_at_boundary(self):
        assert label_goodwill(2000) == "Excellent"

    def test_brilliant(self):
        assert label_goodwill(1500) == "Brilliant"

    def test_brilliant_just_below_excellent(self):
        assert label_goodwill(1999) == "Brilliant"

    def test_great(self):
        assert label_goodwill(1000) == "Great"

    def test_good(self):
        assert label_goodwill(500) == "Good"

    def test_good_just_below_great(self):
        assert label_goodwill(999) == "Good"

    def test_neutral_zero(self):
        assert label_goodwill(0) == "Neutral"

    def test_neutral_positive(self):
        assert label_goodwill(499) == "Neutral"

    def test_neutral_negative(self):
        assert label_goodwill(-499) == "Neutral"

    def test_bad(self):
        assert label_goodwill(-500) == "Bad"

    def test_bad_just_above_awful(self):
        assert label_goodwill(-999) == "Bad"

    def test_awful(self):
        assert label_goodwill(-1000) == "Awful"

    def test_dreary(self):
        assert label_goodwill(-1500) == "Dreary"

    def test_terrible(self):
        assert label_goodwill(-2500) == "Terrible"

    def test_terrible_at_boundary(self):
        assert label_goodwill(-2000) == "Terrible"

    def test_dreary_just_above_terrible(self):
        assert label_goodwill(-1999) == "Dreary"


# ---------------------------------------------------------------------------
# format_faction_standings
# ---------------------------------------------------------------------------

class TestFormatFactionStandings:
    """Tests for format_faction_standings()."""

    def test_full_format(self):
        standings = {"dolg_freedom": -1500, "army_stalker": 0}
        result = format_faction_standings(standings)
        assert "Hostile" in result
        assert "Neutral" in result
        # Uses ↔ separator
        assert "\u2194" in result

    def test_allied_label(self):
        standings = {"army_dolg": 1200}
        result = format_faction_standings(standings)
        assert "Allied" in result

    def test_filter_relevant_factions(self):
        standings = {
            "dolg_freedom": -1500,
            "army_stalker": 0,
            "bandit_monolith": -1000,
        }
        result = format_faction_standings(standings, relevant_factions={"dolg", "freedom"})
        assert "Duty" in result or "Freedom" in result
        # army_stalker should not appear (neither is relevant)
        lines = result.strip().split("\n")
        for line in lines:
            assert "Army" not in line or "Duty" in line or "Freedom" in line

    def test_empty_standings(self):
        result = format_faction_standings({})
        assert result == ""

    def test_none_standings(self):
        result = format_faction_standings(None)
        assert result == ""

    def test_display_names_used(self):
        standings = {"dolg_freedom": -1500}
        result = format_faction_standings(standings)
        assert "Duty" in result
        assert "Freedom" in result


# ---------------------------------------------------------------------------
# format_player_goodwill
# ---------------------------------------------------------------------------

class TestFormatPlayerGoodwill:
    """Tests for format_player_goodwill()."""

    def test_full_format(self):
        goodwill = {"dolg": 1200, "freedom": -300}
        result = format_player_goodwill(goodwill)
        assert "Duty: +1200 (Great)" in result
        assert "Freedom: -300 (Neutral)" in result

    def test_filter_relevant_factions(self):
        goodwill = {"dolg": 1200, "freedom": -300, "bandit": -800}
        result = format_player_goodwill(goodwill, relevant_factions={"dolg"})
        assert "Duty" in result
        assert "Freedom" not in result
        assert "Bandit" not in result

    def test_empty_goodwill(self):
        result = format_player_goodwill({})
        assert result == ""

    def test_none_goodwill(self):
        result = format_player_goodwill(None)
        assert result == ""

    def test_positive_sign(self):
        goodwill = {"dolg": 500}
        result = format_player_goodwill(goodwill)
        assert "+500" in result

    def test_negative_sign(self):
        goodwill = {"freedom": -500}
        result = format_player_goodwill(goodwill)
        assert "-500" in result

    def test_zero_goodwill(self):
        goodwill = {"stalker": 0}
        result = format_player_goodwill(goodwill)
        assert "+0" in result
        assert "Neutral" in result


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    """Tests for exported constants."""

    def test_companion_note_content(self):
        assert "Faction hostilities" in COMPANION_FACTION_TENSION_NOTE
        assert "attitude and dialogue" in COMPANION_FACTION_TENSION_NOTE

    def test_faction_relation_thresholds(self):
        assert FACTION_RELATION_THRESHOLDS["Allied"] == 1000
        assert FACTION_RELATION_THRESHOLDS["Hostile"] == -1000

    def test_goodwill_tiers_ordered(self):
        # Thresholds should be in descending order
        prev = None
        for threshold, _ in GOODWILL_TIERS:
            if prev is not None:
                assert threshold < prev, f"Tiers not descending: {threshold} >= {prev}"
            prev = threshold

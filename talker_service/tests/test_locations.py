"""Tests for locations module - location name and description resolution."""

import pytest
from texts.locations import (
    get_location_name,
    get_location_description,
    format_description,
    LOCATION_NAMES,
    LOCATION_DESCRIPTIONS,
)


class TestGetLocationName:
    """Tests for get_location_name function."""

    def test_known_location(self):
        """Test resolving a known location ID."""
        assert get_location_name("l01_escape") == "Cordon"
        assert get_location_name("l02_garbage") == "Garbage"
        assert get_location_name("jupiter") == "Jupiter"

    def test_unknown_location_returns_original(self):
        """Test that unknown location ID returns the original ID."""
        assert get_location_name("unknown_zone") == "unknown_zone"

    def test_empty_returns_empty(self):
        """Test that empty string returns empty string."""
        assert get_location_name("") == ""

    def test_case_insensitive(self):
        """Test that lookup is case-insensitive."""
        assert get_location_name("L01_ESCAPE") == "Cordon"


class TestGetLocationDescription:
    """Tests for get_location_description function."""

    def test_known_location_returns_description(self):
        """Test getting description for a known location."""
        desc = get_location_description("l01_escape")
        assert "Cordon" in desc
        assert "Zone" in desc
        # Faction placeholders should be resolved
        assert "%stalker%" not in desc
        assert "Loners" in desc  # %stalker% -> "Loners"

    def test_unknown_location_returns_empty(self):
        """Test that unknown location ID returns empty string."""
        assert get_location_description("unknown_zone") == ""

    def test_empty_returns_empty(self):
        """Test that empty string returns empty string."""
        assert get_location_description("") == ""

    def test_case_insensitive(self):
        """Test that lookup is case-insensitive."""
        desc = get_location_description("L01_ESCAPE")
        assert "Cordon" in desc

    def test_placeholder_resolution(self):
        """Test that faction placeholders are resolved in descriptions."""
        desc = get_location_description("l05_bar")
        # %dolg% should become "Duty"
        assert "Duty" in desc
        assert "%dolg%" not in desc


class TestFormatDescription:
    """Tests for format_description function."""

    def test_single_placeholder(self):
        """Test resolving a single faction placeholder."""
        text = "This area is controlled by %stalker%."
        result = format_description(text)
        assert result == "This area is controlled by Loners."

    def test_multiple_placeholders(self):
        """Test resolving multiple faction placeholders."""
        text = "%dolg% and %freedom% are enemies."
        result = format_description(text)
        assert result == "Duty and Freedom are enemies."

    def test_unknown_placeholder_unchanged(self):
        """Test that unknown placeholders are kept as-is (without %)."""
        text = "The %unknown_faction% lives here."
        result = format_description(text)
        assert result == "The unknown_faction lives here."

    def test_no_placeholders(self):
        """Test text without placeholders is unchanged."""
        text = "A dangerous area with many mutants."
        result = format_description(text)
        assert result == "A dangerous area with many mutants."

    def test_empty_string(self):
        """Test empty string returns empty string."""
        assert format_description("") == ""

    def test_all_factions(self):
        """Test all known faction placeholders resolve correctly."""
        # Test a few key factions
        assert "Loners" in format_description("%stalker%")
        assert "Duty" in format_description("%dolg%")
        assert "Freedom" in format_description("%freedom%")
        assert "Bandits" in format_description("%bandit%")
        assert "Mercenaries" in format_description("%killer%")
        assert "Monolith" in format_description("%monolith%")

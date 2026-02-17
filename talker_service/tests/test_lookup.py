"""Tests for lookup module - personality and backstory ID resolution."""

import pytest
from talker_service.prompts.lookup import resolve_personality, resolve_backstory, resolve_faction_name


class TestResolvePersonality:
    """Tests for resolve_personality function."""
    
    def test_resolve_valid_faction_id(self):
        """Test resolving a valid faction-based personality ID."""
        result = resolve_personality("bandit.1")
        assert result == "morose"
    
    def test_resolve_another_faction_id(self):
        """Test resolving personality ID from another faction."""
        result = resolve_personality("ecolog.1")
        assert result == "morose"  # First entry in ecolog module
    
    def test_resolve_unique_character(self):
        """Test resolving a unique character personality ID."""
        result = resolve_personality("unique.devushka")
        assert "loyal" in result.lower()  # Hip is described as loyal
    
    def test_resolve_nonexistent_returns_empty(self):
        """Test that nonexistent ID returns empty string."""
        result = resolve_personality("nonexistent.999")
        assert result == ""
    
    def test_resolve_empty_returns_empty(self):
        """Test that empty ID returns empty string."""
        result = resolve_personality("")
        assert result == ""
    
    def test_resolve_none_returns_empty(self):
        """Test that None returns empty string."""
        result = resolve_personality(None)
        assert result == ""
    
    def test_resolve_invalid_format_returns_empty(self):
        """Test that invalid format (no dot) returns empty string."""
        result = resolve_personality("morose and aggressive")
        assert result == ""
    
    def test_resolve_generic_fallback(self):
        """Test resolving a generic personality ID."""
        result = resolve_personality("generic.1")
        assert result != ""  # Should find something in generic module


class TestResolveBackstory:
    """Tests for resolve_backstory function."""
    
    def test_resolve_empty_returns_empty(self):
        """Test that empty ID returns empty string."""
        result = resolve_backstory("")
        assert result == ""
    
    def test_resolve_none_returns_empty(self):
        """Test that None returns empty string."""
        result = resolve_backstory(None)
        assert result == ""
    
    def test_resolve_invalid_format_returns_empty(self):
        """Test that invalid format (no dot) returns empty string."""
        result = resolve_backstory("A former soldier who came to the Zone...")
        assert result == ""
    
    def test_resolve_unique_character(self):
        """Test resolving unique character backstory."""
        # Sidorovich's tech name is esc_m_trader
        result = resolve_backstory("unique.esc_m_trader")
        assert result != ""
        assert "information broker" in result.lower() or "sidorovich" in result.lower()
    
    def test_resolve_generic_backstory(self):
        """Test resolving generic backstory ID."""
        result = resolve_backstory("generic.1")
        assert result != ""
        assert "PTSD" in result or "friend" in result.lower()  # First generic story is about PTSD
    
    def test_resolve_bandit_backstory(self):
        """Test resolving bandit faction backstory."""
        result = resolve_backstory("bandit.1")
        assert result != ""
    
    def test_resolve_duty_backstory(self):
        """Test resolving Duty faction backstory."""
        result = resolve_backstory("duty.1")
        assert result != ""
    
    def test_resolve_freedom_backstory(self):
        """Test resolving Freedom faction backstory."""
        result = resolve_backstory("freedom.1")
        assert result != ""
    
    def test_resolve_nonexistent_returns_empty(self):
        """Test that nonexistent ID returns empty string."""
        result = resolve_backstory("nonexistent.999")
        assert result == ""
    
    def test_resolve_unique_with_complex_name(self):
        """Test resolving unique character with complex tech name."""
        # Wolf's tech name
        result = resolve_backstory("unique.esc_2_12_stalker_wolf")
        assert result != ""
        assert "rookie village" in result.lower() or "security" in result.lower()


class TestResolveFactionName:
    """Tests for resolve_faction_name function."""
    
    def test_resolve_valid_faction_id(self):
        """Test resolving a valid faction ID."""
        result = resolve_faction_name("dolg")
        assert result == "Duty"
    
    def test_resolve_stalker_to_loner(self):
        """Test that 'stalker' resolves to 'Loner'."""
        result = resolve_faction_name("stalker")
        assert result == "Loner"
    
    def test_resolve_killer_to_mercenary(self):
        """Test that 'killer' resolves to 'Mercenary'."""
        result = resolve_faction_name("killer")
        assert result == "Mercenary"
    
    def test_resolve_csky_to_clear_sky(self):
        """Test that 'csky' resolves to 'Clear Sky'."""
        result = resolve_faction_name("csky")
        assert result == "Clear Sky"
    
    def test_resolve_unknown_returns_raw(self):
        """Test that unknown faction ID returns the raw ID."""
        result = resolve_faction_name("unknownfaction")
        assert result == "unknownfaction"
    
    def test_resolve_empty_returns_empty(self):
        """Test that empty string returns empty string."""
        result = resolve_faction_name("")
        assert result == ""
    
    def test_resolve_none_returns_none(self):
        """Test that None returns None."""
        result = resolve_faction_name(None)
        assert result is None
    
    def test_resolve_monster_faction(self):
        """Test resolving monster faction."""
        result = resolve_faction_name("monster")
        assert result == "Monster"
    
    def test_resolve_zombied_faction(self):
        """Test resolving zombied faction."""
        result = resolve_faction_name("zombied")
        assert result == "Zombied"

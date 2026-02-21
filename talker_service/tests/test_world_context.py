"""Tests for world_context module - world state context builders."""

import pytest
from dataclasses import dataclass

# Import the module under test
from talker_service.prompts.world_context import (
    _get_characters,
    _get_leaders,
    _get_important,
    _get_notable,
    get_all_story_ids,
    _extract_story_ids_from_events,
    _is_notable_relevant,
    build_dead_leaders_context,
    build_dead_important_context,
    build_info_portions_context,
    build_regional_context,
    build_world_context,
)


# Mock SceneContext for testing
@dataclass
class MockSceneContext:
    """Mock SceneContext for testing."""
    loc: str = ""
    poi: str = ""
    time: dict = None
    weather: str = ""
    emission: bool = False
    psy_storm: bool = False
    sheltering: bool = False
    campfire: bool = False
    brain_scorcher_disabled: bool = False
    miracle_machine_disabled: bool = False

    def __post_init__(self):
        if self.time is None:
            self.time = {"h": 12, "m": 0}


class TestGetCharacters:
    """Tests for character retrieval functions."""
    
    def test_get_characters_returns_list(self):
        """Test that _get_characters returns a non-empty list."""
        result = _get_characters()
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_get_leaders_returns_leaders_only(self):
        """Test that _get_leaders only returns leader role characters."""
        leaders = _get_leaders()
        assert len(leaders) > 0
        for leader in leaders:
            assert leader.get("role") == "leader"
    
    def test_get_important_returns_important_only(self):
        """Test that _get_important only returns important role characters."""
        important = _get_important()
        assert len(important) > 0
        for char in important:
            assert char.get("role") == "important"
    
    def test_get_notable_returns_notable_only(self):
        """Test that _get_notable only returns notable role characters."""
        notable = _get_notable()
        assert len(notable) > 0
        for char in notable:
            assert char.get("role") == "notable"
    
    def testget_all_story_ids_returns_flat_list(self):
        """Test that get_all_story_ids returns flattened list of IDs."""
        ids = get_all_story_ids()
        assert isinstance(ids, list)
        assert len(ids) > 0
        # All IDs should be strings
        for id_ in ids:
            assert isinstance(id_, str)


class TestBuildDeadLeadersContext:
    """Tests for build_dead_leaders_context function."""
    
    def test_no_dead_leaders_returns_empty(self):
        """Test that no dead leaders returns empty string."""
        # All leaders alive
        all_ids = get_all_story_ids()
        alive_status = {id_: True for id_ in all_ids}
        
        result = build_dead_leaders_context(alive_status)
        assert result == ""
    
    def test_dead_leader_included_in_output(self):
        """Test that dead leaders appear in output."""
        # Get a real leader ID
        leaders = _get_leaders()
        assert len(leaders) > 0
        
        # Mark first leader as dead
        leader = leaders[0]
        leader_id = leader["ids"][0]
        alive_status = {leader_id: False}
        
        result = build_dead_leaders_context(alive_status)
        
        # Should contain the leader's name
        assert leader["name"] in result
        assert "is dead" in result
    
    def test_multiple_dead_leaders(self):
        """Test that multiple dead leaders all appear."""
        leaders = _get_leaders()
        assert len(leaders) >= 2
        
        # Mark first two leaders as dead
        alive_status = {}
        for leader in leaders[:2]:
            for id_ in leader["ids"]:
                alive_status[id_] = False
        
        result = build_dead_leaders_context(alive_status)
        
        # Both should appear with "is dead"
        assert leaders[0]["name"] in result
        assert leaders[1]["name"] in result
        assert result.count("is dead") == 2


class TestExtractStoryIdsFromEvents:
    """Tests for _extract_story_ids_from_events helper function."""
    
    def test_extracts_from_witnesses(self):
        """Test extraction from event witnesses with story_id."""
        @dataclass
        class MockCharacter:
            story_id: str | None = None
        
        @dataclass
        class MockEvent:
            witnesses: list = None
            context: dict = None
            
            def __post_init__(self):
                if self.witnesses is None:
                    self.witnesses = []
                if self.context is None:
                    self.context = {}
        
        event = MockEvent(
            witnesses=[MockCharacter(story_id="esc_2_12_stalker_wolf")],
            context={}
        )
        
        result = _extract_story_ids_from_events([event])
        assert "esc_2_12_stalker_wolf" in result
    
    def test_extracts_from_context_actor(self):
        """Test extraction from context actor field."""
        @dataclass
        class MockEvent:
            witnesses: list = None
            context: dict = None
            
            def __post_init__(self):
                if self.witnesses is None:
                    self.witnesses = []
                if self.context is None:
                    self.context = {}
        
        event = MockEvent(
            witnesses=[],
            context={"actor": {"story_id": "bar_dolg_leader", "name": "Voronin"}}
        )
        
        result = _extract_story_ids_from_events([event])
        assert "bar_dolg_leader" in result
    
    def test_extracts_from_context_victim(self):
        """Test extraction from context victim field."""
        @dataclass
        class MockEvent:
            witnesses: list = None
            context: dict = None
            
            def __post_init__(self):
                if self.witnesses is None:
                    self.witnesses = []
                if self.context is None:
                    self.context = {}
        
        event = MockEvent(
            witnesses=[],
            context={"victim": {"story_id": "esc_2_12_stalker_wolf"}}
        )
        
        result = _extract_story_ids_from_events([event])
        assert "esc_2_12_stalker_wolf" in result
    
    def test_skips_none_story_ids(self):
        """Test that None story_ids are skipped."""
        @dataclass
        class MockCharacter:
            story_id: str | None = None
        
        @dataclass
        class MockEvent:
            witnesses: list = None
            context: dict = None
            
            def __post_init__(self):
                if self.witnesses is None:
                    self.witnesses = []
                if self.context is None:
                    self.context = {}
        
        event = MockEvent(
            witnesses=[MockCharacter(story_id=None)],
            context={}
        )
        
        result = _extract_story_ids_from_events([event])
        assert len(result) == 0


class TestIsNotableRelevant:
    """Tests for _is_notable_relevant helper function."""
    
    def test_story_id_in_witnesses_returns_true(self):
        """Criterion 1: Character's story_id in event witnesses."""
        @dataclass
        class MockCharacter:
            story_id: str | None = None
        
        @dataclass
        class MockEvent:
            witnesses: list = None
            context: dict = None
            
            def __post_init__(self):
                if self.witnesses is None:
                    self.witnesses = []
                if self.context is None:
                    self.context = {}
        
        char = {"name": "Wolf", "area": "l01_escape", "ids": ["esc_2_12_stalker_wolf"]}
        events = [MockEvent(witnesses=[MockCharacter(story_id="esc_2_12_stalker_wolf")])]
        
        result = _is_notable_relevant(char, current_area="", recent_events=events)
        assert result is True
    
    def test_story_id_in_context_returns_true(self):
        """Criterion 1: Character's story_id in event context."""
        @dataclass
        class MockEvent:
            witnesses: list = None
            context: dict = None
            
            def __post_init__(self):
                if self.witnesses is None:
                    self.witnesses = []
                if self.context is None:
                    self.context = {}
        
        char = {"name": "Voronin", "ids": ["bar_dolg_leader"]}
        events = [MockEvent(context={"speaker": {"story_id": "bar_dolg_leader"}})]
        
        result = _is_notable_relevant(char, current_area="", recent_events=events)
        assert result is True
    
    def test_current_location_match_returns_true(self):
        """Criterion 2: Current location matches character's area."""
        char = {"name": "Wolf", "area": "l01_escape", "ids": ["esc_2_12_stalker_wolf"]}
        
        result = _is_notable_relevant(char, current_area="l01_escape", recent_events=None)
        assert result is True
    
    def test_current_location_case_insensitive(self):
        """Criterion 2: Location matching is case-insensitive."""
        char = {"name": "Wolf", "area": "l01_escape", "ids": ["esc_2_12_stalker_wolf"]}
        
        result = _is_notable_relevant(char, current_area="L01_ESCAPE", recent_events=None)
        assert result is True
    
    def test_current_location_matches_areas_list(self):
        """Criterion 2: Current location matches any area in 'areas' list."""
        char = {"name": "Degtyarev", "areas": ["l10_radar", "l11_pripyat"], "ids": ["army_degtyarev"]}
        
        result = _is_notable_relevant(char, current_area="l11_pripyat", recent_events=None)
        assert result is True
    
    def test_no_criteria_match_returns_false(self):
        """No criteria match returns False."""
        @dataclass
        class MockCharacter:
            story_id: str | None = None
        
        @dataclass
        class MockEvent:
            witnesses: list = None
            context: dict = None
            
            def __post_init__(self):
                if self.witnesses is None:
                    self.witnesses = []
                if self.context is None:
                    self.context = {}
        
        char = {"name": "Wolf", "area": "l01_escape", "ids": ["esc_2_12_stalker_wolf"]}
        events = [MockEvent(witnesses=[MockCharacter(story_id="some_other_id")])]
        
        result = _is_notable_relevant(char, current_area="l02_garbage", recent_events=events)
        assert result is False
    
    def test_no_events_and_no_location_returns_false(self):
        """No events and no current location returns False."""
        char = {"name": "Wolf", "area": "l01_escape", "ids": ["esc_2_12_stalker_wolf"]}
        
        result = _is_notable_relevant(char, current_area="", recent_events=None)
        assert result is False
    
    def test_empty_events_list_returns_false_without_location(self):
        """Empty events with no location match returns False."""
        char = {"name": "Wolf", "area": "l01_escape", "ids": ["esc_2_12_stalker_wolf"]}
        
        result = _is_notable_relevant(char, current_area="l02_garbage", recent_events=[])
        assert result is False


class TestBuildDeadImportantContext:
    """Tests for build_dead_important_context function."""
    
    def test_no_dead_important_returns_empty(self):
        """Test that no dead important characters returns empty string."""
        all_ids = get_all_story_ids()
        alive_status = {id_: True for id_ in all_ids}
        
        result = build_dead_important_context(alive_status)
        assert result == ""
    
    def test_dead_important_included(self):
        """Test that dead important characters appear in output."""
        important = _get_important()
        if not important:
            pytest.skip("No important characters defined")
        
        # Mark first important character as dead
        char = important[0]
        alive_status = {char["ids"][0]: False}
        
        result = build_dead_important_context(alive_status)
        
        assert char["name"] in result
        assert "is dead" in result
    
    def test_notable_filtered_by_area(self):
        """Test that notable characters are filtered by area."""
        notable = _get_notable()
        if not notable:
            pytest.skip("No notable characters defined")
        
        # Find a notable with an area defined
        area_notable = None
        for char in notable:
            if char.get("area"):
                area_notable = char
                break
        
        if not area_notable:
            pytest.skip("No notable characters with area defined")
        
        # Mark as dead
        alive_status = {area_notable["ids"][0]: False}
        
        # Without matching area - should not appear
        result_wrong_area = build_dead_important_context(
            alive_status, current_area="wrong_area"
        )
        assert area_notable["name"] not in result_wrong_area
        
        # With matching area - should appear
        result_right_area = build_dead_important_context(
            alive_status, current_area=area_notable["area"]
        )
        assert area_notable["name"] in result_right_area
    
    def test_notable_filtered_by_name_in_events(self):
        """Test that notable characters appear if their name is in recent events."""
        notable = _get_notable()
        if not notable:
            pytest.skip("No notable characters defined")
        
        # Find a notable with an area defined
        area_notable = None
        for char in notable:
            if char.get("area"):
                area_notable = char
                break
        
        if not area_notable:
            pytest.skip("No notable characters with area defined")
        
        # Mark as dead
        alive_status = {area_notable["ids"][0]: False}
        
        # Without story_id in events and wrong area - should not appear
        @dataclass
        class MockCharacter:
            story_id: str | None = None
        
        @dataclass
        class MockEvent:
            witnesses: list = None
            context: dict = None
            
            def __post_init__(self):
                if self.witnesses is None:
                    self.witnesses = []
                if self.context is None:
                    self.context = {}
        
        events_unrelated = [MockEvent(witnesses=[MockCharacter(story_id="unrelated_id")])]
        result_no_match = build_dead_important_context(
            alive_status, current_area="wrong_area", recent_events=events_unrelated
        )
        assert area_notable["name"] not in result_no_match
        
        # With story_id in events (but wrong area) - should appear
        events_with_id = [MockEvent(witnesses=[MockCharacter(story_id=area_notable["ids"][0])])]
        result_name_match = build_dead_important_context(
            alive_status, current_area="wrong_area", recent_events=events_with_id
        )
        assert area_notable["name"] in result_name_match
    
    def test_notable_filtered_by_area_in_events(self):
        """Test that notable characters appear if player is in their area."""
        notable = _get_notable()
        if not notable:
            pytest.skip("No notable characters defined")
        
        # Find a notable with an area defined
        area_notable = None
        for char in notable:
            if char.get("area"):
                area_notable = char
                break
        
        if not area_notable:
            pytest.skip("No notable characters with area defined")
        
        # Mark as dead
        alive_status = {area_notable["ids"][0]: False}
        
        # With current area matching character's area - should appear
        result_area_match = build_dead_important_context(
            alive_status, current_area=area_notable['area'], recent_events=[]
        )
        assert area_notable["name"] in result_area_match


class TestBuildInfoPortionsContext:
    """Tests for build_info_portions_context function."""
    
    def test_nothing_disabled_returns_empty(self):
        """Test that no disabled installations returns empty string."""
        scene = MockSceneContext(
            brain_scorcher_disabled=False,
            miracle_machine_disabled=False,
        )
        
        result = build_info_portions_context(scene)
        assert result == ""
    
    def test_brain_scorcher_disabled_shows_message(self):
        """Test that disabled Brain Scorcher shows appropriate message."""
        scene = MockSceneContext(brain_scorcher_disabled=True)
        
        result = build_info_portions_context(scene)
        
        assert "Brain Scorcher" in result
        assert "disabled" in result.lower()
        assert "Radar" in result
    
    def test_miracle_machine_disabled_shows_message(self):
        """Test that disabled Miracle Machine shows appropriate message."""
        scene = MockSceneContext(miracle_machine_disabled=True)
        
        result = build_info_portions_context(scene)
        
        assert "Miracle Machine" in result
        assert "disabled" in result.lower()
        assert "Yantar" in result
    
    def test_both_disabled_shows_both_messages(self):
        """Test that both disabled shows both messages."""
        scene = MockSceneContext(
            brain_scorcher_disabled=True,
            miracle_machine_disabled=True,
        )
        
        result = build_info_portions_context(scene)
        
        assert "Brain Scorcher" in result
        assert "Miracle Machine" in result


class TestBuildRegionalContext:
    """Tests for build_regional_context function."""
    
    def test_cordon_shows_truce_info(self):
        """Test that Cordon shows Military/Loner truce info."""
        result = build_regional_context("l01_escape")
        
        assert "Military" in result
        assert "truce" in result.lower()
    
    def test_cordon_case_insensitive(self):
        """Test that area matching is case-insensitive."""
        result = build_regional_context("L01_Escape")
        
        assert "Military" in result
    
    def test_other_areas_return_empty(self):
        """Test that non-special areas return empty string."""
        result = build_regional_context("l03_agroprom")
        assert result == ""
    
    def test_empty_area_returns_empty(self):
        """Test that empty area returns empty string."""
        result = build_regional_context("")
        assert result == ""


class TestBuildWorldContext:
    """Tests for build_world_context aggregator function."""
    
    @pytest.mark.asyncio
    async def test_aggregates_all_sections(self):
        """Test that build_world_context combines all context sections."""
        # Return all characters as alive
        all_ids = get_all_story_ids()
        alive_status = {id_: True for id_ in all_ids}
        
        scene = MockSceneContext(
            loc="l01_escape",
            brain_scorcher_disabled=True,
        )
        
        result = await build_world_context(scene, alive_status=alive_status)
        
        # Should include Brain Scorcher (info portion) and Cordon truce (regional)
        assert "Brain Scorcher" in result
        assert "Military" in result
    
    @pytest.mark.asyncio
    async def test_empty_when_nothing_notable(self):
        """Test that empty context returns empty string."""
        # All alive, nothing disabled, no regional context
        all_ids = get_all_story_ids()
        alive_status = {id_: True for id_ in all_ids}
        
        scene = MockSceneContext(
            loc="l03_agroprom",
            brain_scorcher_disabled=False,
            miracle_machine_disabled=False,
        )
        
        result = await build_world_context(scene, alive_status=alive_status)
        
        assert result == ""
    
    @pytest.mark.asyncio
    async def test_includes_dead_leaders(self):
        """Test that dead leaders appear in aggregated context."""
        leaders = _get_leaders()
        if not leaders:
            pytest.skip("No leaders defined")
        
        # Mark first leader as dead
        leader_id = leaders[0]["ids"][0]
        all_ids = get_all_story_ids()
        alive_status = {id_: True for id_ in all_ids}
        alive_status[leader_id] = False
        
        scene = MockSceneContext(loc="l03_agroprom")
        
        result = await build_world_context(scene, alive_status=alive_status)
        
        assert leaders[0]["name"] in result
        assert "is dead" in result

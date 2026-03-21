"""Tests for BackgroundGenerator (one-shot LLM background generation)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from talker_service.dialogue.background_generator import BackgroundGenerator
from talker_service.state.batch import BatchResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_client():
    """Mock LLM client returning a valid background JSON array."""
    client = MagicMock()
    client.complete = AsyncMock(return_value=json.dumps([
        {
            "id": "npc_002",
            "background": {
                "traits": ["aggressive", "loyal"],
                "backstory": "A seasoned Duty enforcer.",
                "connections": ["npc_001"],
            },
        }
    ]))
    return client


@pytest.fixture
def mock_state_client():
    """Mock state query client."""
    client = MagicMock()
    client.execute_batch = AsyncMock()
    client.mutate_batch = AsyncMock(return_value=True)
    return client


@pytest.fixture
def sample_candidates():
    """Two candidates — one with background, one without."""
    return [
        {
            "game_id": "npc_001",
            "name": "Wolf",
            "faction": "dolg",
            "rank": 500,
        },
        {
            "game_id": "npc_002",
            "name": "Razor",
            "faction": "bandit",
            "rank": 300,
        },
    ]


# ---------------------------------------------------------------------------
# ensure_backgrounds
# ---------------------------------------------------------------------------


class TestEnsureBackgrounds:
    """Tests for the top-level ensure_backgrounds() orchestrator."""

    @pytest.mark.asyncio
    async def test_all_present_skips_generation(
        self, mock_llm_client, mock_state_client, sample_candidates,
    ):
        """When all candidates already have backgrounds, no LLM call is made."""
        mock_state_client.execute_batch.return_value = BatchResult({
            "bg_npc_001": {"ok": True, "data": {"traits": ["brave"], "backstory": "A veteran.", "connections": []}},
            "bg_npc_002": {"ok": True, "data": {"traits": ["sly"], "backstory": "A thief.", "connections": []}},
        })

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        result = await gen.ensure_backgrounds(sample_candidates)

        assert len(result) == 2
        assert result[0]["background"]["traits"] == ["brave"]
        assert result[1]["background"]["traits"] == ["sly"]
        mock_llm_client.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_missing_triggers_generation(
        self, mock_llm_client, mock_state_client, sample_candidates,
    ):
        """When some candidates lack backgrounds, LLM generates them."""
        # First call: batch read backgrounds — npc_002 missing
        mock_state_client.execute_batch.side_effect = [
            BatchResult({
                "bg_npc_001": {"ok": True, "data": {"traits": ["brave"], "backstory": "A veteran.", "connections": []}},
                "bg_npc_002": {"ok": True, "data": None},
            }),
            # Second call: character info for npc_002
            BatchResult({
                "ci_npc_002": {"ok": True, "data": {"character": {"gender": "male"}, "squad_members": []}},
            }),
        ]

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        result = await gen.ensure_backgrounds(sample_candidates)

        assert result[0]["background"]["traits"] == ["brave"]
        assert result[1]["background"]["traits"] == ["aggressive", "loyal"]
        mock_llm_client.complete.assert_called_once()
        mock_state_client.mutate_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_candidates_returns_empty(
        self, mock_llm_client, mock_state_client,
    ):
        """Empty candidate list is a no-op."""
        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        result = await gen.ensure_backgrounds([])

        assert result == []
        mock_llm_client.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_background_treated_as_missing(
        self, mock_llm_client, mock_state_client, sample_candidates,
    ):
        """Background dicts with 'error' key are treated as missing."""
        mock_state_client.execute_batch.side_effect = [
            BatchResult({
                "bg_npc_001": {"ok": True, "data": {"error": "not found"}},
                "bg_npc_002": {"ok": True, "data": {"traits": ["sly"], "backstory": "A thief.", "connections": []}},
            }),
            # char info for npc_001
            BatchResult({
                "ci_npc_001": {"ok": True, "data": {"character": {"gender": "male"}}},
            }),
        ]

        # LLM returns background for npc_001
        mock_llm_client.complete.return_value = json.dumps([
            {"id": "npc_001", "background": {"traits": ["stern"], "backstory": "Born leader.", "connections": []}},
        ])

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        result = await gen.ensure_backgrounds(sample_candidates)

        assert result[0]["background"]["traits"] == ["stern"]
        assert result[1]["background"]["traits"] == ["sly"]

    @pytest.mark.asyncio
    async def test_non_dict_background_treated_as_missing(
        self, mock_llm_client, mock_state_client,
    ):
        """Non-dict values (e.g. string) are treated as missing."""
        cands = [{"game_id": "npc_001", "name": "Wolf", "faction": "dolg"}]
        mock_state_client.execute_batch.side_effect = [
            BatchResult({"bg_npc_001": {"ok": True, "data": "corrupted"}}),
            BatchResult({"ci_npc_001": {"ok": True, "data": {}}}),
        ]
        mock_llm_client.complete.return_value = json.dumps([
            {"id": "npc_001", "background": {"traits": ["brave"], "backstory": "A veteran.", "connections": []}},
        ])

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        result = await gen.ensure_backgrounds(cands)
        assert result[0]["background"]["traits"] == ["brave"]


# ---------------------------------------------------------------------------
# _batch_read_backgrounds
# ---------------------------------------------------------------------------


class TestBatchReadBackgrounds:
    """Tests for _batch_read_backgrounds."""

    @pytest.mark.asyncio
    async def test_returns_backgrounds_keyed_by_id(
        self, mock_llm_client, mock_state_client,
    ):
        cands = [
            {"game_id": "a", "name": "Alpha"},
            {"game_id": "b", "name": "Bravo"},
        ]
        mock_state_client.execute_batch.return_value = BatchResult({
            "bg_a": {"ok": True, "data": {"traits": ["x"]}},
            "bg_b": {"ok": True, "data": None},
        })

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        bgs = await gen._batch_read_backgrounds(cands)

        assert bgs["a"] == {"traits": ["x"]}
        assert bgs["b"] is None

    @pytest.mark.asyncio
    async def test_batch_read_failure_returns_empty(
        self, mock_llm_client, mock_state_client,
    ):
        """Exception during batch read yields empty dict."""
        mock_state_client.execute_batch.side_effect = ConnectionError("offline")

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        bgs = await gen._batch_read_backgrounds([{"game_id": "a", "name": "Alpha"}])

        assert bgs == {}

    @pytest.mark.asyncio
    async def test_query_error_maps_to_none(
        self, mock_llm_client, mock_state_client,
    ):
        """Failed sub-query for a specific candidate maps to None."""
        mock_state_client.execute_batch.return_value = BatchResult({
            "bg_a": {"ok": False, "error": "not found"},
        })

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        bgs = await gen._batch_read_backgrounds([{"game_id": "a", "name": "Alpha"}])
        assert bgs["a"] is None


# ---------------------------------------------------------------------------
# _fetch_character_info
# ---------------------------------------------------------------------------


class TestFetchCharacterInfo:
    """Tests for _fetch_character_info."""

    @pytest.mark.asyncio
    async def test_returns_infos_keyed_by_id(
        self, mock_llm_client, mock_state_client,
    ):
        mock_state_client.execute_batch.return_value = BatchResult({
            "ci_a": {"ok": True, "data": {"character": {"gender": "male"}}},
        })

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        infos = await gen._fetch_character_info(["a"])

        assert infos["a"]["character"]["gender"] == "male"

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty(
        self, mock_llm_client, mock_state_client,
    ):
        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        infos = await gen._fetch_character_info([])
        assert infos == {}

    @pytest.mark.asyncio
    async def test_batch_failure_returns_empty(
        self, mock_llm_client, mock_state_client,
    ):
        mock_state_client.execute_batch.side_effect = TimeoutError("slow")

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        infos = await gen._fetch_character_info(["a", "b"])
        assert infos == {}

    @pytest.mark.asyncio
    async def test_failed_sub_query_maps_to_empty_dict(
        self, mock_llm_client, mock_state_client,
    ):
        mock_state_client.execute_batch.return_value = BatchResult({
            "ci_a": {"ok": False, "error": "not found"},
        })

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        infos = await gen._fetch_character_info(["a"])
        assert infos["a"] == {}


# ---------------------------------------------------------------------------
# _generate_backgrounds
# ---------------------------------------------------------------------------


class TestGenerateBackgrounds:
    """Tests for _generate_backgrounds."""

    @pytest.mark.asyncio
    async def test_builds_payload_and_calls_llm(
        self, mock_llm_client, mock_state_client,
    ):
        cands = [
            {"game_id": "a", "name": "Alpha", "faction": "loner", "rank": 100, "background": None},
        ]
        char_infos = {"a": {"character": {"gender": "male"}, "squad_members": [{"name": "Bravo"}]}}

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        mock_llm_client.complete.return_value = json.dumps([
            {"id": "a", "background": {"traits": ["brave"], "backstory": "A lone wolf.", "connections": ["Bravo"]}},
        ])

        result = await gen._generate_backgrounds(cands, char_infos)

        assert len(result) == 1
        assert result[0]["id"] == "a"
        # Verify the LLM was called with system + user messages
        call_args = mock_llm_client.complete.call_args[0][0]
        assert call_args[0].role == "system"
        assert call_args[1].role == "user"
        # User message should be a JSON payload
        payload = json.loads(call_args[1].content)
        assert payload["characters"][0]["squad"] == ["Bravo"]

    @pytest.mark.asyncio
    async def test_llm_call_failure_returns_empty(
        self, mock_llm_client, mock_state_client,
    ):
        mock_llm_client.complete.side_effect = RuntimeError("API error")

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        result = await gen._generate_backgrounds(
            [{"game_id": "a", "name": "Alpha", "faction": "loner", "background": None}],
            {},
        )
        assert result == []


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    """Tests for _parse_response static method."""

    def test_valid_json_array(self):
        resp = json.dumps([
            {"id": "a", "background": {"traits": ["brave"], "backstory": "Survived.", "connections": []}},
        ])
        result = BackgroundGenerator._parse_response(resp)
        assert len(result) == 1
        assert result[0]["id"] == "a"

    def test_markdown_fence_stripped(self):
        resp = "```json\n" + json.dumps([
            {"id": "b", "background": {"traits": ["sly"], "backstory": "Cunning.", "connections": []}},
        ]) + "\n```"
        result = BackgroundGenerator._parse_response(resp)
        assert len(result) == 1
        assert result[0]["id"] == "b"

    def test_malformed_json_returns_empty(self):
        result = BackgroundGenerator._parse_response("not json at all")
        assert result == []

    def test_non_array_json_returns_empty(self):
        result = BackgroundGenerator._parse_response('{"id": "a"}')
        assert result == []

    def test_missing_id_field_skipped(self):
        resp = json.dumps([
            {"background": {"traits": ["brave"]}},  # missing id
            {"id": "b", "background": {"traits": ["sly"], "backstory": "Ok.", "connections": []}},
        ])
        result = BackgroundGenerator._parse_response(resp)
        assert len(result) == 1
        assert result[0]["id"] == "b"

    def test_missing_background_field_skipped(self):
        resp = json.dumps([
            {"id": "a"},  # missing background
            {"id": "b", "background": {"traits": [], "backstory": "", "connections": []}},
        ])
        result = BackgroundGenerator._parse_response(resp)
        assert len(result) == 1
        assert result[0]["id"] == "b"

    def test_non_dict_background_skipped(self):
        resp = json.dumps([
            {"id": "a", "background": "just a string"},
            {"id": "b", "background": {"traits": ["ok"]}},
        ])
        result = BackgroundGenerator._parse_response(resp)
        assert len(result) == 1
        assert result[0]["id"] == "b"

    def test_defaults_missing_sub_fields(self):
        """Missing traits/backstory/connections get sensible defaults."""
        resp = json.dumps([
            {"id": "a", "background": {}},
        ])
        result = BackgroundGenerator._parse_response(resp)
        assert len(result) == 1
        bg = result[0]["background"]
        assert bg["traits"] == []
        assert bg["backstory"] == ""
        assert bg["connections"] == []

    def test_non_dict_entries_skipped(self):
        resp = json.dumps(["a string", None, 42, {"id": "a", "background": {"traits": []}}])
        result = BackgroundGenerator._parse_response(resp)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _persist_backgrounds
# ---------------------------------------------------------------------------


class TestPersistBackgrounds:
    """Tests for _persist_backgrounds."""

    @pytest.mark.asyncio
    async def test_sends_mutations_for_each_entry(
        self, mock_llm_client, mock_state_client,
    ):
        gen_map = {
            "a": {"traits": ["brave"], "backstory": "Survived.", "connections": []},
            "b": {"traits": ["sly"], "backstory": "Cunning.", "connections": []},
        }

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        await gen._persist_backgrounds(gen_map)

        mock_state_client.mutate_batch.assert_called_once()
        mutations = mock_state_client.mutate_batch.call_args[0][0]
        assert len(mutations) == 2
        assert all(m["op"] == "set" for m in mutations)
        assert all(m["resource"] == "memory.background" for m in mutations)
        ids = {m["params"]["character_id"] for m in mutations}
        assert ids == {"a", "b"}

    @pytest.mark.asyncio
    async def test_empty_map_skips_mutation(
        self, mock_llm_client, mock_state_client,
    ):
        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        await gen._persist_backgrounds({})
        mock_state_client.mutate_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_mutation_failure_non_fatal(
        self, mock_llm_client, mock_state_client,
    ):
        """Mutation failure is logged but doesn't raise."""
        mock_state_client.mutate_batch.side_effect = ConnectionError("offline")

        gen = BackgroundGenerator(mock_llm_client, mock_state_client)
        # Should not raise
        await gen._persist_backgrounds({"a": {"traits": ["brave"]}})


# ---------------------------------------------------------------------------
# fast_llm_client support
# ---------------------------------------------------------------------------


class TestFastLLMClient:
    """Tests for fast_llm_client parameter in BackgroundGenerator."""

    def test_uses_fast_client_when_provided(self):
        """When fast_llm_client is provided, _generation_client should be the fast one."""
        main_client = MagicMock()
        fast_client = MagicMock()
        state_client = MagicMock()

        gen = BackgroundGenerator(main_client, state_client, fast_llm_client=fast_client)

        assert gen._generation_client is fast_client
        assert gen.llm_client is main_client

    def test_falls_back_to_main_client_when_no_fast(self):
        """When fast_llm_client is omitted, _generation_client should be the main one."""
        main_client = MagicMock()
        state_client = MagicMock()

        gen = BackgroundGenerator(main_client, state_client)

        assert gen._generation_client is main_client
        assert gen.llm_client is main_client

    @pytest.mark.asyncio
    async def test_generate_backgrounds_uses_fast_client(self):
        """_generate_backgrounds should call _generation_client (the fast one)."""
        main_client = MagicMock()
        main_client.complete = AsyncMock(return_value="should not be called")
        fast_client = MagicMock()
        fast_client.complete = AsyncMock(return_value=json.dumps([
            {"id": "a", "background": {"traits": ["quick"], "backstory": "Fast generated.", "connections": []}},
        ]))
        state_client = MagicMock()

        gen = BackgroundGenerator(main_client, state_client, fast_llm_client=fast_client)

        cands = [{"game_id": "a", "name": "Alpha", "faction": "loner", "background": None}]
        result = await gen._generate_backgrounds(cands, {})

        assert len(result) == 1
        fast_client.complete.assert_called_once()
        main_client.complete.assert_not_called()

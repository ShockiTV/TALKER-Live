"""Tests for BatchQuery, BatchResult, QueryError, and execute_batch."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from talker_service.state.batch import BatchQuery, BatchResult, QueryError
from talker_service.state.client import StateQueryClient, StateQueryTimeout


# ---------------------------------------------------------------------------
# 3.7  BatchQuery builder tests
# ---------------------------------------------------------------------------

class TestBatchQuery:
    """Tests for the BatchQuery builder."""

    def test_add_single_query(self):
        batch = BatchQuery().add("mem", "store.memories", params={"character_id": "123"})
        built = batch.build()
        assert len(built) == 1
        assert built[0]["id"] == "mem"
        assert built[0]["resource"] == "store.memories"
        assert built[0]["params"] == {"character_id": "123"}
        # Optional keys absent when not specified
        assert "filter" not in built[0]
        assert "sort" not in built[0]
        assert "limit" not in built[0]
        assert "fields" not in built[0]

    def test_add_chaining(self):
        batch = (
            BatchQuery()
            .add("a", "store.events")
            .add("b", "store.memories", params={"character_id": "x"})
            .add("c", "query.world")
        )
        built = batch.build()
        assert len(built) == 3
        assert [q["id"] for q in built] == ["a", "b", "c"]

    def test_query_ids_property(self):
        batch = BatchQuery().add("x", "store.events").add("y", "query.world")
        assert batch.query_ids == ["x", "y"]

    def test_full_sub_query_with_all_options(self):
        batch = BatchQuery().add(
            "ev",
            "store.events",
            filter={"type": "DEATH"},
            sort={"game_time_ms": -1},
            limit=12,
            fields=["type", "game_time_ms"],
        )
        q = batch.build()[0]
        assert q["filter"] == {"type": "DEATH"}
        assert q["sort"] == {"game_time_ms": -1}
        assert q["limit"] == 12
        assert q["fields"] == ["type", "game_time_ms"]

    def test_ref_helper(self):
        ref_str = BatchQuery.ref("mem", "last_update_time_ms")
        assert ref_str == "$ref:mem.last_update_time_ms"

    def test_ref_in_filter(self):
        batch = (
            BatchQuery()
            .add("mem", "store.memories", params={"character_id": "c1"})
            .add("ev", "store.events", filter={
                "game_time_ms": {"$gt": BatchQuery.ref("mem", "last_update_time_ms")}
            })
        )
        built = batch.build()
        assert built[1]["filter"]["game_time_ms"]["$gt"] == "$ref:mem.last_update_time_ms"

    def test_ref_ordering_valid(self):
        """$ref pointing to an earlier query is allowed."""
        batch = (
            BatchQuery()
            .add("a", "query.world")
            .add("b", "store.events", filter={"x": BatchQuery.ref("a", "loc")})
        )
        # Should not raise
        batch.build()

    def test_ref_ordering_invalid_later(self):
        """$ref pointing to a later query raises ValueError."""
        batch = (
            BatchQuery()
            .add("a", "store.events", filter={"x": BatchQuery.ref("b", "loc")})
            .add("b", "query.world")
        )
        with pytest.raises(ValueError, match="declared later"):
            batch.build()

    def test_ref_ordering_invalid_unknown(self):
        """$ref pointing to a non-existent query raises ValueError."""
        batch = BatchQuery().add(
            "a", "store.events",
            filter={"x": BatchQuery.ref("nonexistent", "field")}
        )
        with pytest.raises(ValueError, match="not a known query id"):
            batch.build()

    def test_ref_in_params(self):
        """$ref in params is also validated for ordering."""
        batch = (
            BatchQuery()
            .add("char", "query.character", params={"id": "c1"})
            .add("mem", "store.memories", params={
                "character_id": BatchQuery.ref("char", "game_id")
            })
        )
        # Should not raise — char is declared before mem
        batch.build()

    def test_ref_in_params_invalid(self):
        """$ref in params pointing to a later query raises ValueError."""
        batch = (
            BatchQuery()
            .add("mem", "store.memories", params={
                "character_id": BatchQuery.ref("char", "game_id")
            })
            .add("char", "query.character", params={"id": "c1"})
        )
        with pytest.raises(ValueError, match="declared later"):
            batch.build()

    def test_ref_nested_in_filter(self):
        """$ref deeply nested in filter structure is still validated."""
        batch = (
            BatchQuery()
            .add("ev", "store.events", filter={
                "$and": [
                    {"type": "DEATH"},
                    {"game_time_ms": {"$gt": BatchQuery.ref("missing", "ts")}}
                ]
            })
        )
        with pytest.raises(ValueError, match="not a known query id"):
            batch.build()

    def test_empty_batch_builds(self):
        """Empty batch builds to empty list."""
        assert BatchQuery().build() == []

    def test_self_ref_is_invalid(self):
        """Self-referencing $ref is invalid (not declared yet at point of use)."""
        batch = BatchQuery().add(
            "a", "store.events",
            filter={"x": BatchQuery.ref("a", "something")}
        )
        with pytest.raises(ValueError, match="declared later"):
            batch.build()


# ---------------------------------------------------------------------------
# 3.8  BatchResult accessor tests
# ---------------------------------------------------------------------------

class TestBatchResult:
    """Tests for the BatchResult accessor."""

    def test_getitem_success(self):
        result = BatchResult({
            "mem": {"ok": True, "data": {"narrative": "test"}},
        })
        assert result["mem"] == {"narrative": "test"}

    def test_getitem_returns_list(self):
        result = BatchResult({
            "ev": {"ok": True, "data": [{"type": "DEATH"}, {"type": "DIALOGUE"}]},
        })
        assert len(result["ev"]) == 2

    def test_getitem_none_data(self):
        """Successful query can return None data (e.g., no narrative)."""
        result = BatchResult({"mem": {"ok": True, "data": None}})
        assert result["mem"] is None

    def test_getitem_unknown_key(self):
        result = BatchResult({"mem": {"ok": True, "data": {}}})
        with pytest.raises(KeyError, match="no_such_query"):
            result["no_such_query"]

    def test_getitem_failed_query(self):
        result = BatchResult({
            "bad": {"ok": False, "error": "resource not found"},
        })
        with pytest.raises(QueryError) as exc_info:
            result["bad"]
        assert exc_info.value.query_id == "bad"
        assert "resource not found" in str(exc_info.value)

    def test_ok_success(self):
        result = BatchResult({"a": {"ok": True, "data": 42}})
        assert result.ok("a") is True

    def test_ok_failure(self):
        result = BatchResult({"a": {"ok": False, "error": "boom"}})
        assert result.ok("a") is False

    def test_ok_missing(self):
        result = BatchResult({})
        assert result.ok("missing") is False

    def test_error_returns_message(self):
        result = BatchResult({"a": {"ok": False, "error": "boom"}})
        assert result.error("a") == "boom"

    def test_error_returns_none_on_success(self):
        result = BatchResult({"a": {"ok": True, "data": 1}})
        assert result.error("a") is None

    def test_error_returns_none_for_missing(self):
        result = BatchResult({})
        assert result.error("missing") is None

    def test_keys(self):
        result = BatchResult({
            "a": {"ok": True, "data": 1},
            "b": {"ok": False, "error": "x"},
        })
        assert sorted(result.keys()) == ["a", "b"]


class TestQueryError:
    """Tests for the QueryError exception."""

    def test_attributes(self):
        err = QueryError("myquery", "something broke")
        assert err.query_id == "myquery"
        assert err.error == "something broke"

    def test_str(self):
        err = QueryError("myquery", "something broke")
        assert "myquery" in str(err)
        assert "something broke" in str(err)

    def test_is_exception(self):
        assert issubclass(QueryError, Exception)


# ---------------------------------------------------------------------------
# 3.9  execute_batch integration tests (mock ZMQ)
# ---------------------------------------------------------------------------

class TestExecuteBatch:
    """Tests for StateQueryClient.execute_batch with mocked ZMQ router."""

    @pytest.fixture
    def mock_router(self):
        router = MagicMock()
        router.publish = AsyncMock(return_value=True)
        router.create_request = MagicMock()
        return router

    @pytest.mark.asyncio
    async def test_execute_batch_success(self, mock_router):
        """Successful batch with two sub-queries."""
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({
            "results": {
                "mem": {"ok": True, "data": {"narrative": "story"}},
                "world": {"ok": True, "data": {"loc": "Rostok"}},
            }
        })
        mock_router.create_request.return_value = response_future

        client = StateQueryClient(mock_router, timeout=5.0)
        batch = (
            BatchQuery()
            .add("mem", "store.memories", params={"character_id": "c1"})
            .add("world", "query.world")
        )

        result = await client.execute_batch(batch)

        assert result.ok("mem")
        assert result["mem"]["narrative"] == "story"
        assert result["world"]["loc"] == "Rostok"

        # Verify publish was called with correct topic
        mock_router.publish.assert_called_once()
        call_args = mock_router.publish.call_args
        assert call_args[0][0] == "state.query.batch"
        payload = call_args[0][1]
        assert "request_id" in payload
        assert len(payload["queries"]) == 2

    @pytest.mark.asyncio
    async def test_execute_batch_partial_failure(self, mock_router):
        """One sub-query fails; the other succeeds."""
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({
            "results": {
                "ok_query": {"ok": True, "data": [1, 2, 3]},
                "bad_query": {"ok": False, "error": "unknown resource"},
            }
        })
        mock_router.create_request.return_value = response_future

        client = StateQueryClient(mock_router, timeout=5.0)
        batch = (
            BatchQuery()
            .add("ok_query", "store.events")
            .add("bad_query", "store.nope")
        )

        result = await client.execute_batch(batch)
        assert result.ok("ok_query")
        assert result["ok_query"] == [1, 2, 3]
        assert not result.ok("bad_query")
        with pytest.raises(QueryError):
            result["bad_query"]

    @pytest.mark.asyncio
    async def test_execute_batch_timeout(self, mock_router):
        """Timeout raises StateQueryTimeout with batch topic."""
        future = asyncio.get_event_loop().create_future()

        async def timeout_later():
            await asyncio.sleep(0.05)
            if not future.done():
                future.set_exception(TimeoutError("timed out"))

        asyncio.create_task(timeout_later())
        mock_router.create_request.return_value = future

        client = StateQueryClient(mock_router, timeout=5.0)
        batch = BatchQuery().add("a", "query.world")

        with pytest.raises(StateQueryTimeout) as exc_info:
            await client.execute_batch(batch)

        assert exc_info.value.topic == "state.query.batch"

    @pytest.mark.asyncio
    async def test_execute_batch_publish_fails(self, mock_router):
        """ConnectionError when router.publish returns False."""
        mock_router.publish = AsyncMock(return_value=False)
        mock_router.create_request.return_value = asyncio.get_event_loop().create_future()

        client = StateQueryClient(mock_router, timeout=5.0)
        batch = BatchQuery().add("a", "query.world")

        with pytest.raises(ConnectionError, match="Failed to publish"):
            await client.execute_batch(batch)

    @pytest.mark.asyncio
    async def test_execute_batch_validates_refs(self, mock_router):
        """build() validation runs before any ZMQ call."""
        client = StateQueryClient(mock_router, timeout=5.0)
        batch = (
            BatchQuery()
            .add("a", "store.events", filter={"x": BatchQuery.ref("b", "y")})
            .add("b", "query.world")
        )

        with pytest.raises(ValueError, match="declared later"):
            await client.execute_batch(batch)

        # No ZMQ calls should have been made
        mock_router.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_batch_custom_timeout(self, mock_router):
        """Custom timeout is passed to create_request."""
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({"results": {}})
        mock_router.create_request.return_value = response_future

        client = StateQueryClient(mock_router, timeout=30.0)
        batch = BatchQuery().add("a", "query.world")

        await client.execute_batch(batch, timeout=5.0)

        mock_router.create_request.assert_called_once()
        call_args = mock_router.create_request.call_args
        assert call_args[0][1] == 5.0  # custom timeout

    @pytest.mark.asyncio
    async def test_execute_batch_returns_batch_result(self, mock_router):
        """Return type is BatchResult."""
        response_future = asyncio.get_event_loop().create_future()
        response_future.set_result({"results": {"a": {"ok": True, "data": 1}}})
        mock_router.create_request.return_value = response_future

        client = StateQueryClient(mock_router, timeout=5.0)
        batch = BatchQuery().add("a", "query.world")

        result = await client.execute_batch(batch)
        assert isinstance(result, BatchResult)

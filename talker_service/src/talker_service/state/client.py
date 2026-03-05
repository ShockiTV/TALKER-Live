"""State query client for requesting game state from Lua via WebSocket."""

from __future__ import annotations

import uuid
from typing import Any

from loguru import logger

from .batch import BatchQuery, BatchResult


class StateQueryTimeout(TimeoutError):
    """Raised when a state query to Lua times out.
    
    Subclass of TimeoutError so existing ``except TimeoutError`` handlers
    still catch it, while callers that need to distinguish transient
    connectivity failures (e.g. Lua paused in main menu) can catch this
    specific type.
    
    Attributes:
        topic: The query topic that timed out (e.g. "state.query.memories").
        character_id: The character_id parameter if the query was character-specific.
    """

    def __init__(
        self,
        message: str = "State query timed out",
        *,
        topic: str | None = None,
        character_id: str | None = None,
    ):
        super().__init__(message)
        self.topic = topic
        self.character_id = character_id


class StateQueryClient:
    """Client for querying game state from Lua via WebSocket.
    
    Uses request/response pattern with request_id correlation.
    Publishes query with ``r`` field; response resolved via WSRouter's
    ``r``-field short-circuit.
    """
    
    def __init__(self, router, timeout: float = 30.0):
        """Initialize state query client.
        
        Args:
            router: WSRouter instance with publish and create_request capability
            timeout: Default timeout for queries in seconds
        """
        self.router = router
        self.timeout = timeout
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return str(uuid.uuid4())
    
    async def _send_query(
        self,
        topic: str,
        params: dict[str, Any],
        timeout: float | None = None
    ) -> dict[str, Any]:
        """Send a query and wait for response.
        
        Args:
            topic: Query topic (e.g., "state.query.memories")
            params: Query parameters
            timeout: Optional timeout override
            
        Returns:
            Response data dict
            
        Raises:
            StateQueryTimeout: If query times out (subclass of TimeoutError)
            ConnectionError: If query cannot be published
        """
        request_id = self._generate_request_id()
        timeout = timeout or self.timeout
        
        # Create pending request future
        future = self.router.create_request(request_id, timeout)
        
        # Build and send query
        payload = {
            "request_id": request_id,
            **params
        }
        
        success = await self.router.publish(topic, payload, r=request_id)
        if not success:
            raise ConnectionError(f"Failed to publish query to {topic}")
        
        logger.debug(f"Sent query {topic} with request_id {request_id}")
        
        # Wait for response
        try:
            response = await future
        except TimeoutError:
            character_id = params.get("character_id")
            raise StateQueryTimeout(
                f"State query timed out: {topic} (request_id={request_id})",
                topic=topic,
                character_id=character_id,
            ) from None
        
        logger.debug(f"Received response for {request_id}")
        
        return response.get("data", response)

    async def execute_batch(
        self,
        batch: BatchQuery,
        *,
        timeout: float | None = None,
        session: str | None = None,
    ) -> BatchResult:
        """Execute a batch query against Lua in a single WS roundtrip.

        Publishes a ``state.query.batch`` message containing all sub-queries
        with the request ID in the ``r`` field.  The response is resolved
        when ``WSRouter`` receives a frame with the matching ``r``.

        Args:
            batch: A :class:`BatchQuery` with at least one sub-query.
            timeout: Optional timeout override in seconds.
            session: Optional session_id for targeted send.

        Returns:
            BatchResult accessor for individual sub-query results.

        Raises:
            StateQueryTimeout: If Lua does not respond within the timeout.
            ConnectionError: If the WS publish fails.
            ValueError: If the batch has invalid $ref ordering.
        """
        queries = batch.build()  # validates $ref ordering
        request_id = self._generate_request_id()
        effective_timeout = timeout or self.timeout

        future = self.router.create_request(request_id, effective_timeout)

        payload = {
            "request_id": request_id,
            "queries": queries,
        }

        success = await self.router.publish("state.query.batch", payload, r=request_id, session=session)
        if not success:
            raise ConnectionError("Failed to publish batch query")

        logger.debug(
            "Sent batch query with {} sub-queries, request_id={}",
            len(queries),
            request_id,
        )

        try:
            response = await future
        except TimeoutError:
            raise StateQueryTimeout(
                f"Batch query timed out (request_id={request_id})",
                topic="state.query.batch",
            ) from None

        # Extract data field (matches wire format: {"request_id": ..., "data": {...}})
        data = response.get("data", response)
        results_raw = data.get("results", {}) if isinstance(data, dict) else {}
        logger.debug(
            "Received batch response for {} ({} results)",
            request_id,
            len(results_raw),
        )

        return BatchResult(results_raw)
    
    async def query_batch(
        self,
        queries: list[dict[str, Any]],
        *,
        timeout: float | None = None,
        session: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a batch of queries (simplified interface).

        Accepts old-style dicts with ``query`` and top-level params,
        auto-generates ``id`` fields, and translates to the batch
        protocol format expected by ``handle_batch_query`` in Lua.
        
        Args:
            queries: List of query dicts with 'query' (or 'resource') field and params
            timeout: Optional timeout override
            session: Optional session_id
        
        Returns:
            List of response dicts in same order as queries
        
        Raises:
            StateQueryTimeout: If query times out
            ConnectionError: If publish fails
        """
        request_id = self._generate_request_id()
        effective_timeout = timeout or self.timeout

        # Translate simplified format to batch protocol format
        translated: list[dict[str, Any]] = []
        ordered_ids: list[str] = []
        for idx, q in enumerate(queries):
            qid = q.get("id") or f"q{idx}"
            ordered_ids.append(qid)

            resource = q.get("resource") or q.get("query", "")
            # Gather remaining keys as params (exclude protocol keys)
            params = q.get("params")
            if params is None:
                params = {
                    k: v for k, v in q.items()
                    if k not in ("id", "resource", "query", "filter", "sort", "limit", "fields")
                }
            translated.append({
                "id": qid,
                "resource": resource,
                "params": params or {},
            })

        future = self.router.create_request(request_id, effective_timeout)
        
        payload = {
            "request_id": request_id,
            "queries": translated,
        }
        
        success = await self.router.publish("state.query.batch", payload, r=request_id, session=session)
        if not success:
            raise ConnectionError("Failed to publish batch query")
        
        logger.debug(f"Sent simple batch query ({len(translated)} queries, request_id={request_id})")
        
        try:
            response = await future
        except TimeoutError:
            raise StateQueryTimeout(
                f"Batch query timed out (request_id={request_id})",
                topic="state.query.batch",
            ) from None
        
        # Extract results dict keyed by qid, then convert to ordered list
        data = response.get("data", response)
        results_map = data.get("results", {}) if isinstance(data, dict) else {}

        # Return results as ordered list matching input query order
        results: list[dict[str, Any]] = []
        for qid in ordered_ids:
            entry = results_map.get(qid, {})
            if isinstance(entry, dict) and entry.get("ok"):
                results.append(entry.get("data", {}))
            else:
                results.append(entry)
        
        return results
    
    async def mutate_batch(
        self,
        mutations: list[dict[str, Any]],
        *,
        timeout: float | None = None,
        session: str | None = None,
    ) -> bool:
        """Execute a batch of state mutations.
        
        Sends state.mutate.batch message to Lua with mutation operations.
        Each mutation has: character_id, verb, resource, data.
        
        Args:
            mutations: List of mutation dicts
            timeout: Optional timeout override
            session: Optional session_id
        
        Returns:
            True if mutation succeeded
        
        Raises:
            StateQueryTimeout: If mutation times out
            ConnectionError: If publish fails
        """
        request_id = self._generate_request_id()
        effective_timeout = timeout or self.timeout
        
        future = self.router.create_request(request_id, effective_timeout)
        
        payload = {
            "request_id": request_id,
            "mutations": mutations,
        }
        
        success = await self.router.publish("state.mutate.batch", payload, r=request_id, session=session)
        if not success:
            raise ConnectionError("Failed to publish mutation batch")
        
        logger.debug(f"Sent mutation batch ({len(mutations)} mutations, request_id={request_id})")
        
        try:
            response = await future
        except TimeoutError:
            raise StateQueryTimeout(
                f"Mutation batch timed out (request_id={request_id})",
                topic="state.mutate.batch",
            ) from None
        
        # Check success status — response has {results: {id: {ok, error?}, ...}}
        results = response.get("results", {})
        if not results:
            return True  # Empty results means no mutations were processed (no-op)
        if isinstance(results, dict):
            return all(
                isinstance(r, dict) and r.get("ok", False)
                for r in results.values()
            )
        return True

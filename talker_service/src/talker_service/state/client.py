"""State query client for requesting game state from Lua via ZMQ."""

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
        topic: The ZMQ query topic that timed out (e.g. "state.query.memories").
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
    """Client for querying game state from Lua via ZMQ.
    
    Uses request/response pattern with request_id correlation.
    Publishes query to Lua, waits for response on state.response topic.
    """
    
    def __init__(self, router, timeout: float = 30.0):
        """Initialize state query client.
        
        Args:
            router: ZMQRouter instance with publish capability
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
        
        success = await self.router.publish(topic, payload)
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
    ) -> BatchResult:
        """Execute a batch query against Lua in a single ZMQ roundtrip.

        Publishes a ``state.query.batch`` message containing all sub-queries,
        waits for a correlated ``state.response``, and wraps the per-query
        results in a :class:`BatchResult`.

        Args:
            batch: A :class:`BatchQuery` with at least one sub-query.
            timeout: Optional timeout override in seconds.

        Returns:
            BatchResult accessor for individual sub-query results.

        Raises:
            StateQueryTimeout: If Lua does not respond within the timeout.
            ConnectionError: If the ZMQ publish fails.
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

        success = await self.router.publish("state.query.batch", payload)
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

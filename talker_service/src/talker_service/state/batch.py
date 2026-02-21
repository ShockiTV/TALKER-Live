"""Batch query builder and result accessor for state queries.

Provides BatchQuery for composing multiple sub-queries into a single ZMQ
roundtrip, and BatchResult for typed access to individual results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class QueryError(Exception):
    """Raised when accessing a failed sub-query result from BatchResult."""

    def __init__(self, query_id: str, error: str):
        self.query_id = query_id
        self.error = error
        super().__init__(f"Query '{query_id}' failed: {error}")


@dataclass
class _SubQuery:
    """Internal representation of a single sub-query."""
    id: str
    resource: str
    params: dict[str, Any] | None = None
    filter: dict[str, Any] | None = None
    sort: dict[str, int] | None = None
    limit: int | None = None
    fields: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id, "resource": self.resource}
        if self.params is not None:
            d["params"] = self.params
        if self.filter is not None:
            d["filter"] = self.filter
        if self.sort is not None:
            d["sort"] = self.sort
        if self.limit is not None:
            d["limit"] = self.limit
        if self.fields is not None:
            d["fields"] = self.fields
        return d


# Regex to find $ref strings in nested structures
_REF_PATTERN = re.compile(r'^\$ref:([^.]+)\.')


def _find_refs_in_value(value: Any) -> set[str]:
    """Recursively find all $ref query IDs referenced in a value."""
    refs: set[str] = set()
    if isinstance(value, str):
        m = _REF_PATTERN.match(value)
        if m:
            refs.add(m.group(1))
    elif isinstance(value, dict):
        for v in value.values():
            refs.update(_find_refs_in_value(v))
    elif isinstance(value, list):
        for v in value:
            refs.update(_find_refs_in_value(v))
    return refs


class BatchQuery:
    """Builder for composing batch query requests.

    Usage::

        batch = (
            BatchQuery()
            .add("mem", "store.memories", params={"character_id": "123"})
            .add("ev", "store.events",
                 filter={"game_time_ms": {"$gt": BatchQuery.ref("mem", "last_update_time_ms")}},
                 sort={"game_time_ms": -1},
                 limit=12)
        )

    Note: ``$regex`` in filters uses **Lua patterns** (not PCRE).
    Use ``$in`` for exact alternation or ``$or`` with multiple ``$regex``.
    """

    def __init__(self) -> None:
        self._queries: list[_SubQuery] = []
        self._ids: list[str] = []

    def add(
        self,
        id: str,
        resource: str,
        *,
        params: dict[str, Any] | None = None,
        filter: dict[str, Any] | None = None,
        sort: dict[str, int] | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
    ) -> "BatchQuery":
        """Add a sub-query to the batch. Returns self for chaining."""
        self._queries.append(_SubQuery(
            id=id,
            resource=resource,
            params=params,
            filter=filter,
            sort=sort,
            limit=limit,
            fields=fields,
        ))
        self._ids.append(id)
        return self

    @staticmethod
    def ref(query_id: str, path: str) -> str:
        """Generate a $ref string for cross-query value references.

        Args:
            query_id: ID of the earlier query to reference.
            path: Dotted path into the query result data.

        Returns:
            A ``$ref:query_id.path`` string.
        """
        return f"$ref:{query_id}.{path}"

    def build(self) -> list[dict[str, Any]]:
        """Build the queries array for the wire payload.

        Validates that $ref references only point to query IDs declared
        earlier in the add order.

        Raises:
            ValueError: If a $ref references an undeclared or out-of-order ID.
        """
        declared: set[str] = set()

        for q in self._queries:
            # Collect all $ref targets in this query's filter and params
            refs: set[str] = set()
            if q.filter:
                refs.update(_find_refs_in_value(q.filter))
            if q.params:
                refs.update(_find_refs_in_value(q.params))

            for ref_id in refs:
                if ref_id not in declared:
                    if ref_id in set(self._ids):
                        raise ValueError(
                            f"$ref ordering error: query '{q.id}' references "
                            f"'{ref_id}' which is declared later in the batch"
                        )
                    else:
                        raise ValueError(
                            f"$ref error: query '{q.id}' references "
                            f"'{ref_id}' which is not a known query id"
                        )

            declared.add(q.id)

        return [q.to_dict() for q in self._queries]

    @property
    def query_ids(self) -> list[str]:
        """Return the ordered list of query IDs."""
        return list(self._ids)


class BatchResult:
    """Accessor for batch query results.

    Provides dict-like access to individual sub-query results::

        result = await state_client.execute_batch(batch)
        memories = result["mem"]        # returns data or raises QueryError
        if result.ok("mem"):            # check success
            ...
    """

    def __init__(self, results: dict[str, dict[str, Any]]) -> None:
        self._results = results

    def __getitem__(self, query_id: str) -> Any:
        """Get the data for a successful sub-query, or raise on failure.

        Raises:
            KeyError: If query_id was not in the batch.
            QueryError: If the sub-query failed (ok=false).
        """
        if query_id not in self._results:
            raise KeyError(f"No result for query id: '{query_id}'")

        entry = self._results[query_id]
        if not entry.get("ok", False):
            raise QueryError(query_id, entry.get("error", "unknown error"))
        return entry.get("data")

    def ok(self, query_id: str) -> bool:
        """Check whether a sub-query succeeded.

        Returns False if the query_id is not present or failed.
        """
        entry = self._results.get(query_id)
        if entry is None:
            return False
        return bool(entry.get("ok", False))

    def error(self, query_id: str) -> str | None:
        """Get the error message for a failed sub-query, or None."""
        entry = self._results.get(query_id)
        if entry is None:
            return None
        if entry.get("ok", False):
            return None
        return entry.get("error")

    def keys(self) -> list[str]:
        """Return all sub-query IDs in the result."""
        return list(self._results.keys())

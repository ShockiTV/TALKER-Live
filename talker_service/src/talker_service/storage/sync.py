"""Two-step session sync: manifest diff, then fetch and upsert missing entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger


def _pair_set(items: list[dict[str, Any]] | None) -> set[tuple[int, str]]:
    out: set[tuple[int, str]] = set()
    for item in items or []:
        ts = item.get("ts")
        cs = item.get("cs")
        if ts is None or not cs:
            continue
        out.add((int(ts), str(cs)))
    return out


@dataclass
class MissingCharacter:
    id: str
    tiers: dict[str, set[tuple[int, str]]]
    background_cs: str | None = None


class SessionSyncService:
    """Syncs Lua memory_store_v2 state into Neo4j for a session."""

    def __init__(self, *, state_client, neo4j_client) -> None:
        self._state_client = state_client
        self._neo4j_client = neo4j_client

    async def fetch_manifest(self, connection_session: str) -> dict[str, Any]:
        results = await self._state_client.query_batch(
            [{"id": "manifest", "resource": "memory.sync_manifest", "params": {}}],
            session=connection_session,
        )
        if not results:
            return {"characters": [], "global_events": []}
        manifest = results[0] or {}
        if not isinstance(manifest, dict):
            return {"characters": [], "global_events": []}
        return manifest

    def diff_manifest(self, lua_manifest: dict[str, Any], graph_manifest: dict[str, Any]) -> dict[str, Any]:
        missing_characters: list[MissingCharacter] = []

        graph_chars: dict[str, dict[str, set[tuple[int, str]]]] = graph_manifest.get("characters", {})

        for char in lua_manifest.get("characters") or []:
            char_id = str(char.get("id") or "")
            if not char_id:
                continue

            tiers = char.get("tiers") or {}
            graph_tiers = graph_chars.get(char_id, {})

            missing_tiers: dict[str, set[tuple[int, str]]] = {}
            for tier_name in ("events", "summaries", "digests", "cores"):
                lua_pairs = _pair_set(tiers.get(tier_name))
                graph_pairs = graph_tiers.get(tier_name, set())
                missing = lua_pairs - graph_pairs
                if missing:
                    missing_tiers[tier_name] = missing

            missing_background = None
            background = char.get("background")
            if isinstance(background, dict) and background.get("cs"):
                lua_bg = str(background.get("cs"))
                graph_bg_set = graph_tiers.get("background", set())
                if (0, lua_bg) not in graph_bg_set:
                    missing_background = lua_bg

            if missing_tiers or missing_background:
                missing_characters.append(
                    MissingCharacter(
                        id=char_id,
                        tiers=missing_tiers,
                        background_cs=missing_background,
                    )
                )

        lua_global = _pair_set(lua_manifest.get("global_events"))
        graph_global = graph_manifest.get("global_events", set())
        missing_global = lua_global - graph_global

        return {
            "characters": missing_characters,
            "global_events": missing_global,
        }

    async def fetch_missing_entities(self, *, missing: dict[str, Any], connection_session: str) -> dict[str, Any]:
        queries: list[dict[str, Any]] = []
        query_meta: dict[str, tuple[str, str, Any]] = {}

        for char in missing["characters"]:
            for tier_name, pairs in char.tiers.items():
                qid = f"{char.id}:{tier_name}"
                queries.append(
                    {
                        "id": qid,
                        "resource": f"memory.{tier_name}",
                        "params": {"character_id": char.id},
                    }
                )
                query_meta[qid] = (char.id, tier_name, pairs)

            if char.background_cs:
                qid = f"{char.id}:background"
                queries.append(
                    {
                        "id": qid,
                        "resource": "memory.background",
                        "params": {"character_id": char.id},
                    }
                )
                query_meta[qid] = (char.id, "background", char.background_cs)

        if missing["global_events"]:
            qid = "global_events"
            queries.append({"id": qid, "resource": "memory.global_events", "params": {}})
            query_meta[qid] = ("__global__", "global_events", missing["global_events"])

        if not queries:
            return {"characters": [], "global_events": []}

        results = await self._state_client.query_batch(queries, session=connection_session)

        entities_by_char: dict[str, dict[str, Any]] = {}
        global_events: list[dict[str, Any]] = []

        for idx, q in enumerate(queries):
            qid = q["id"]
            response = results[idx] if idx < len(results) else None
            if response is None:
                continue

            char_id, tier_name, wanted = query_meta[qid]

            if tier_name == "global_events":
                wanted_pairs = wanted
                for item in response or []:
                    ts = item.get("ts")
                    cs = item.get("cs")
                    if ts is None or not cs:
                        continue
                    if (int(ts), str(cs)) in wanted_pairs:
                        global_events.append(item)
                continue

            if char_id not in entities_by_char:
                entities_by_char[char_id] = {
                    "id": char_id,
                    "tiers": {
                        "events": [],
                        "summaries": [],
                        "digests": [],
                        "cores": [],
                    },
                    "background": None,
                }

            if tier_name == "background":
                if isinstance(response, dict) and str(response.get("cs") or "") == str(wanted):
                    entities_by_char[char_id]["background"] = response
                continue

            wanted_pairs = wanted
            for item in response or []:
                ts = item.get("ts")
                cs = item.get("cs")
                if ts is None or not cs:
                    continue
                if (int(ts), str(cs)) in wanted_pairs:
                    entities_by_char[char_id]["tiers"][tier_name].append(item)

        return {
            "characters": list(entities_by_char.values()),
            "global_events": global_events,
        }

    async def sync_if_needed(
        self,
        *,
        connection_session: str,
        lua_session_id: str,
        player_id: str,
        branch: str,
        previous_lua_session_id: str | None,
    ) -> dict[str, Any]:
        """Perform two-step sync unless this is same-session reconnect."""
        if previous_lua_session_id == lua_session_id:
            logger.debug("Session sync skipped (same lua session_id: {})", lua_session_id)
            return {"skipped": True, "reason": "same_session"}

        if not self._neo4j_client or not self._neo4j_client.is_available():
            logger.debug("Session sync skipped (neo4j unavailable)")
            return {"skipped": True, "reason": "neo4j_unavailable"}

        manifest = await self.fetch_manifest(connection_session)
        graph_manifest = self._neo4j_client.get_manifest(lua_session_id)
        missing = self.diff_manifest(manifest, graph_manifest)

        missing_count = sum(len(char.tiers.get("events", set())) for char in missing["characters"])
        missing_count += len(missing["global_events"])

        entities = await self.fetch_missing_entities(missing=missing, connection_session=connection_session)
        self._neo4j_client.upsert_sync_entities(
            session_id=lua_session_id,
            entities=entities,
            player_id=player_id,
            branch=branch,
        )

        logger.info(
            "Session sync complete: session={}, chars={}, globals={}",
            lua_session_id,
            len(entities.get("characters", [])),
            len(entities.get("global_events", [])),
        )
        return {
            "skipped": False,
            "missing_count": missing_count,
            "characters_synced": len(entities.get("characters", [])),
            "global_synced": len(entities.get("global_events", [])),
        }

"""Neo4j client and ingest helpers for graph memory."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from loguru import logger

try:
    from neo4j import GraphDatabase  # pyright: ignore[reportMissingImports]
except Exception:  # pragma: no cover - optional dependency for local dev
    GraphDatabase = None


CONTEXT_ROLES_BY_TYPE: dict[str, list[str]] = {
    "death": ["killer", "victim", "actor"],
    "callout": ["spotter", "target", "actor"],
    "taunt": ["taunter", "target", "actor"],
    "artifact": ["actor"],
    "anomaly": ["actor"],
    "map_transition": ["actor"],
    "injury": ["actor"],
    "sleep": ["actor"],
    "task": ["actor", "task_giver"],
    "weapon_jam": ["actor"],
    "reload": ["actor"],
    "dialogue": ["speaker", "actor"],
    "idle": ["speaker", "actor"],
    "emission": ["actor"],
}


def _canonical_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": event.get("type"),
        "context": event.get("context", {}),
        "game_time_ms": event.get("game_time_ms") or event.get("timestamp") or 0,
    }


def compute_event_checksum(event: dict[str, Any]) -> str:
    """Fallback checksum when Lua payload lacks cs."""
    payload = _canonical_event_payload(event)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()[:8]


def _format_character(value: Any) -> str:
    if not isinstance(value, dict):
        return str(value)
    name = value.get("name") or "Unknown"
    technical_id = value.get("game_id") or value.get("id") or "?"
    return f"{name} [{technical_id}]"


def render_event_text(event: dict[str, Any]) -> str:
    """Render compact deterministic text for indexing and BM25."""
    event_type = str(event.get("type") or "unknown")
    context = event.get("context") or {}

    roles = CONTEXT_ROLES_BY_TYPE.get(event_type, [])
    parts: list[str] = []

    for role in roles:
        value = context.get(role)
        if value is None:
            continue
        if isinstance(value, dict):
            parts.append(f"{role}={_format_character(value)}")
        else:
            parts.append(f"{role}={value}")

    for key in sorted(context.keys()):
        if key in roles:
            continue
        value = context[key]
        if isinstance(value, (dict, list)):
            continue
        parts.append(f"{key}={value}")

    if parts:
        return f"{event_type}: " + ", ".join(parts)
    return event_type


class Neo4jClient:
    """Thin Neo4j driver wrapper with graceful no-config behavior."""

    def __init__(
        self,
        *,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
    ) -> None:
        self.uri = uri or os.getenv("NEO4J_URI", "").strip()
        self.user = user or os.getenv("NEO4J_USER", "neo4j").strip() or "neo4j"
        self.password = password or os.getenv("NEO4J_PASSWORD", "").strip()
        self.database = database
        self._driver = None

        if not self.uri:
            return
        if GraphDatabase is None:
            logger.warning("neo4j package not installed; graph storage disabled")
            return

        auth = (self.user, self.password)
        try:
            self._driver = GraphDatabase.driver(self.uri, auth=auth)
        except Exception as exc:
            logger.warning("Failed to initialize Neo4j driver: {}", exc)
            self._driver = None

    def is_available(self) -> bool:
        return bool(self._driver and self.uri)

    def close(self) -> None:
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                logger.debug("Neo4j driver close failed", exc_info=True)

    def execute_read(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self.is_available():
            return []
        params = params or {}
        with self._driver.session(database=self.database) as session:
            result = session.execute_read(lambda tx: list(tx.run(cypher, **params)))
        return [dict(row) for row in result]

    def execute_write(self, cypher: str, params: dict[str, Any] | None = None) -> None:
        if not self.is_available():
            return
        params = params or {}
        with self._driver.session(database=self.database) as session:
            session.execute_write(lambda tx: tx.run(cypher, **params).consume())

    def ensure_session(self, session_id: str, *, player_id: str = "local", branch: str = "main") -> None:
        if not session_id:
            return
        self.execute_write(
            """
            MERGE (s:Session {id: $session_id})
            ON CREATE SET s.created_at = $created_at
            SET s.player_id = $player_id,
                s.branch = $branch
            """,
            {
                "session_id": session_id,
                "created_at": int(time.time() * 1000),
                "player_id": player_id,
                "branch": branch,
            },
        )

    def has_event_embedding(self, ts: int, cs: str) -> bool:
        rows = self.execute_read(
            "MATCH (e:Event {ts: $ts, cs: $cs}) RETURN e.embedding IS NOT NULL AS has_embedding LIMIT 1",
            {"ts": int(ts), "cs": str(cs)},
        )
        if not rows:
            return False
        return bool(rows[0].get("has_embedding"))

    def ingest_event(
        self,
        session_id: str,
        event: dict[str, Any],
        embedding: list[float] | None = None,
        *,
        player_id: str = "local",
        branch: str = "main",
        text: str | None = None,
    ) -> bool:
        if not self.is_available() or not session_id:
            return False

        event_ts = int(event.get("ts") or event.get("game_time_ms") or event.get("timestamp") or 0)
        event_cs = str(event.get("cs") or compute_event_checksum(event))
        event_type = str(event.get("type") or "unknown")
        event_time = int(event.get("game_time_ms") or event.get("timestamp") or event_ts)
        event_text = text or render_event_text(event)
        token_count = max(1, len(event_text) // 4)

        self.ensure_session(session_id, player_id=player_id, branch=branch)

        self.execute_write(
            """
            MATCH (s:Session {id: $session_id})
            MERGE (e:Event {ts: $ts, cs: $cs})
            ON CREATE SET e.created_at = $created_at
            SET e.type = $event_type,
                e.game_time_ms = $game_time_ms,
                e.text = $text,
                e.token_count = $token_count
            FOREACH (_ IN CASE WHEN $embedding IS NULL THEN [] ELSE [1] END |
                SET e.embedding = $embedding
            )
            MERGE (s)-[:HAS_EVENT]->(e)
            """,
            {
                "session_id": session_id,
                "ts": event_ts,
                "cs": event_cs,
                "created_at": int(time.time() * 1000),
                "event_type": event_type,
                "game_time_ms": event_time,
                "text": event_text,
                "token_count": token_count,
                "embedding": embedding,
            },
        )

        context = event.get("context") or {}
        roles = CONTEXT_ROLES_BY_TYPE.get(event_type, [])

        for role in roles:
            char = context.get(role)
            if isinstance(char, dict):
                self._merge_character_edge(
                    session_id=session_id,
                    event_ts=event_ts,
                    event_cs=event_cs,
                    role=role,
                    character=char,
                    player_id=player_id,
                    branch=branch,
                )

        for witness in event.get("witnesses") or []:
            if isinstance(witness, dict):
                self._merge_witness_edge(
                    session_id=session_id,
                    event_ts=event_ts,
                    event_cs=event_cs,
                    character=witness,
                    player_id=player_id,
                    branch=branch,
                )

        return True

    def _merge_character_edge(
        self,
        *,
        session_id: str,
        event_ts: int,
        event_cs: str,
        role: str,
        character: dict[str, Any],
        player_id: str,
        branch: str,
    ) -> None:
        self.execute_write(
            """
            MATCH (s:Session {id: $session_id})
            MATCH (e:Event {ts: $event_ts, cs: $event_cs})
            MERGE (c:Character {game_id: $game_id, session_id: $session_id})
            SET c.name = coalesce($name, c.name),
                c.faction = coalesce($faction, c.faction),
                c.experience = coalesce($experience, c.experience),
                c.story_id = coalesce($story_id, c.story_id),
                c.player_id = $player_id,
                c.branch = $branch
            FOREACH (_ IN CASE WHEN $is_player THEN [1] ELSE [] END |
                SET c:PlayerCharacter
            )
            MERGE (s)-[:SCOPES]->(c)
            MERGE (e)-[:INVOLVES {role: $role}]->(c)
            """,
            {
                "session_id": session_id,
                "event_ts": event_ts,
                "event_cs": event_cs,
                "role": role,
                "game_id": str(character.get("game_id") or ""),
                "name": character.get("name"),
                "faction": character.get("faction"),
                "experience": character.get("experience"),
                "story_id": character.get("story_id"),
                "is_player": str(character.get("game_id")) == "0",
                "player_id": player_id,
                "branch": branch,
            },
        )

    def _merge_witness_edge(
        self,
        *,
        session_id: str,
        event_ts: int,
        event_cs: str,
        character: dict[str, Any],
        player_id: str,
        branch: str,
    ) -> None:
        self.execute_write(
            """
            MATCH (s:Session {id: $session_id})
            MATCH (e:Event {ts: $event_ts, cs: $event_cs})
            MERGE (c:Character {game_id: $game_id, session_id: $session_id})
            SET c.name = coalesce($name, c.name),
                c.faction = coalesce($faction, c.faction),
                c.experience = coalesce($experience, c.experience),
                c.story_id = coalesce($story_id, c.story_id),
                c.player_id = $player_id,
                c.branch = $branch
            FOREACH (_ IN CASE WHEN $is_player THEN [1] ELSE [] END |
                SET c:PlayerCharacter
            )
            MERGE (s)-[:SCOPES]->(c)
            MERGE (c)-[:WITNESSED]->(e)
            """,
            {
                "session_id": session_id,
                "event_ts": event_ts,
                "event_cs": event_cs,
                "game_id": str(character.get("game_id") or ""),
                "name": character.get("name"),
                "faction": character.get("faction"),
                "experience": character.get("experience"),
                "story_id": character.get("story_id"),
                "is_player": str(character.get("game_id")) == "0",
                "player_id": player_id,
                "branch": branch,
            },
        )

    def get_manifest(self, session_id: str) -> dict[str, Any]:
        """Load compact (ts, cs) manifest currently present for a session."""
        if not self.is_available() or not session_id:
            return {"characters": {}, "global_events": set()}

        rows = self.execute_read(
            """
            MATCH (s:Session {id: $session_id})-[:SCOPES]->(c:Character)
            OPTIONAL MATCH (s)-[:HAS_EVENT]->(ev:Event)
            OPTIONAL MATCH (s)-[:HAS_GLOBAL_EVENT]->(ge:GlobalEvent)
            RETURN c.game_id AS character_id,
                   collect(DISTINCT [ev.ts, ev.cs]) AS events,
                   collect(DISTINCT [ge.ts, ge.cs]) AS global_events
            """,
            {"session_id": session_id},
        )

        characters: dict[str, dict[str, set[tuple[int, str]]]] = {}
        global_pairs: set[tuple[int, str]] = set()

        for row in rows:
            character_id = str(row.get("character_id") or "")
            char_data = characters.setdefault(
                character_id,
                {
                    "events": set(),
                    "summaries": set(),
                    "digests": set(),
                    "cores": set(),
                    "background": set(),
                },
            )
            for ts_cs in row.get("events") or []:
                if isinstance(ts_cs, (list, tuple)) and len(ts_cs) == 2 and ts_cs[0] is not None and ts_cs[1]:
                    char_data["events"].add((int(ts_cs[0]), str(ts_cs[1])))
            for ts_cs in row.get("global_events") or []:
                if isinstance(ts_cs, (list, tuple)) and len(ts_cs) == 2 and ts_cs[0] is not None and ts_cs[1]:
                    global_pairs.add((int(ts_cs[0]), str(ts_cs[1])))

        return {"characters": characters, "global_events": global_pairs}

    def upsert_sync_entities(
        self,
        *,
        session_id: str,
        entities: dict[str, Any],
        player_id: str = "local",
        branch: str = "main",
    ) -> None:
        """Upsert entities fetched from Lua during two-step sync."""
        if not self.is_available() or not session_id:
            return

        self.ensure_session(session_id, player_id=player_id, branch=branch)

        for item in entities.get("global_events") or []:
            ts = int(item.get("ts") or 0)
            cs = str(item.get("cs") or "")
            if not ts or not cs:
                continue
            text = item.get("text") or str(item.get("type") or "global_event")
            token_count = max(1, len(text) // 4)
            self.execute_write(
                """
                MATCH (s:Session {id: $session_id})
                MERGE (g:GlobalEvent {ts: $ts, cs: $cs})
                SET g.type = coalesce($event_type, g.type),
                    g.game_time_ms = coalesce($game_time_ms, g.game_time_ms, $ts),
                    g.text = coalesce($text, g.text),
                    g.token_count = coalesce($token_count, g.token_count)
                MERGE (s)-[:HAS_GLOBAL_EVENT]->(g)
                """,
                {
                    "session_id": session_id,
                    "ts": ts,
                    "cs": cs,
                    "event_type": item.get("type"),
                    "game_time_ms": item.get("timestamp") or item.get("game_time_ms") or ts,
                    "text": text,
                    "token_count": token_count,
                },
            )

        for char in entities.get("characters") or []:
            char_id = str(char.get("id") or "")
            if not char_id:
                continue

            self.execute_write(
                """
                MATCH (s:Session {id: $session_id})
                MERGE (c:Character {game_id: $char_id, session_id: $session_id})
                SET c.player_id = $player_id,
                    c.branch = $branch
                MERGE (s)-[:SCOPES]->(c)
                """,
                {
                    "session_id": session_id,
                    "char_id": char_id,
                    "player_id": player_id,
                    "branch": branch,
                },
            )

            tiers = char.get("tiers") or {}
            for tier_name, label, rel in (
                ("summaries", "Summary", "HAS_SUMMARY"),
                ("digests", "Digest", "HAS_DIGEST"),
                ("cores", "Core", "HAS_CORE"),
            ):
                for item in tiers.get(tier_name) or []:
                    ts = int(item.get("ts") or 0)
                    cs = str(item.get("cs") or "")
                    if not ts or not cs:
                        continue
                    text = item.get("text") or ""
                    token_count = max(1, len(text) // 4)
                    self.execute_write(
                        f"""
                        MATCH (s:Session {{id: $session_id}})
                        MATCH (c:Character {{game_id: $char_id, session_id: $session_id}})
                        MERGE (m:MemoryNode:{label} {{ts: $ts, cs: $cs}})
                        SET m.tier = $tier,
                            m.start_ts = coalesce($start_ts, m.start_ts),
                            m.end_ts = coalesce($end_ts, m.end_ts),
                            m.text = coalesce($text, m.text),
                            m.token_count = coalesce($token_count, m.token_count)
                        MERGE (c)-[:{rel}]->(m)
                        """,
                        {
                            "session_id": session_id,
                            "char_id": char_id,
                            "ts": ts,
                            "cs": cs,
                            "tier": item.get("tier") or tier_name[:-1],
                            "start_ts": item.get("start_ts"),
                            "end_ts": item.get("end_ts"),
                            "text": text,
                            "token_count": token_count,
                        },
                    )

            for item in tiers.get("events") or []:
                ts = int(item.get("ts") or 0)
                cs = str(item.get("cs") or "")
                if not ts or not cs:
                    continue
                self.execute_write(
                    """
                    MATCH (s:Session {id: $session_id})
                    MATCH (c:Character {game_id: $char_id, session_id: $session_id})
                    MERGE (e:Event {ts: $ts, cs: $cs})
                    SET e.type = coalesce($event_type, e.type),
                        e.game_time_ms = coalesce($game_time_ms, e.game_time_ms, $ts),
                        e.text = coalesce($text, e.text),
                        e.token_count = coalesce($token_count, e.token_count)
                    MERGE (s)-[:HAS_EVENT]->(e)
                    MERGE (c)-[:WITNESSED]->(e)
                    """,
                    {
                        "session_id": session_id,
                        "char_id": char_id,
                        "ts": ts,
                        "cs": cs,
                        "event_type": item.get("type"),
                        "game_time_ms": item.get("timestamp") or item.get("game_time_ms") or ts,
                        "text": item.get("text") or item.get("type") or "event",
                        "token_count": max(1, len(item.get("text") or item.get("type") or "event") // 4),
                    },
                )

            background = char.get("background")
            if isinstance(background, dict) and background.get("cs"):
                bg_cs = str(background.get("cs"))
                text = background.get("backstory") or "background"
                self.execute_write(
                    """
                    MATCH (c:Character {game_id: $char_id, session_id: $session_id})
                    MERGE (b:Background {character_id: $char_id, cs: $cs})
                    SET b.text = coalesce($text, b.text),
                        b.token_count = coalesce($token_count, b.token_count)
                    MERGE (c)-[:HAS_BACKGROUND]->(b)
                    """,
                    {
                        "session_id": session_id,
                        "char_id": char_id,
                        "cs": bg_cs,
                        "text": text,
                        "token_count": max(1, len(text) // 4),
                    },
                )

    def search_vector(
        self,
        *,
        session_id: str,
        char_id: str,
        embedding: list[float] | None,
        scope: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not embedding:
            return []
        if not self.is_available():
            return []

        if scope == "global":
            cypher = """
            CALL db.index.vector.queryNodes('event_embedding_idx', $limit, $embedding)
            YIELD node, score
            MATCH (s:Session {id: $session_id})-[:HAS_EVENT|HAS_GLOBAL_EVENT]->(node)
            RETURN node.ts AS ts,
                   node.cs AS cs,
                   node.text AS text,
                   coalesce(node.token_count, 0) AS token_count,
                   coalesce(node.game_time_ms, node.ts, 0) AS game_time_ms,
                   score
            """
            params = {
                "session_id": session_id,
                "limit": int(limit),
                "embedding": embedding,
            }
        else:
            cypher = """
            CALL db.index.vector.queryNodes('event_embedding_idx', $limit, $embedding)
            YIELD node, score
            MATCH (s:Session {id: $session_id})-[:SCOPES]->(c:Character {game_id: $char_id, session_id: $session_id})
            WHERE (c)-[:WITNESSED|HAS_SUMMARY|HAS_DIGEST|HAS_CORE|HAS_BACKGROUND]->(node)
               OR (s)-[:HAS_EVENT]->(node)
            RETURN node.ts AS ts,
                   node.cs AS cs,
                   node.text AS text,
                   coalesce(node.token_count, 0) AS token_count,
                   coalesce(node.game_time_ms, node.ts, 0) AS game_time_ms,
                   score
            """
            params = {
                "session_id": session_id,
                "char_id": char_id,
                "limit": int(limit),
                "embedding": embedding,
            }

        try:
            return self.execute_read(cypher, params)
        except Exception as exc:
            logger.debug("Vector search unavailable: {}", exc)
            return []

    def search_bm25(
        self,
        *,
        session_id: str,
        char_id: str,
        query_text: str,
        scope: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if not query_text:
            return []
        if not self.is_available():
            return []

        cypher = """
        CALL db.index.fulltext.queryNodes('character_name_fulltext', $query_text, {limit: $limit})
        YIELD node AS c, score
        MATCH (s:Session {id: $session_id})-[:SCOPES]->(c)
        OPTIONAL MATCH (e:Event)-[:INVOLVES]->(c)
        WHERE e IS NOT NULL
        RETURN e.ts AS ts,
               e.cs AS cs,
               e.text AS text,
               coalesce(e.token_count, 0) AS token_count,
               coalesce(e.game_time_ms, e.ts, 0) AS game_time_ms,
               score
        ORDER BY score DESC
        LIMIT $limit
        """

        params = {
            "session_id": session_id,
            "query_text": query_text,
            "limit": int(limit),
            "char_id": char_id,
        }

        try:
            rows = self.execute_read(cypher, params)
        except Exception as exc:
            logger.debug("BM25 search unavailable: {}", exc)
            return []

        if scope == "global":
            return rows

        filtered: list[dict[str, Any]] = []
        for row in rows:
            filtered.append(row)
        return filtered

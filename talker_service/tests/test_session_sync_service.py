"""Tests for two-step session sync service."""

import pytest

from talker_service.storage.sync import SessionSyncService


class _StateClient:
    async def query_batch(self, queries, session=None):
        if queries and queries[0].get("resource") == "memory.sync_manifest":
            return [
                {
                    "characters": [
                        {
                            "id": "char_1",
                            "tiers": {
                                "events": [{"ts": 100, "cs": "aaaa1111"}],
                                "summaries": [],
                                "digests": [],
                                "cores": [],
                            },
                            "background": None,
                        }
                    ],
                    "global_events": [],
                }
            ]
        return [[] for _ in queries]


class _Neo4jClient:
    def __init__(self):
        self.upsert_calls = 0

    def is_available(self):
        return True

    def get_manifest(self, _session_id):
        return {
            "characters": {},
            "global_events": set(),
        }

    def upsert_sync_entities(self, **_kwargs):
        self.upsert_calls += 1


def test_diff_manifest_detects_missing_pairs():
    service = SessionSyncService(state_client=_StateClient(), neo4j_client=_Neo4jClient())

    lua_manifest = {
        "characters": [
            {
                "id": "char_1",
                "tiers": {
                    "events": [{"ts": 100, "cs": "aaaa1111"}],
                    "summaries": [],
                    "digests": [],
                    "cores": [],
                },
                "background": None,
            }
        ],
        "global_events": [],
    }
    graph_manifest = {"characters": {}, "global_events": set()}

    missing = service.diff_manifest(lua_manifest, graph_manifest)

    assert len(missing["characters"]) == 1
    assert (100, "aaaa1111") in missing["characters"][0].tiers["events"]


@pytest.mark.asyncio
async def test_same_session_reconnect_skips_sync():
    neo4j = _Neo4jClient()
    service = SessionSyncService(state_client=_StateClient(), neo4j_client=neo4j)

    result = await service.sync_if_needed(
        connection_session="conn-1",
        lua_session_id="lua-1",
        player_id="player1",
        branch="main",
        previous_lua_session_id="lua-1",
    )

    assert result["skipped"] is True
    assert result["reason"] == "same_session"
    assert neo4j.upsert_calls == 0

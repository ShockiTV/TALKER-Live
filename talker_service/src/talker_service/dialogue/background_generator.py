"""Background generator for NPC characters.

Ensures all dialogue candidates have backgrounds before speaker selection.
When missing backgrounds are detected, runs a separate one-shot LLM
conversation to generate them, then persists via state mutations.
"""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from loguru import logger

from ..state.batch import BatchQuery

if TYPE_CHECKING:
    from ..llm.base import LLMClient
    from ..llm.models import Message
    from ..state.client import StateQueryClient


_BACKGROUND_SYSTEM_PROMPT = """\
You are a Game Master creating character backgrounds for NPCs in the Zone \
(STALKER universe). Your task is to generate backgrounds for characters who \
lack one, using the existing backgrounds of their squad-mates and neighbours \
as style reference.

For each character that needs a background, generate:
- **traits**: 3–6 adjective or short-phrase personality traits (JSON array of strings)
- **backstory**: A GM-style briefing paragraph (2–4 sentences) describing the \
character's history, motivation, and current situation in the Zone
- **connections**: References to other known characters or factions \
(JSON array of strings)

Return your answer as a JSON array. Each element must have:
```json
{"id": "<character_id>", "background": {"traits": [...], "backstory": "...", "connections": [...]}}
```

Only include characters whose background was null in the input. \
Do NOT re-generate backgrounds for characters that already have one. \
Return ONLY the JSON array — no prose, no markdown fences."""


class BackgroundGenerator:
    """Generates NPC backgrounds via a one-shot LLM conversation.

    Usage::

        gen = BackgroundGenerator(llm_client, state_client, fast_llm_client=fast_client)
        updated_candidates = await gen.ensure_backgrounds(candidates)

    The constructor accepts an optional ``fast_llm_client`` for cheaper
    background generation.  When provided, ``generate()`` uses the fast
    model; otherwise it falls back to the main ``llm_client``.
    """

    def __init__(
        self,
        llm_client: "LLMClient",
        state_client: "StateQueryClient",
        *,
        fast_llm_client: "LLMClient | None" = None,
    ) -> None:
        self.llm_client = llm_client
        self.state_client = state_client
        self._generation_client = fast_llm_client or llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ensure_backgrounds(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Ensure every candidate has a background, generating missing ones.

        Mutates candidate dicts in-place (adds ``background`` key) and also
        persists generated backgrounds to the game state.

        Args:
            candidates: Candidate speaker dicts with at least ``game_id``,
                ``name``, ``faction``.

        Returns:
            The same candidates list (possibly with newly-populated backgrounds).
        """
        if not candidates:
            return candidates

        # Step 1: batch-read backgrounds for all candidates
        backgrounds = await self._batch_read_backgrounds(candidates)

        # Attach existing backgrounds and track who is missing
        missing: list[dict[str, Any]] = []
        for cand in candidates:
            cid = str(cand.get("game_id", ""))
            bg = backgrounds.get(cid)
            if bg and not isinstance(bg, dict):
                bg = None
            if bg and bg.get("error"):
                bg = None
            cand["background"] = bg or None
            if cand["background"] is None:
                missing.append(cand)

        if not missing:
            logger.debug("All {} candidates already have backgrounds", len(candidates))
            return candidates

        logger.info(
            "{}/{} candidates lack backgrounds — generating",
            len(missing), len(candidates),
        )

        # Step 2: fetch character info for missing characters
        char_infos = await self._fetch_character_info(
            [str(c.get("game_id", "")) for c in missing]
        )

        # Step 3: build JSON payload and run LLM
        generated = await self._generate_backgrounds(candidates, char_infos)

        if not generated:
            logger.warning("Background generation returned no results")
            return candidates

        # Step 4: apply generated backgrounds to candidates and persist
        gen_map: dict[str, dict[str, Any]] = {
            str(g["id"]): g["background"] for g in generated if "id" in g and "background" in g
        }

        for cand in candidates:
            cid = str(cand.get("game_id", ""))
            if cid in gen_map and cand.get("background") is None:
                cand["background"] = gen_map[cid]

        await self._persist_backgrounds(gen_map)

        return candidates

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _batch_read_backgrounds(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Batch-read ``memory.background`` for all candidates."""
        batch = BatchQuery()
        ids: list[str] = []
        for cand in candidates:
            cid = str(cand.get("game_id", ""))
            if cid:
                batch.add(f"bg_{cid}", resource="memory.background", params={"character_id": cid})
                ids.append(cid)

        if not ids:
            return {}

        try:
            result = await self.state_client.execute_batch(batch, timeout=10.0)
        except Exception as e:
            logger.warning("Background batch read failed: {}", e)
            return {}

        backgrounds: dict[str, Any] = {}
        for cid in ids:
            qid = f"bg_{cid}"
            if result.ok(qid):
                backgrounds[cid] = result[qid]
            else:
                backgrounds[cid] = None
        return backgrounds

    async def _fetch_character_info(
        self,
        character_ids: list[str],
    ) -> dict[str, Any]:
        """Batch-query ``query.character_info`` for the given IDs."""
        if not character_ids:
            return {}

        batch = BatchQuery()
        for cid in character_ids:
            batch.add(f"ci_{cid}", resource="query.character_info", params={"id": cid})

        try:
            result = await self.state_client.execute_batch(batch, timeout=10.0)
        except Exception as e:
            logger.warning("Character info batch query failed: {}", e)
            return {}

        infos: dict[str, Any] = {}
        for cid in character_ids:
            qid = f"ci_{cid}"
            if result.ok(qid):
                infos[cid] = result[qid] or {}
            else:
                infos[cid] = {}
        return infos

    async def _generate_backgrounds(
        self,
        all_candidates: list[dict[str, Any]],
        char_infos: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Run one-shot LLM call to generate backgrounds.

        Args:
            all_candidates: All candidates (with and without backgrounds).
            char_infos: Character info dicts for characters needing generation.

        Returns:
            List of ``{"id": ..., "background": {...}}`` dicts, or empty on failure.
        """
        from ..llm.models import Message  # local import to avoid circular

        # Build JSON payload
        chars_payload: list[dict[str, Any]] = []
        for cand in all_candidates:
            cid = str(cand.get("game_id", ""))
            entry: dict[str, Any] = {
                "id": cid,
                "name": cand.get("name", "Unknown"),
                "faction": cand.get("faction", "unknown"),
                "rank": cand.get("rank", ""),
            }

            # Add gender / squad info from char_infos if available
            info = char_infos.get(cid, {})
            char_data = info.get("character", info)
            entry["gender"] = char_data.get("gender", "unknown")

            squad_members = info.get("squad_members", [])
            if squad_members:
                entry["squad"] = [
                    m.get("name", "Unknown") for m in squad_members
                ]

            entry["background"] = cand.get("background")  # None for missing
            chars_payload.append(entry)

        user_content = json.dumps({"characters": chars_payload}, indent=2)

        messages: list[Message] = [
            Message(role="system", content=_BACKGROUND_SYSTEM_PROMPT),
            Message(role="user", content=user_content),
        ]

        try:
            response = await self._generation_client.complete(messages)
        except Exception as e:
            logger.error("Background generation LLM call failed: {}", e)
            return []

        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: str) -> list[dict[str, Any]]:
        """Parse the LLM JSON response, tolerating markdown fences."""
        text = response.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Background generation returned invalid JSON: {}", e)
            return []

        if not isinstance(parsed, list):
            logger.error("Background generation expected JSON array, got {}", type(parsed).__name__)
            return []

        # Validate entries
        valid: list[dict[str, Any]] = []
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            if "id" not in entry or "background" not in entry:
                continue
            bg = entry["background"]
            if not isinstance(bg, dict):
                continue
            # Ensure required fields exist
            bg.setdefault("traits", [])
            bg.setdefault("backstory", "")
            bg.setdefault("connections", [])
            valid.append(entry)

        return valid

    async def _persist_backgrounds(
        self,
        gen_map: dict[str, dict[str, Any]],
    ) -> None:
        """Persist generated backgrounds via ``state.mutate.batch``."""
        if not gen_map:
            return

        mutations: list[dict[str, Any]] = []
        for cid, bg in gen_map.items():
            mutations.append({
                "op": "set",
                "resource": "memory.background",
                "params": {"character_id": cid},
                "data": bg,
            })

        try:
            await self.state_client.mutate_batch(mutations, timeout=10.0)
            logger.info("Persisted {} generated backgrounds", len(mutations))
        except Exception as e:
            logger.warning("Background mutation failed (non-fatal): {}", e)

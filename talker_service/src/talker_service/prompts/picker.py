"""Prompt builders for the ephemeral speaker picker step.

The picker selects which NPC from a set of candidates should react
to a given event.  Its messages are injected temporarily into the
conversation history and removed after the choice is parsed.
"""

from __future__ import annotations

import json
from typing import Any


def build_candidates_message(candidates: list[dict[str, Any]]) -> str:
    """Build a user message presenting candidate NPCs as JSON.

    Each candidate entry includes id, name, faction, rank, and
    background (traits / backstory / connections).

    Args:
        candidates: Candidate dicts, each with ``game_id``, ``name``,
            ``faction``, ``rank``, and ``background`` keys.

    Returns:
        JSON-formatted string listing all candidates.
    """
    entries: list[dict[str, Any]] = []
    for cand in candidates:
        entries.append({
            "id": str(cand.get("game_id", "unknown")),
            "name": cand.get("name", "Unknown"),
            "faction": cand.get("faction", "unknown"),
            "rank": cand.get("rank", ""),
            "background": cand.get("background"),
        })
    return json.dumps(entries, indent=2)


def build_event_description(event: dict[str, Any]) -> str:
    """Build a concise event description for the picker step.

    Args:
        event: Event data dict with ``type`` and ``context`` keys.

    Returns:
        Short structured event description.
    """
    from ..dialogue.conversation import _resolve_event_display_name

    event_type = event.get("type", "unknown")
    event_name = _resolve_event_display_name(event_type)
    context = event.get("context", {})

    actor = context.get("actor") or context.get("killer")
    victim = context.get("victim")

    actor_name = (
        actor.get("name", "Unknown") if isinstance(actor, dict) else str(actor)
    ) if actor else None
    victim_name = (
        victim.get("name", "Unknown") if isinstance(victim, dict) else str(victim)
    ) if victim else None

    parts: list[str] = [f"Event: {event_name}"]
    if actor_name:
        parts.append(f"Actor: {actor_name}")
    if victim_name:
        parts.append(f"Victim: {victim_name}")

    location = context.get("location")
    if location:
        parts.append(f"Location: {location}")

    return "\n".join(parts)


PICK_INSTRUCTION = (
    "Pick the character who would most naturally react to this event. "
    "Respond with ONLY their character ID (the numeric or string id from "
    "the candidate list above). Do not include any other text."
)


def parse_picker_response(
    response: str,
    candidate_ids: set[str],
) -> str | None:
    """Parse the LLM's picker response into a candidate ID.

    Strips whitespace and surrounding quotes / brackets, then checks
    against the candidate set.

    Args:
        response: Raw LLM response text.
        candidate_ids: Set of valid candidate IDs.

    Returns:
        Matched candidate ID, or ``None`` if invalid.
    """
    cleaned = response.strip().strip('"').strip("'").strip()
    # Also strip brackets e.g. [12345]
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1].strip()
    if cleaned in candidate_ids:
        return cleaned
    # Try matching as substring (LLM may add extra text like "ID: 12345")
    for cid in candidate_ids:
        if cid in cleaned:
            return cid
    return None

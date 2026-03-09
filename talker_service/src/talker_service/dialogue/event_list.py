"""Event list assembly: dedup, format, and filter events across candidates.

Fetches witness events for all speaker candidates, deduplicates by ``ts``
timestamp, and provides formatting/filtering helpers for picker and dialogue
steps.

Spec: specs/event-list-assembly/spec.md
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Event type display name mapping
# ---------------------------------------------------------------------------

_EVENT_DISPLAY_NAMES: dict[str | int, str] = {
    # String keys (canonical wire format from Lua)
    "death": "DEATH",
    "dialogue": "DIALOGUE",
    "callout": "CALLOUT",
    "taunt": "TAUNT",
    "artifact": "ARTIFACT",
    "anomaly": "ANOMALY",
    "map_transition": "MAP_TRANSITION",
    "emission": "EMISSION",
    "injury": "INJURY",
    "sleep": "SLEEP",
    "task": "TASK",
    "weapon_jam": "WEAPON_JAM",
    "reload": "RELOAD",
    "idle": "IDLE",
    "action": "ACTION",
    # Numeric keys (legacy / future-proofing)
    0: "DEATH", 1: "DIALOGUE", 2: "CALLOUT", 3: "TAUNT",
    4: "ARTIFACT", 5: "ANOMALY", 6: "MAP_TRANSITION", 7: "EMISSION",
    8: "INJURY", 9: "SLEEP", 10: "TASK", 11: "WEAPON_JAM",
    12: "RELOAD", 13: "IDLE", 14: "ACTION",
}

# Verb mapping for actor→victim event descriptions
_VERB_MAP: dict[str, str] = {
    "DEATH": "killed",
    "INJURY": "injured",
}


def _resolve_display_name(event_type: str | int) -> str:
    """Resolve an event type value to its uppercase display name."""
    return _EVENT_DISPLAY_NAMES.get(
        event_type,
        event_type.upper() if isinstance(event_type, str) else f"EVENT_{event_type}",
    )


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def assemble_event_list(
    events_by_candidate: dict[str, list[dict[str, Any]]],
    candidate_names: dict[str, str],
) -> tuple[dict[int, dict[str, Any]], dict[int, set[str]]]:
    """Deduplicate events across candidates by ``ts`` timestamp.

    Iterates over every candidate's event list.  Events without a ``ts``
    field are skipped.  When the same ``ts`` appears for multiple candidates
    each candidate's name is recorded in the witness set.

    Args:
        events_by_candidate: Mapping of ``candidate_id`` → list of event dicts.
        candidate_names: Mapping of ``candidate_id`` → display name.

    Returns:
        Tuple of:
        - ``unique_events``: ``{ts: event_dict}`` — first-seen event per ts.
        - ``witness_map``: ``{ts: {name1, name2, ...}}`` — which candidates saw it.
    """
    unique_events: dict[int, dict[str, Any]] = {}
    witness_map: dict[int, set[str]] = {}

    for cand_id, events in events_by_candidate.items():
        cand_name = candidate_names.get(cand_id, cand_id)
        for event in events:
            ts = event.get("ts")
            if ts is None:
                continue
            ts = int(ts)
            if ts not in unique_events:
                unique_events[ts] = event
            if ts not in witness_map:
                witness_map[ts] = set()
            witness_map[ts].add(cand_name)

    return unique_events, witness_map


def format_event_line(
    ts: int,
    event: dict[str, Any],
    witness_names: set[str],
) -> str:
    """Format a single event as a ``[ts] TYPE — description (witnesses: ...)`` line.

    Args:
        ts: Unique timestamp identifier for this event.
        event: Event data dict with ``type`` and ``context`` keys.
        witness_names: Set of display names for all witnesses.

    Returns:
        Formatted single-line string.
    """
    event_type = event.get("type", "unknown")
    event_name = _resolve_display_name(event_type)

    context = event.get("context", {})
    actor = context.get("actor") or context.get("killer")
    victim = context.get("victim")

    actor_name = (
        actor.get("name", "Unknown") if isinstance(actor, dict) else str(actor)
    ) if actor else None
    victim_name = (
        victim.get("name", "Unknown") if isinstance(victim, dict) else str(victim)
    ) if victim else None

    witnesses_str = ", ".join(sorted(witness_names))

    if actor_name and victim_name:
        verb = _VERB_MAP.get(event_name, "affected")
        return f"[{ts}] {event_name} — {actor_name} {verb} {victim_name} (witnesses: {witnesses_str})"
    elif actor_name:
        return f"[{ts}] {event_name} — {actor_name} (witnesses: {witnesses_str})"
    else:
        return f"[{ts}] {event_name} (witnesses: {witnesses_str})"


def build_event_list_text(
    unique_events: dict[int, dict[str, Any]],
    witness_map: dict[int, set[str]],
) -> str:
    """Build a multi-line event list string sorted by ``ts`` ascending.

    Args:
        unique_events: ``{ts: event_dict}`` deduplicated event collection.
        witness_map: ``{ts: set[str]}`` witness name sets.

    Returns:
        Newline-delimited event lines, or empty string if no events.
    """
    if not unique_events:
        return ""
    lines: list[str] = []
    for ts in sorted(unique_events.keys()):
        event = unique_events[ts]
        witnesses = witness_map.get(ts, set())
        lines.append(format_event_line(ts, event, witnesses))
    return "\n".join(lines)


def filter_events_for_speaker(
    unique_events: dict[int, dict[str, Any]],
    witness_map: dict[int, set[str]],
    speaker_name: str,
) -> tuple[dict[int, dict[str, Any]], dict[int, set[str]]]:
    """Filter events to only those witnessed by the given speaker name.

    Witness annotations in the returned map are preserved in full — all
    witnesses are included, not just the speaker.

    Args:
        unique_events: ``{ts: event_dict}`` deduplicated event collection.
        witness_map: ``{ts: set[str]}`` witness name sets.
        speaker_name: Display name of the speaker to filter by.

    Returns:
        Tuple of:
        - ``filtered_events``: ``{ts: event_dict}`` for witnessed events.
        - ``filtered_witness``: ``{ts: set[str]}`` with full witness sets preserved.
    """
    filtered_events: dict[int, dict[str, Any]] = {}
    filtered_witness: dict[int, set[str]] = {}

    for ts, witnesses in witness_map.items():
        if speaker_name in witnesses:
            filtered_events[ts] = unique_events[ts]
            filtered_witness[ts] = witnesses

    return filtered_events, filtered_witness

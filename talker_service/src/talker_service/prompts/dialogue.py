"""Dialogue prompt builders for the two-step dialogue flow.

Constructs the pointer-based user message sent to the LLM during the
persistent dialogue generation step.  Event details and backgrounds are
NOT inlined — they are already present as tagged system messages
(``EVT:``, ``BG:``, ``MEM:``).
"""

from __future__ import annotations


def build_dialogue_user_message(
    speaker_name: str,
    speaker_id: str,
    event_ts: int,
    narrative: str,
) -> str:
    """Build the pointer-based user message for the dialogue generation step.

    References the triggering event by ``EVT:{ts}`` and identifies the
    character by ID.  Personal narrative memories (if any) are included
    but event descriptions and background are NOT — those are already
    present as system messages.

    Args:
        speaker_name: Display name of the chosen speaker.
        speaker_id: Character ID string.
        event_ts: Timestamp of the triggering event (for EVT: reference).
        narrative: Personal narrative text (summaries/digests/cores), or
            empty string if no memories.

    Returns:
        Fully assembled user message string.
    """
    parts: list[str] = [
        f"React as **{speaker_name}** (ID: {speaker_id}) to EVT:{event_ts}.",
    ]
    if narrative:
        parts.append(f"\n**Personal memories:**\n{narrative}")
    parts.append(
        f"\nGenerate {speaker_name}'s dialogue — just the spoken words, nothing else."
    )
    return "\n".join(parts)

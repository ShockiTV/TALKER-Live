"""Dialogue prompt builders for the two-step dialogue flow.

Constructs the user message sent to the LLM during the persistent dialogue
generation step.  Event description, weather/time/location, and
speaker-witnessed events are included inline.  Backgrounds and static
world context live in the context-block user message (``_messages[1]``).
"""

from __future__ import annotations


def build_dialogue_user_message(
    speaker_name: str,
    speaker_id: str,
    event_description: str,
    narrative: str,
    *,
    dynamic_world_line: str = "",
    witness_text: str = "",
) -> str:
    """Build the user message for the dialogue generation step.

    Includes the triggering event description inline along with weather,
    time, and location.  Speaker-witnessed events are appended when
    available.

    Args:
        speaker_name: Display name of the chosen speaker.
        speaker_id: Character ID string.
        event_description: Human-readable event description.
        narrative: Personal narrative text (summaries/digests/cores), or
            empty string if no memories.
        dynamic_world_line: Per-turn weather/time/location string.
        witness_text: Formatted witness events text block.

    Returns:
        Fully assembled user message string.
    """
    parts: list[str] = []
    if dynamic_world_line:
        parts.append(dynamic_world_line)
    parts.append(event_description)
    if witness_text:
        parts.append(
            f"\n**Recent events witnessed by {speaker_name}:**\n{witness_text}"
        )
    parts.append(f"\nReact as **{speaker_name}** (ID: {speaker_id}).")
    if narrative:
        parts.append(f"\n**Personal memories:**\n{narrative}")
    parts.append(
        f"\nGenerate {speaker_name}'s dialogue — just the spoken words, nothing else."
    )
    return "\n".join(parts)

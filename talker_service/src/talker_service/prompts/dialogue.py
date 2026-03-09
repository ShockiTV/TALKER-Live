"""Dialogue prompt builders for the two-step dialogue flow.

Constructs the user message sent to the LLM during the persistent dialogue
generation step.  Events are listed in ``[ts] TYPE — description (witnesses:...)``
format with a ``[ts]`` pointer to the triggering event.  Backgrounds and static
world context live in the context-block user message (``_messages[1]``).  The
user message is ephemeral — removed after the LLM call; only the assistant
response persists in history.
"""

from __future__ import annotations


def build_dialogue_user_message(
    speaker_name: str,
    speaker_id: str,
    ts: int,
    narrative: str,
    *,
    dynamic_world_line: str = "",
    speaker_event_list_text: str = "",
) -> str:
    """Build the user message for the dialogue generation step.

    Uses ``[ts]`` pointer format with a speaker-filtered event list.
    The caller should pop this message from the conversation history after the
    LLM call and append only the assistant response (ephemeral pattern).

    Args:
        speaker_name: Display name of the chosen speaker.
        speaker_id: Character ID string.
        ts: Unique timestamp of the triggering event (used as pointer).
        narrative: Personal narrative text (summaries/digests/cores), or
            empty string if no memories.
        dynamic_world_line: Per-turn weather/time/location string.
        speaker_event_list_text: Formatted event list filtered to events
            witnessed by this speaker, in ``[ts] TYPE — ...`` format.

    Returns:
        Fully assembled user message string.
    """
    parts: list[str] = []
    if dynamic_world_line:
        parts.append(dynamic_world_line)
    if speaker_event_list_text:
        parts.append(
            f"\n**Recent events witnessed by {speaker_name}:**\n{speaker_event_list_text}"
        )
    parts.append(f"\nReact to event [{ts}] as **{speaker_name}** (ID: {speaker_id}).")
    if narrative:
        parts.append(f"\n**Personal memories:**\n{narrative}")
    parts.append(
        f"\nGenerate {speaker_name}'s dialogue — just the spoken words, nothing else."
    )
    return "\n".join(parts)


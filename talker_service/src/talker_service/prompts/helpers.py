"""Helper functions for prompt building.

Ports helper functions from Lua's prompt_builder.lua and event.lua.
"""

from .models import Character, Event


# Event types considered "junk" (low value for narrative)
JUNK_EVENT_TYPES = {
    "ARTIFACT",
    "ANOMALY", 
    "RELOAD",
    "WEAPON_JAM",
}


def describe_character(char: Character) -> str:
    """Format character description for prompts.
    
    Args:
        char: Character to describe
        
    Returns:
        Formatted string like "Wolf (Veteran Loner, Good rep)"
    """
    if char.faction in ("Monster", "Zombied"):
        return f"{char.name} ({char.faction})"
    
    parts = [char.name]
    details = []
    
    if char.experience:
        details.append(char.experience)
    if char.faction:
        details.append(char.faction)
    if char.reputation:
        details.append(f"{char.reputation} rep")
    
    if details:
        parts.append(f"({', '.join(details)})")
    
    # Add disguise info if present
    if char.visual_faction:
        parts.append(f"[disguised as {char.visual_faction}]")
    
    return " ".join(parts)


def describe_character_with_id(char: Character) -> str:
    """Format character with ID for speaker selection.
    
    Args:
        char: Character to describe
        
    Returns:
        Formatted string like "[ID: 123] Wolf (Veteran Loner)"
    """
    return f"[ID: {char.game_id}] {describe_character(char)}"


def describe_event(event: Event) -> str:
    """Convert event to human-readable text.
    
    Handles both typed events and legacy content-based events.
    
    Args:
        event: Event to describe
        
    Returns:
        Human-readable event description
    """
    # Synthetic/compressed events return content directly
    if event.is_synthetic and event.content:
        return event.content
    
    # Legacy content-based events
    if event.content and not event.is_typed:
        return event.content
    
    # Typed events - format based on type
    if event.type:
        return _format_typed_event(event)
    
    # Fallback
    return event.content or "Unknown event"


def _format_typed_event(event: Event) -> str:
    """Format a typed event based on its type and context."""
    ctx = event.context
    event_type = event.type
    
    # Get actor description if present
    actor = None
    if "actor" in ctx and isinstance(ctx["actor"], dict):
        actor = Character.from_dict(ctx["actor"])
    
    if event_type == "DEATH":
        victim = ctx.get("victim", {})
        killer = ctx.get("killer", {})
        victim_char = Character.from_dict(victim) if isinstance(victim, dict) else None
        killer_char = Character.from_dict(killer) if isinstance(killer, dict) else None
        
        if killer_char and victim_char:
            return f"{describe_character(killer_char)} killed {describe_character(victim_char)}"
        elif victim_char:
            return f"{describe_character(victim_char)} died"
        return "Someone died"
    
    elif event_type == "DIALOGUE":
        speaker = ctx.get("speaker", {})
        text = ctx.get("text", "")
        speaker_char = Character.from_dict(speaker) if isinstance(speaker, dict) else None
        
        if speaker_char:
            return f'{describe_character(speaker_char)} said: "{text}"'
        return f'Someone said: "{text}"'
    
    elif event_type == "CALLOUT":
        spotter = ctx.get("spotter", {})
        target = ctx.get("target", {})
        spotter_char = Character.from_dict(spotter) if isinstance(spotter, dict) else None
        target_char = Character.from_dict(target) if isinstance(target, dict) else None
        
        if spotter_char and target_char:
            return f"{describe_character(spotter_char)} spotted {describe_character(target_char)}"
        return "Someone spotted an enemy"
    
    elif event_type == "TAUNT":
        taunter = ctx.get("taunter", {})
        taunter_char = Character.from_dict(taunter) if isinstance(taunter, dict) else None
        
        if taunter_char:
            return f"{describe_character(taunter_char)} taunted their enemies"
        return "Someone taunted their enemies"
    
    elif event_type == "ARTIFACT":
        action = ctx.get("action", "found")
        item_name = ctx.get("item_name", "an artifact")
        
        if actor:
            return f"{describe_character(actor)} {action} {item_name}"
        return f"Someone {action} {item_name}"
    
    elif event_type == "ANOMALY":
        anomaly_type = ctx.get("anomaly_type", "an anomaly")
        
        if actor:
            return f"{describe_character(actor)} encountered {anomaly_type}"
        return f"Someone encountered {anomaly_type}"
    
    elif event_type == "MAP_TRANSITION":
        from_area = ctx.get("from_area", "somewhere")
        to_area = ctx.get("to_area", "somewhere")
        
        if actor:
            return f"{describe_character(actor)} traveled from {from_area} to {to_area}"
        return f"Traveled from {from_area} to {to_area}"
    
    elif event_type == "EMISSION":
        return "An emission swept through the Zone"
    
    elif event_type == "INJURY":
        severity = ctx.get("severity", "")
        
        if actor:
            return f"{describe_character(actor)} was injured{' severely' if severity == 'severe' else ''}"
        return "Someone was injured"
    
    elif event_type == "SLEEP":
        hours = ctx.get("hours", 0)
        
        if actor:
            return f"{describe_character(actor)} rested for {hours} hours"
        return f"Rested for {hours} hours"
    
    elif event_type == "TASK":
        task_status = ctx.get("task_status", "updated")
        task_name = ctx.get("task_name", "a task")
        
        if actor:
            return f"{describe_character(actor)} {task_status} task: {task_name}"
        return f"Task {task_status}: {task_name}"
    
    elif event_type == "WEAPON_JAM":
        if actor:
            return f"{describe_character(actor)}'s weapon jammed"
        return "A weapon jammed"
    
    elif event_type == "RELOAD":
        if actor:
            return f"{describe_character(actor)} reloaded their weapon"
        return "Someone reloaded"
    
    elif event_type == "IDLE":
        if actor:
            return f"{describe_character(actor)} is nearby and available for conversation"
        return "Someone is nearby"
    
    elif event_type == "ACTION":
        action_text = ctx.get("action", "did something")
        if actor:
            return f"{describe_character(actor)} {action_text}"
        return action_text
    
    # Fallback for unknown types
    return event.content or f"Event: {event_type}"


def is_junk_event(event: Event) -> bool:
    """Check if event is low-value for narrative (should be filtered).
    
    Args:
        event: Event to check
        
    Returns:
        True if event should be filtered from narrative
    """
    # Check typed event type
    if event.type and event.type in JUNK_EVENT_TYPES:
        return True
    
    # Check flags
    if event.flags.get("is_junk"):
        return True
    
    # Legacy content-based checks
    if event.content:
        content_lower = event.content.lower()
        junk_keywords = ["artifact", "anomaly", "reload", "jammed"]
        for keyword in junk_keywords:
            if keyword in content_lower:
                return True
    
    return False


def was_witnessed_by(event: Event, character_id: str) -> bool:
    """Check if a character witnessed an event.
    
    Args:
        event: Event to check
        character_id: Character ID to look for
        
    Returns:
        True if character is in witnesses list
    """
    if not event.witnesses:
        return False
    for witness in event.witnesses:
        if str(witness.game_id) == str(character_id):
            return True
    return False

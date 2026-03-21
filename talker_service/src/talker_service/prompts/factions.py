"""Faction data and relations.

Ports faction information from Lua's infra/STALKER/factions.lua.
"""

# Technical faction ID to display name mapping
FACTION_NAMES = {
    "stalker": "Loner",
    "dolg": "Duty",
    "freedom": "Freedom",
    "bandit": "Bandit",
    "army": "Army",
    "ecolog": "Ecolog",
    "killer": "Mercenary",
    "monolith": "Monolith",
    "csky": "Clear Sky",
    "renegade": "Renegade",
    "greh": "Sin",
    "isg": "ISG",
    "zombied": "Zombied",
    "monster": "Monster",
    "trader": "Trader",
}


def resolve_faction_name(faction_id: str) -> str:
    """Resolve technical faction ID to display name.
    
    Args:
        faction_id: Technical faction ID (e.g., "dolg", "killer")
        
    Returns:
        Display name (e.g., "Duty", "Mercenary") or the ID if unknown
    """
    return FACTION_NAMES.get(faction_id, faction_id)


# Faction descriptions keyed by technical ID
FACTION_DESCRIPTIONS = {
    "stalker": "Independent stalkers (Loners) who survive in the Zone through scavenging, artifact hunting, and odd jobs. No central leadership, just mutual aid.",
    "dolg": "A paramilitary faction dedicated to containing and eventually destroying the Zone. Strict discipline, military hierarchy, hostile to Freedom.",
    "freedom": "A faction of anarchists and idealists who believe the Zone should be open to all. Relaxed, drug-friendly, hostile to Duty.",
    "bandit": "Criminals and thugs who prey on other stalkers. No honor among thieves.",
    "army": "Ukrainian military forces tasked with securing the Zone perimeter. Shoot unauthorized personnel on sight.",
    "ecolog": "Scientists studying the Zone's anomalies and artifacts. Typically non-combatant, protected by guards.",
    "killer": "Professional soldiers for hire. No ideology, just money. Will work for anyone who pays.",
    "monolith": "Fanatical cultists who worship the Monolith and protect the center of the Zone. Extremely dangerous, near-mindless zealots.",
    "csky": "A scientific faction studying the Zone. Once prominent, now diminished after the second emission.",
    "renegade": "Outcasts and criminals, even more desperate than Bandits. Bottom of the Zone's hierarchy.",
    "greh": "A mysterious faction of Zone-worshipping zealots, distinct from but similar to Monolith.",
    "isg": "International military forces operating covertly in the Zone. Well-equipped and professional.",
    "zombied": "Stalkers whose minds have been destroyed by psy-emissions. Shambling husks of their former selves.",
    "monster": "Mutated creatures of the Zone. Not a faction per se, but universally hostile.",
    "trader": "Merchants who buy and sell goods throughout the Zone. Typically neutral.",
}


def get_faction_description(faction_id: str) -> str:
    """Get description for a faction.
    
    Args:
        faction_id: Technical faction ID (e.g., "dolg", "killer")
        
    Returns:
        Faction description or empty string
    """
    return FACTION_DESCRIPTIONS.get(faction_id, "")


# Faction relations (from game data) - using technical IDs
# Values: -1 = hostile, 0 = neutral, 1 = friendly/allied
FACTION_RELATIONS = {
    ("dolg", "freedom"): -1,
    ("dolg", "bandit"): -1,
    ("dolg", "monolith"): -1,
    ("dolg", "renegade"): -1,
    ("dolg", "army"): 0,
    ("dolg", "stalker"): 0,
    ("dolg", "ecolog"): 1,
    
    ("freedom", "dolg"): -1,
    ("freedom", "bandit"): 0,
    ("freedom", "monolith"): -1,
    ("freedom", "army"): -1,
    ("freedom", "stalker"): 1,
    ("freedom", "csky"): 0,
    
    ("army", "stalker"): -1,
    ("army", "bandit"): -1,
    ("army", "freedom"): -1,
    ("army", "monolith"): -1,
    ("army", "dolg"): 0,
    ("army", "ecolog"): 1,
    
    ("bandit", "stalker"): -1,
    ("bandit", "dolg"): -1,
    ("bandit", "army"): -1,
    ("bandit", "renegade"): 0,
    
    ("monolith", "stalker"): -1,
    ("monolith", "dolg"): -1,
    ("monolith", "freedom"): -1,
    ("monolith", "army"): -1,
    ("monolith", "ecolog"): -1,
    ("monolith", "killer"): -1,
    
    ("ecolog", "stalker"): 0,
    ("ecolog", "dolg"): 1,
    ("ecolog", "army"): 1,
    
    ("killer", "stalker"): 0,
    ("killer", "bandit"): 0,
    
    ("renegade", "stalker"): -1,
    ("renegade", "bandit"): 0,
}


def get_faction_relation(faction1: str, faction2: str) -> int:
    """Get relation between two factions.
    
    Args:
        faction1: First faction name
        faction2: Second faction name
        
    Returns:
        -1 (hostile), 0 (neutral), or 1 (allied)
    """
    if faction1 == faction2:
        return 1  # Same faction = allied
    
    # Check direct relation
    relation = FACTION_RELATIONS.get((faction1, faction2))
    if relation is not None:
        return relation
    
    # Check reverse
    relation = FACTION_RELATIONS.get((faction2, faction1))
    if relation is not None:
        return relation
    
    # Default to neutral
    return 0


def get_faction_relations_text(speaker_faction: str, mentioned_factions: set[str]) -> str:
    """Generate faction relations text for prompts.
    
    Args:
        speaker_faction: Speaker's faction (technical ID)
        mentioned_factions: Set of faction IDs mentioned in events
        
    Returns:
        Formatted faction relations text with display names
    """
    if not mentioned_factions:
        return ""
    
    lines = []
    
    for faction in mentioned_factions:
        if faction == speaker_faction or faction == "unknown":
            continue
        
        relation = get_faction_relation(speaker_faction, faction)
        speaker_name = resolve_faction_name(speaker_faction)
        faction_name = resolve_faction_name(faction)
        
        if relation == -1:
            lines.append(f"HOSTILE: {speaker_name} - {faction_name}")
        elif relation == 1:
            lines.append(f"ALLIED: {speaker_name} - {faction_name}")
        # Neutral relations omitted for brevity
    
    return "\n".join(lines) if lines else ""


# ---------------------------------------------------------------------------
# Dynamic faction relation thresholds & labels
# ---------------------------------------------------------------------------

# Faction-pair relation thresholds (from game_relations.script)
FACTION_RELATION_THRESHOLDS = {
    "Allied": 1000,   # >= 1000
    "Hostile": -1000,  # <= -1000
    # Between = Neutral
}

# Player goodwill tiers matching PDA display (ordered highest-first)
# Positive tiers use >= (spec: >= 2000, >= 1500, etc.)
# Negative tiers use > (spec: > -500, > -1000, etc.) → mapped to >= with +1 for integers
GOODWILL_TIERS: list[tuple[int, str]] = [
    (2000, "Excellent"),
    (1500, "Brilliant"),
    (1000, "Great"),
    (500, "Good"),
    (-499, "Neutral"),   # > -500 → >= -499 for integers
    (-999, "Bad"),       # > -1000 → >= -999
    (-1499, "Awful"),    # > -1500 → >= -1499
    (-1999, "Dreary"),   # > -2000 → >= -1999
    # <= -2000 → Terrible (fallback)
]


def label_faction_relation(value: int) -> str:
    """Label a faction-pair relation value.

    Args:
        value: Raw integer from ``relation_registry.community_relation()``.

    Returns:
        ``"Allied"``, ``"Hostile"``, or ``"Neutral"``.
    """
    if value >= FACTION_RELATION_THRESHOLDS["Allied"]:
        return "Allied"
    if value <= FACTION_RELATION_THRESHOLDS["Hostile"]:
        return "Hostile"
    return "Neutral"


def label_goodwill(value: int) -> str:
    """Label a player goodwill value using PDA-style tiers.

    Args:
        value: Raw integer from ``actor:community_goodwill()``.

    Returns:
        Tier label string (e.g. ``"Excellent"``, ``"Neutral"``, ``"Terrible"``).
    """
    for threshold, label in GOODWILL_TIERS:
        if value >= threshold:
            return label
    return "Terrible"


# ---------------------------------------------------------------------------
# Formatters for prompt injection
# ---------------------------------------------------------------------------

def format_faction_standings(
    faction_standings: dict[str, int] | None,
    relevant_factions: set[str] | None = None,
) -> str:
    """Format faction-pair standings into prompt text.

    Args:
        faction_standings: Flat dict of ``"factionA_factionB"`` → int.
        relevant_factions: If provided, only pairs where at least one
            faction is in this set are included.

    Returns:
        Formatted text with one line per pair, or empty string.
    """
    if not faction_standings:
        return ""

    lines: list[str] = []
    for key in sorted(faction_standings):
        value = faction_standings[key]
        parts = key.split("_", 1)
        if len(parts) != 2:
            continue
        a, b = parts

        if relevant_factions is not None:
            if a not in relevant_factions and b not in relevant_factions:
                continue

        name_a = resolve_faction_name(a)
        name_b = resolve_faction_name(b)
        label = label_faction_relation(value)
        lines.append(f"{name_a}\u2194{name_b}: {label}")

    return "\n".join(lines)


def format_player_goodwill(
    player_goodwill: dict[str, int] | None,
    relevant_factions: set[str] | None = None,
) -> str:
    """Format per-faction player goodwill into prompt text.

    Args:
        player_goodwill: Dict of ``faction_id`` → int.
        relevant_factions: If provided, only matching factions are included.

    Returns:
        Formatted text with one line per faction, or empty string.
    """
    if not player_goodwill:
        return ""

    lines: list[str] = []
    for faction_id in sorted(player_goodwill):
        if relevant_factions is not None and faction_id not in relevant_factions:
            continue
        value = player_goodwill[faction_id]
        name = resolve_faction_name(faction_id)
        sign = "+" if value >= 0 else ""
        label = label_goodwill(value)
        lines.append(f"{name}: {sign}{value} ({label})")

    return "\n".join(lines)


# Companion faction tension note — injected into system prompt
COMPANION_FACTION_TENSION_NOTE = (
    "Faction hostilities apply to your attitude and dialogue, not just combat. "
    "Even if you are travelling as a companion and are mechanically safe from a "
    "hostile faction, you still hold your faction's opinions about them."
)

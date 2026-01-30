"""Faction data and relations.

Ports faction information from Lua's infra/STALKER/factions.lua.
"""

# Faction descriptions
FACTION_DESCRIPTIONS = {
    "stalker": "Independent stalkers (Loners) who survive in the Zone through scavenging, artifact hunting, and odd jobs. No central leadership, just mutual aid.",
    "Duty": "A paramilitary faction dedicated to containing and eventually destroying the Zone. Strict discipline, military hierarchy, hostile to Freedom.",
    "Freedom": "A faction of anarchists and idealists who believe the Zone should be open to all. Relaxed, drug-friendly, hostile to Duty.",
    "Bandit": "Criminals and thugs who prey on other stalkers. No honor among thieves.",
    "Army": "Ukrainian military forces tasked with securing the Zone perimeter. Shoot unauthorized personnel on sight.",
    "Ecolog": "Scientists studying the Zone's anomalies and artifacts. Typically non-combatant, protected by guards.",
    "Mercenary": "Professional soldiers for hire. No ideology, just money. Will work for anyone who pays.",
    "Monolith": "Fanatical cultists who worship the Monolith and protect the center of the Zone. Extremely dangerous, near-mindless zealots.",
    "Clear Sky": "A scientific faction studying the Zone. Once prominent, now diminished after the second emission.",
    "Renegade": "Outcasts and criminals, even more desperate than Bandits. Bottom of the Zone's hierarchy.",
    "Sin": "A mysterious faction of Zone-worshipping zealots, distinct from but similar to Monolith.",
    "ISG": "International military forces operating covertly in the Zone. Well-equipped and professional.",
    "Zombied": "Stalkers whose minds have been destroyed by psy-emissions. Shambling husks of their former selves.",
    "Monster": "Mutated creatures of the Zone. Not a faction per se, but universally hostile.",
    "Trader": "Merchants who buy and sell goods throughout the Zone. Typically neutral.",
}


def get_faction_description(faction: str) -> str:
    """Get description for a faction.
    
    Args:
        faction: Faction name
        
    Returns:
        Faction description or empty string
    """
    return FACTION_DESCRIPTIONS.get(faction, "")


# Faction relations (from game data)
# Values: -1 = hostile, 0 = neutral, 1 = friendly/allied
FACTION_RELATIONS = {
    ("Duty", "Freedom"): -1,
    ("Duty", "Bandit"): -1,
    ("Duty", "Monolith"): -1,
    ("Duty", "Renegade"): -1,
    ("Duty", "Army"): 0,
    ("Duty", "stalker"): 0,
    ("Duty", "Ecolog"): 1,
    
    ("Freedom", "Duty"): -1,
    ("Freedom", "Bandit"): 0,
    ("Freedom", "Monolith"): -1,
    ("Freedom", "Army"): -1,
    ("Freedom", "stalker"): 1,
    ("Freedom", "Clear Sky"): 0,
    
    ("Army", "stalker"): -1,
    ("Army", "Bandit"): -1,
    ("Army", "Freedom"): -1,
    ("Army", "Monolith"): -1,
    ("Army", "Duty"): 0,
    ("Army", "Ecolog"): 1,
    
    ("Bandit", "stalker"): -1,
    ("Bandit", "Duty"): -1,
    ("Bandit", "Army"): -1,
    ("Bandit", "Renegade"): 0,
    
    ("Monolith", "stalker"): -1,
    ("Monolith", "Duty"): -1,
    ("Monolith", "Freedom"): -1,
    ("Monolith", "Army"): -1,
    ("Monolith", "Ecolog"): -1,
    ("Monolith", "Mercenary"): -1,
    
    ("Ecolog", "stalker"): 0,
    ("Ecolog", "Duty"): 1,
    ("Ecolog", "Army"): 1,
    
    ("Mercenary", "stalker"): 0,
    ("Mercenary", "Bandit"): 0,
    
    ("Renegade", "stalker"): -1,
    ("Renegade", "Bandit"): 0,
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
        speaker_faction: Speaker's faction
        mentioned_factions: Set of faction names mentioned in events
        
    Returns:
        Formatted faction relations text
    """
    if not mentioned_factions:
        return ""
    
    lines = []
    
    for faction in mentioned_factions:
        if faction == speaker_faction or faction == "unknown":
            continue
        
        relation = get_faction_relation(speaker_faction, faction)
        
        if relation == -1:
            lines.append(f"HOSTILE: {speaker_faction} - {faction}")
        elif relation == 1:
            lines.append(f"ALLIED: {speaker_faction} - {faction}")
        # Neutral relations omitted for brevity
    
    return "\n".join(lines) if lines else ""

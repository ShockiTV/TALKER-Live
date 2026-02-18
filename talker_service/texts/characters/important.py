# fmt: off
"""Important characters registry for world state context.

Characters are categorized by role:
- Leader: Faction leaders (always shown if dead)
- Important: Major story characters (always shown if dead)
- Notable: Recurring characters (shown if dead AND relevant to context)
"""

from typing import TypedDict, Optional


class ImportantCharacter(TypedDict, total=False):
    """Character entry in the important characters registry."""
    ids: list[str]  # Story IDs (game's unique identifiers)
    name: str  # Primary display name
    names: list[str]  # Alternative names (for matching)
    role: str  # "leader" | "important" | "notable"
    faction: str  # Faction ID
    area: str  # Optional location ID (e.g., "l01_escape")
    areas: list[str]  # Optional multiple areas
    description: str  # Brief description


# Important characters registry
# Ported from TALKER-fork/bin/lua/infra/STALKER/world_state.lua
CHARACTERS: list[ImportantCharacter] = [
    # ========== FACTION LEADERS ==========
    {
        "ids": ["agr_smart_terrain_1_6_near_2_military_colonel_kovalski"],
        "name": "Colonel Kuznetsov",
        "role": "leader",
        "faction": "army",
    },
    {
        "ids": ["bar_dolg_leader"],
        "name": "General Voronin",
        "role": "leader",
        "faction": "dolg",
    },
    {
        "ids": ["mil_smart_terrain_7_7_freedom_leader_stalker"],
        "name": "Lukash",
        "role": "leader",
        "faction": "freedom",
    },
    {
        "ids": ["mar_smart_terrain_base_stalker_leader_marsh"],
        "name": "Cold",
        "role": "leader",
        "faction": "csky",
    },
    {
        "ids": ["yan_stalker_sakharov"],
        "name": "Sakharov",
        "role": "leader",
        "faction": "ecolog",
    },
    {
        "ids": ["cit_killers_merc_trader_stalker"],
        "name": "Dushman",
        "role": "leader",
        "faction": "killer",
    },
    {
        "ids": ["zat_b7_bandit_boss_sultan"],
        "name": "Sultan",
        "role": "leader",
        "faction": "bandit",
    },
    {
        "ids": ["lider_monolith_haron"],
        "name": "Charon",
        "role": "leader",
        "faction": "monolith",
    },
    {
        "ids": ["kat_greh_sabaoth", "gen_greh_sabaoth", "sar_greh_sabaoth"],
        "name": "Chernobog",
        "role": "leader",
        "faction": "greh",
    },
    {
        "ids": ["ds_domik_isg_leader", "jup_depo_isg_leader"],
        "name": "Major Hernandez",
        "role": "leader",
        "faction": "isg",
    },
    # ========== IMPORTANT CHARACTERS ==========
    {
        "ids": ["esc_m_trader", "m_trader", "esc_2_12_stalker_trader"],
        "name": "Sidorovich",
        "role": "important",
        "faction": "trader",
        "area": "l01_escape",
    },
    {
        "ids": ["lost_stalker_strelok", "stalker_strelok_hb", "stalker_strelok_oa"],
        "name": "Strelok",
        "role": "important",
        "faction": "stalker",
        "area": "pripyat",
    },
    {
        "ids": ["army_degtyarev", "army_degtyarev_jup"],
        "name": "Colonel Degtyarev",
        "names": ["Colonel Degtyarev", "Degtyarev"],
        "role": "important",
        "faction": "army",
        "description": "a legendary stalker and undercover agent of the Security Service of Ukraine, head of Operation Afterglow",
        "areas": ["zaton", "jupiter"],
    },
    {
        "ids": ["zat_a2_stalker_barmen"],
        "name": "Beard",
        "role": "important",
        "faction": "stalker",
        "description": "owner and bartender at the Skadovsk in Zaton and de facto leader of the stalkers in the north",
        "area": "zaton",
    },
    {
        "ids": ["esc_2_12_stalker_nimble", "zat_a2_stalker_nimble"],
        "name": "Nimble",
        "role": "important",
        "faction": "stalker",
        "description": "smuggler and rare weapons dealer",
        "area": "zaton",
    },
    {
        "ids": ["bar_visitors_barman_stalker_trader"],
        "name": "Barkeep",
        "role": "important",
        "faction": "trader",
        "description": "barkeep at the 100 Rads bar in Rostok",
        "area": "l05_bar",
    },
    {
        "ids": ["bar_arena_manager"],
        "name": "Arnie",
        "role": "important",
        "faction": "trader",
        "description": "manager and owner of the Arena in Rostok",
        "area": "l05_bar",
    },
    {
        "ids": ["bar_dolg_general_petrenko_stalker"],
        "name": "Colonel Petrenko",
        "names": ["Colonel Petrenko", "Petrenko"],
        "role": "important",
        "faction": "dolg",
        "description": "Colonel and head recruiter of the Duty faction",
        "area": "l05_bar",
    },
    {
        "ids": ["yan_ecolog_kruglov"],
        "name": "Professor Kruglov",
        "names": ["Professor Kruglov", "Kruglov"],
        "role": "important",
        "faction": "ecolog",
        "description": "Ecolog scientist at the Yantar lab",
        "area": "l08_yantar",
    },
    {
        "ids": ["jup_b6_scientist_nuclear_physicist"],
        "name": "Professor Hermann",
        "role": "important",
        "faction": "ecolog",
        "description": "Ecolog chief scientist at the Jupiter lab",
        "area": "jupiter",
    },
    {
        "ids": ["stalker_gatekeeper"],
        "name": "Gatekeeper",
        "role": "important",
        "faction": "stalker",
        "description": "guardian against Monolith forces at the Barrier in northern Army Warehouses",
        "area": "l07_military",
    },
    {
        "ids": ["red_forester_tech"],
        "name": "Forester",
        "role": "important",
        "faction": "stalker",
        "description": "mysterious hermit living in the Red Forest",
        "area": "l10_red_forest",
    },
    # ========== NOTABLE CHARACTERS ==========
    {
        "ids": ["esc_2_12_stalker_wolf"],
        "name": "Wolf",
        "role": "notable",
        "faction": "stalker",
        "description": "Head of security for stalkers at Rookie Village in Cordon",
        "area": "l01_escape",
    },
    {
        "ids": ["esc_2_12_stalker_fanat"],
        "name": "Fanatic",
        "role": "notable",
        "faction": "stalker",
        "description": "Second in command in Rookie Village in Cordon, in charge of teaching new rookies",
        "area": "l01_escape",
    },
    {
        "ids": ["devushka"],
        "name": "Hip",
        "role": "notable",
        "faction": "stalker",
        "description": "a young girl who was hanging around Rookie Village in Cordon",
        "area": "l01_escape",
    },
    {
        "ids": ["hunter_gar_trader"],
        "name": "Butcher",
        "role": "notable",
        "faction": "trader",
        "description": "Mutant hunter and trader in Garbage offering good money for mutant parts",
        "area": "l02_garbage",
    },
    {
        "ids": ["stalker_duty_girl"],
        "name": "Anna",
        "role": "notable",
        "faction": "dolg",
        "description": "a young girl who recently joined Duty after her father died to a chimera",
        "area": "l05_bar",
    },
    {
        "ids": ["bar_zastava_2_commander"],
        "name": "Sergeant Kitsenko",
        "names": ["Sergeant Kitsenko", "Kitsenko"],
        "role": "notable",
        "faction": "dolg",
        "description": "captain of the Duty guardpost at the north of Rostok",
        "area": "l05_bar",
    },
    {
        "ids": ["bar_duty_security_squad_leader"],
        "name": "Captain Gavrilenko",
        "names": ["Captain Gavrilenko", "Gavrilenko"],
        "role": "notable",
        "faction": "dolg",
        "description": "captain of the Duty guardpost at the south of Rostok",
        "area": "l05_bar",
    },
    {
        "ids": ["mil_smart_terrain_7_10_freedom_trader_stalker"],
        "name": "Skinflint",
        "role": "notable",
        "faction": "freedom",
        "description": "trader at the Freedom HQ",
        "area": "l07_military",
    },
    {
        "ids": ["monolith_eidolon"],
        "name": "Eidolon",
        "role": "notable",
        "faction": "monolith",
        "description": "legendary Monolith soldier who reactivated the Brain Scorcher in Radar after Strelok disabled it",
        "area": "pripyat",
    },
    {
        "ids": ["zat_b30_owl_stalker_trader"],
        "name": "Owl",
        "role": "notable",
        "faction": "trader",
        "description": "trader at the Skadovsk in Zaton",
        "area": "zaton",
    },
    {
        "ids": ["jup_a6_freedom_leader"],
        "name": "Loki",
        "role": "notable",
        "faction": "freedom",
        "description": "Lukash's second-in-command and leader of the Freedom faction in Jupiter",
        "area": "jupiter",
    },
    {
        "ids": ["guid_jup_stalker_garik"],
        "name": "Garry",
        "role": "notable",
        "faction": "stalker",
        "description": "guide at Yanov Station in Jupiter",
        "area": "jupiter",
    },
    {
        "ids": ["jup_a6_stalker_barmen"],
        "name": "Hawaiian",
        "role": "notable",
        "faction": "stalker",
        "description": "barman at the Yanov Station in Jupiter",
        "area": "jupiter",
    },
    {
        "ids": ["stalker_rogue", "stalker_rogue_ms", "stalker_rogue_oa"],
        "name": "Rogue",
        "role": "notable",
        "faction": "stalker",
        "description": "stalker in Strelok's group",
        "areas": ["zaton", "pripyat"],
    },
    {
        "ids": ["stalker_stitch", "stalker_stitch_ms", "stalker_stitch_oa"],
        "name": "Stitch",
        "role": "notable",
        "faction": "stalker",
        "description": "stalker in Strelok's group",
        "area": "pripyat",
    },
]


def get_all_story_ids() -> list[str]:
    """Get all story IDs from all characters (flattened)."""
    ids = []
    for char in CHARACTERS:
        ids.extend(char.get("ids", []))
    return ids


def get_leaders() -> list[ImportantCharacter]:
    """Get all faction leader characters."""
    return [c for c in CHARACTERS if c.get("role") == "leader"]


def get_important() -> list[ImportantCharacter]:
    """Get all important (non-leader) characters."""
    return [c for c in CHARACTERS if c.get("role") == "important"]


def get_notable() -> list[ImportantCharacter]:
    """Get all notable characters."""
    return [c for c in CHARACTERS if c.get("role") == "notable"]


def get_character_by_id(story_id: str) -> Optional[ImportantCharacter]:
    """Find a character by any of their story IDs."""
    for char in CHARACTERS:
        if story_id in char.get("ids", []):
            return char
    return None

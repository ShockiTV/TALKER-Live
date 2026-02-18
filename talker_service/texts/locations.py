"""Location name mappings for STALKER zones.

Maps technical location IDs (e.g., 'l01_escape') to human-readable names (e.g., 'Cordon').
"""

# Mapping of technical names to human-readable names
LOCATION_NAMES: dict[str, str] = {
    "jupiter": "Jupiter",
    "jupiter_underground": "Jupiter Underground",
    "k00_marsh": "Great Swamps",
    "k01_darkscape": "Darkscape",
    "k02_trucks_cemetery": "Trucks Cemetery",
    "l01_escape": "Cordon",
    "l02_garbage": "Garbage",
    "l03_agroprom": "Agroprom",
    "l04_darkvalley": "Dark Valley",
    "l05_bar": "Rostok",
    "l06_rostok": "Wild Territory",
    "l07_military": "Army Warehouses",
    "l08_yantar": "Yantar",
    "l09_deadcity": "Dead City",
    "l10_limansk": "Limansk",
    "l10_radar": "Radar",
    "l10_red_forest": "Red Forest",
    "l11_pripyat": "Pripyat",
    "labx8": "Lab X8",
    "pripyat": "Pripyat Outskirts",
    "zaton": "Zaton",
    "y04_pole": "The Meadow",
    "l10u_bunker": "Lab X-19",
    "l12u_control_monolith": "Monolith Control Center",
    "l12u_sarcofag": "Sarcophagus",
    "l13u_warlab": "Monolith War Lab",
    "l03u_agr_underground": "Agroprom Underground",
    "l04u_labx18": "Lab X-18",
    "l08u_brainlab": "Lab X-16",
    "l12_stancia": "Chernobyl NPP",
    "l12_stancia_2": "Chernobyl NPP",
    "l13_generators": "Generators",
    "poselok_ug": "'Yuzhniy' Town",
    "promzona": "Promzone",
    "grimwood": "Grimwood",
    "collaider": "Collider",
    "bunker_a1": "Bunker A1",
}


def get_location_name(technical_id: str) -> str:
    """Resolve technical location ID to human-readable name.
    
    Args:
        technical_id: Technical location ID (e.g., 'l01_escape')
        
    Returns:
        Human-readable name (e.g., 'Cordon'), or the original ID if not found
    """
    if not technical_id:
        return ""
    
    # Try exact match first
    if technical_id in LOCATION_NAMES:
        return LOCATION_NAMES[technical_id]
    
    # Try lowercase
    lower_id = technical_id.lower()
    if lower_id in LOCATION_NAMES:
        return LOCATION_NAMES[lower_id]
    
    # Return original if no match found
    return technical_id

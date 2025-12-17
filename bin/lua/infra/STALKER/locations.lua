require('infra.STALKER.factions')

-- Custom string formatter that handles faction tags
local function format_description(str, beholder)
    -- Replace %faction_name% with the faction description
    return str:gsub("%%(%w+)%%", function(faction_name)
        return describe_faction(faction_name, beholder)
    end)
end

-- Mapping of technical names to human-readable names
local LOCATION_NAMES = {
    jupiter = "Jupiter",jupiter_underground = "Jupiter Underground",k00_marsh = "Great Swamps",k01_darkscape = "Darkscape",k02_trucks_cemetery = "Trucks Cemetery",l01_escape = "Cordon",l02_garbage = "Garbage",l03_agroprom = "Agroprom",l04_darkvalley = "Dark Valley",l05_bar = "Rostok",l06_rostok = "Wild Territory",l07_military = "Military Warehouses",l08_yantar = "Yantar",l09_deadcity = "Dead City",l10_limansk = "Limansk",l10_radar = "Radar",l10_red_forest = "Red Forest",l11_pripyat = "Pripyat",labx8 = "Lab X8",pripyat = "Pripyat Outskirts",zaton = "Zaton",y04_pole = "The Meadow",-- Special areas
    l10u_bunker = "Lab X-19",l12u_control_monolith = "Monolith Control Center",l12u_sarcofag = "Sarcophagus",l13u_warlab = "Monolith War Lab",l03u_agr_underground = "Agroprom Underground",l04u_labx18 = "Lab X-18",l08u_brainlab = "Lab X-16",l12_stancia = "Chernobyl NPP",l12_stancia_2 = "Chernobyl NPP",l13_generators = "Generators",poselok_ug = "'Yuzhniy' Town",promzona = "Promzone",grimwood = "Grimwood" 
}

-- Detailed location descriptions with faction tags
local LOCATION_DESCRIPTIONS = {
    jupiter = "Jupiter, a large area west of Pripyat with Yanov Station at its heart, frequented by %stalker% and %ecolog%. Known for its scientific significance and dangerous mutants.",
    jupiter_underground = "Jupiter Underground, a series of secretive tunnels filled with poisonous gases and dangerous mutants.",
    k00_marsh = "Great Swamps, a murky and irradiated area with a %csky% base in the south-west and a significant %renegade% presence.",
    k01_darkscape = "Darkscape, a narrow valley connecting the Cordon to Dark Valley, known for its remote nature and dense forests. Most stalkers avoid it due to this.",
    k02_trucks_cemetery = "Trucks Cemetery, a vast scrapyard full of irradiated vehicles from the 1986 disaster, now a mutant breeding ground.",
    l01_escape = "Cordon, the Zone's antechamber mostly populated by %stalker% rookies with a small presence in the south by the %army%. A common entry point for rookies.",
    l02_garbage = "Garbage, a machinery graveyard and battleground for various factions, including %bandit%s and %stalker%s.",
    l03_agroprom = "Agroprom, a heavily contaminated area with a %army% HQ and dark, dangerous secrets in its underground.",
    l04_darkvalley = "Dark Valley, known for its %bandit% stronghold and the ominous underground lab, a place of horrific experiments.",
    l05_bar = "Rostok, an industrial area repurposed by %dolg% as their main base, hosting the famous 100Rads Bar and Arnie's Arena.",
    l06_rostok = "Wild Territory, located just west of Rostok. Usually has a %killer% presence in key sniper locations as well as some mutants. The location is sprawled with many derelict buildings, trains, and factory equipment long since abandoned.",
    l07_military = "Military Warehouses, a deserted army base and %freedom%'s HQ, defending against %monolith% forces.",
    l08_yantar = "Yantar, a location haunted by mutants and the %ecolog%'s base of operations for Zone research.",
    l09_deadcity = "Dead City, a crumbling ruin partially controlled by %killer%s despite constant %monolith% and mutant invasions.",
    l10_limansk = "Limansk, a secret research city, now a desolate ghost town and a passage for those braving the Zone's north.",
    l10_radar = "Radar, home to the Brain Scorcher and a territory fiercely guarded by the %monolith% faction.",
    l10_red_forest = "Red Forest, a dangerous area with a high mutant activity and a significant %monolith% presence.",
    l11_pripyat = "Pripyat, a dangerous ghost town near the Chernobyl NPP, predominantly controlled by %monolith%.",
    labx8 = "Lab X8, an underground lab focusing on psy-fields and noosphere research, now sought after by %killer%s.",
    pripyat = "Pripyat Outskirts, a remote part of the city with minimal human presence, mostly %monolith% and Zombified Stalkers.",
    zaton = "Zaton, a swamp-like area with the remains of numerous boats and barges, and a hub for various stalker settlements.",
    y04_pole = "The Meadow, a relatively calm area with occasional %bandit% presence, away from the main conflicts of the Zone. Most stalkers find it calm but eerie.",
    poselok_ug = "'Yuzhniy' Town, a ghost town with seemingly no history or evidence that it ever existed. After a massive emission, the empty field between Garbage and Truck Cemetery suddenly revealed the town now named 'Yuzhniy'.",
    promzona = "Promzone, an abandoned train station originally used after the 1986 disaster to transport radioactive garbage from the Northern Regions to the Truck Cemetery, and eventually to Garbage.",
    grimwood = "Grimwood, a region of the forest between the Army Warehouses and the Dead City. Full of mutants and deadly anomalies and with little human life present, making it a good hiding place for those wanting to disappear.",
    -- Special areas
    l10u_bunker = "Lab X-19, containing the 'Brain Scorcher' mechanism, heavily guarded by the %monolith%.",
    l12u_control_monolith = "%monolith% Control Center, a vital part of the Sarcophagus filled with computing machines, maintained by the %monolith%.",
    l12u_sarcofag = "Sarcophagus, the internal structure of the Chernobyl NPP's Reactor 4, shrouded in legends and heavily guarded by the %monolith%.",
    l13u_warlab = "%monolith% War Lab, formerly the accommodations of the C-Consciousness, now a sacred site maintained by the %monolith%.",
    l03u_agr_underground = "Agroprom Underground, a network of scientific and utility tunnels beneath Agroprom, now a haunt for mutants and the desperate.",
    l04u_labx18 = "Lab X-18, a facility of dark rumors and dangerous experiments, now a perilous destination for stalkers.",
    l08u_brainlab = "Lab X-16, home of the 'Miracle Machine', a psy-emitter turning trespassers into zombies.",
    l12_stancia = "Chernobyl NPP, the site of the Zone's creation and the heart of the %monolith%'s territory.",
    l12_stancia_2 = "Chernobyl NPP, continuing the journey through the nuclear power plant and its mysterious surroundings.",
    l13_generators = "Generators, the birthplace of the Zone and the site of the C-Consciousness project."
}

-- Simple function to get location name
function get_location_name(technical_location_name)
    return LOCATION_NAMES[technical_location_name] or technical_location_name
end

-- Function to get faction name
function describe_faction(technical_location_name, beholder)
    return get_faction_name(technical_location_name)
end

-- Function to get detailed location description
function describe_location_detailed(technical_location_name, beholder)
    local description = LOCATION_DESCRIPTIONS[technical_location_name]
    if description then
        return format_description(description, beholder)
    end
    
    -- Fallback for unknown locations
    local name = get_location_name(technical_location_name)
    return name .. " - A location within the Zone."
end

-- Return the module
return {
    get_location_name = get_location_name,describe_location_detailed = describe_location_detailed,describe_faction = describe_faction
}

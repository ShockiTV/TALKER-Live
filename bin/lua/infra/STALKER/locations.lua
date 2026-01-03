require("infra.STALKER.factions")

-- Custom string formatter that handles faction tags
local function format_description(str, beholder)
	-- Replace %faction_name% with the faction description
	return str:gsub("%%(%w+)%%", function(faction_name)
		return describe_faction(faction_name, beholder)
	end)
end

-- Mapping of technical names to human-readable names
local LOCATION_NAMES = {
	jupiter = "Jupiter",
	jupiter_underground = "Jupiter Underground",
	k00_marsh = "Great Swamps",
	k01_darkscape = "Darkscape",
	k02_trucks_cemetery = "Trucks Cemetery",
	l01_escape = "Cordon",
	l02_garbage = "Garbage",
	l03_agroprom = "Agroprom",
	l04_darkvalley = "Dark Valley",
	l05_bar = "Rostok",
	l06_rostok = "Wild Territory",
	l07_military = "Army Warehouses",
	l08_yantar = "Yantar",
	l09_deadcity = "Dead City",
	l10_limansk = "Limansk",
	l10_radar = "Radar",
	l10_red_forest = "Red Forest",
	l11_pripyat = "Pripyat",
	labx8 = "Lab X8",
	pripyat = "Pripyat Outskirts",
	zaton = "Zaton",
	y04_pole = "The Meadow", -- Special areas
	l10u_bunker = "Lab X-19",
	l12u_control_monolith = "Monolith Control Center",
	l12u_sarcofag = "Sarcophagus",
	l13u_warlab = "Monolith War Lab",
	l03u_agr_underground = "Agroprom Underground",
	l04u_labx18 = "Lab X-18",
	l08u_brainlab = "Lab X-16",
	l12_stancia = "Chernobyl NPP",
	l12_stancia_2 = "Chernobyl NPP",
	l13_generators = "Generators",
	poselok_ug = "'Yuzhniy' Town",
	promzona = "Promzone",
	grimwood = "Grimwood",
	collaider = "Collider",
	bunker_a1 = "Bunker A1",
}

-- Detailed location descriptions with faction tags
local LOCATION_DESCRIPTIONS = {
	jupiter = "Jupiter (a large area west of Pripyat and north of Red Forest) is known for its scientific significance and dangerous mutants. In the heart of Jupiter is Yanov Station, a settlement with heavy %stalker% and %freedom% presence providing a safe haven. Professor Hermann's bunker-like mobile lab is also located here, and Jupiter is frequented by %ecolog%s and daring and experienced %stalker%s.",
	jupiter_underground = "Jupiter Underground is a series of secretive tunnels said to connect Jupiter and Pripyat. They are filled with poisonous gases and dangerous mutants.",
	k00_marsh = "Great Swamps is a murky and irradiated area next to Cordon in the south-west with a %csky% base and a significant %renegade% presence.",
	k01_darkscape = "Darkscape is a narrow eastern valley connecting the Cordon to Dark Valley, known for its remote nature and dense forests. Most stalkers avoid it due to this.",
	k02_trucks_cemetery = "Trucks Cemetery is a vast scrapyard to the east of Rostok full of irradiated vehicles from the 1986 disaster. Both %bandit%s and dangerous mutants are often found here.",
	l01_escape = "Cordon (the Zone's antechamber and southernmost location) is an area at the southern edge of the Zone mostly populated by %stalker% rookies and weak mutants. There is a small %army% presence in the south, guarding the southern checkpoint with the aim of keeping the public out of the Zone. Most rookies enter the Zone by sneaking across the border into the Cordon.",
	l02_garbage = "Garbage (an area connecting the Cordon to Rostok) is an area where radioactive trash heaps and broken machinery from the 1986 disaster was dumped. It houses Butcher's shop in an old train depot, and its south-central location means roaming %stalker%s and %bandit%s are common.",
	l03_agroprom = "Agroprom (located west of Garbage and south of Yantar) is a heavily contaminated area with a %army% HQ and dark, dangerous secrets in its underground.",
	l04_darkvalley = "Dark Valley (located to the east of Garbage) is known for its %bandit% stronghold and the ominous underground Lab X-18, a place of horrific experiments.",
	l05_bar = "Rostok (an old industrial area north of Garbage) is repurposed by %dolg% as their main base. It's the largest and safest settlement in the Zone, hosting the famous 100 Rads Bar and Arnie's Arena.",
	l06_rostok = "Wild Territory (an area just west of Rostok) is sprawled with many derelict buildings, trains, and factory equipment long since abandoned. Usually has a %killer% presence in key sniper locations as well as dangerous mutants.",
	l07_military = "Army Warehouses (a deserted army base north of Rostok) is where %freedom%'s HQ is located. It's located between Rostok and Radar and frequently sees %monolith% forces invading from the north, defended by %freedom% and the venerable %stalker% called Gatekeeper.",
	l08_yantar = "Yantar (located in the center-west, between Agroprom and Dead City) is a location haunted by mutants and housing Lab X-16. Sakharov's bunker-like mobile lab in the middle of Lake Yantar is the %ecolog%'s base of operations for Zone research.",
	l09_deadcity = "Dead City (located in the center-west of the Zone) is a crumbling suburban ruin the Private Military Company called %killer% faction has made their stronghold and base of operations. Despite dangerous mutants roaming the area, %killer% patrols make the center of Dead City relatively safe for those on good terms with the faction.",
	l10_limansk = "Limansk (a secret research city located north of Dead City and west of Red Forest) is now a desolate ghost town. It's home to %monolith% forces and %killer% patrols, but those brave enough to navigate its labyrinthine streets find a passage leading to the north of the Zone.",
	l10_radar = "Radar (located just north of Army Warehouses) is an area in the very center of the Zone and a territory fiercely guarded by the %monolith% faction. It is home to the Brain Scorcher, a massive psy-installation turning unprotected stalkers travelling north of the border between Army Warehouses and Radar into zombies or brainwashed %monolith% soldiers.",
	l10_red_forest = "Red Forest (located between Radar and Limansk in the center of the Zone) is a region of a larger forest where the trees had their leaves turn red after absorbing heavy radiation during the 1986 disaster. It is home to dangerous mutants, many dangerous anomalies and a significant %monolith% presence. A mysterious independent %stalker% called Forester is rumoured to live on his own here.",
	l11_pripyat = "Pripyat (a dangerous ghost town near the Chernobyl NPP in the north) is home to dangerous mutants, and %monolith% forces roam its streets.",
	labx8 = "Lab X8 is an underground lab hidden under the streets of Pripyat in the north. Research focusing on psy-fields and the 'noosphere' was conducted here, which is now sought after by the %killer% faction.",
	pripyat = "Pripyat Outskirts is the outer part of the city of Pripyat located in the north of the Zone. There is minimal human presence. Dangerous mutants, %monolith% forces and zombified stalkers roam the streets.",
	zaton = "Zaton (located west of Pripyat and north of Jupiter) is a swamp-like area formed from a drained branch of the Pripyat River, housing the remains of numerous boats and barges in the drained riverbed. Beard's %stalker% settlement housed in the stranded remains of the tanker 'Skadovsk' is the northernmost safe haven for %stalker%s in the Zone.",
	y04_pole = "The Meadow (located east of Cordon) is a relatively calm area in the south-east of the Zone with occasional %bandit% presence, away from the main conflicts. Most stalkers find it calm but eerie.",
	poselok_ug = "Yuzhniy Town (located just south-east of Rostok between Garbage and Truck Cemetery) is a ghost town with seemingly no history or evidence that it ever existed. After a massive emission, a previously empty field suddenly revealed the town now named 'Yuzhniy'.",
	promzona = "Promzone (located in the center-east of the Zone, south of Radar and east of Army Warehouses) is an abandoned train station originally used after the 1986 disaster to transport radioactive garbage from the Northern Regions to the Truck Cemetery and Garbage.",
	grimwood = "Grimwood (located between the Dead City and the Army Warehouses) is the southern region of the same forest as Red Forest. Full of mutants and deadly anomalies and with little human life present, making it a good hiding place for those wanting to disappear.",
	-- Special areas
	collaider = "",
	bunker_a1 = "",
	l10u_bunker = "Lab X-19 contains the 'Brain Scorcher' mechanism and is heavily guarded by the %monolith%.",
	l12u_control_monolith = "The %monolith% Control Center is a vital part of the Sarcophagus filled with computing machines, maintained by the %monolith%.",
	l12u_sarcofag = "The Sarcophagus is the internal structure of the Chernobyl NPP's Reactor 4, shrouded in legends and heavily guarded by the %monolith%.",
	l13u_warlab = "The %monolith% War Lab formerly the accommodations of the C-Consciousness, is now a sacred site maintained by the %monolith%.",
	l03u_agr_underground = "Agroprom Underground is a network of scientific and utility tunnels beneath Agroprom, now a haunt for mutants and the desperate.",
	l04u_labx18 = "Lab X-18 is a facility of dark rumors and dangerous experiments, now a perilous destination for stalkers.",
	l08u_brainlab = "Lab X-16 is home of the 'Miracle Machine', a psy-emitter turning trespassers into zombies.",
	l12_stancia = "Chernobyl NPP (located in the far north of the Zone) is the site of the Zone's creation and the heart of the %monolith%'s territory.",
	l12_stancia_2 = "You continue the journey through the nuclear power plant and its mysterious surroundings.",
	l13_generators = "Generators (the very northernmost area of the Zone) is the birthplace of the Zone itself and the site of the C-Consciousness project.",
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
	get_location_name = get_location_name,
	describe_location_detailed = describe_location_detailed,
	describe_faction = describe_faction,
}

local logger = require("framework.logger")

local factions = {
	killer = {
		name = "Mercenary",
		description = "The Mercenary faction is a Private Military Company from the US operating in the Zone out of their HQ in the old Sports Center in Dead City. While entering the Zone to fulfill several top-secret government contracts, they also offer their services to whoever is willing to pay while here. They are tactical, mercenary, morally flexible, confident, casual and respect nobody except other mercenaries and the ISG faction. ",
	},
	dolg = {
		name = "Duty",
		description = "The Duty faction were founded by former members of the Ukranian army, and have an uneasy truce with the Army faction thanks to this and their shared goal of keeping civilians out of the Zone for their own good. Duty despise the Zone and want to protect people from it, with a long-term goal of destroying it for good, although in the short term they are focused on containing it. They are based in Rostok, and are locked in a long ideological and bloody conflict with Freedom. They have a strong sense of camaraderie and brotherhood within the faction, while acting disciplined, authoritative, brusque and emotionally strained towards members of other factions. ",
	},
	freedom = {
		name = "Freedom",
		description = "The Freedom faction are a predominantly anarchist group based in an old military base in the Army Warehouses next to Rostok. They are locked into a long ideological and bloody conflict with Duty. Freedom dislike authority and want the Zone to be open to all, believing the Zone neither could or should be destroyed and that further research and open access to its secrets would be of great benefit to humanity. Their members tend to be liberal, rebellious, relaxed and expressive. ",
	},
	bandit = {
		name = "Bandit",
		description = "The Bandits are a loose collection of gopnik and vatnik criminals currently ruled by Sultan and based out of the old factory in northern Dark Valley. Although some of their members are scavengers or artifact-hunters, the majority make a living by robbing or killing. They are mostly based in the south of the Zone, where rookie stalkers are their typical prey. They are vulgar and rude but like to crack jokes frequently, are opportunistic and lawless but often cowardly.",
	},
	monolith = {
		name = "Monolith",
		description = "The Monolith are a zealous and fanatical cult who worship the crystal 'Monolith' that lies at the heart of the Chernobyl NPP Reactor. They are not just brainwashed, but partially mind-controlled through psi-energies. They retain very little of their memories and personality from before their minds were taken over, generally acting as fervent, single-minded soldiers seeking to eradicate intruders from the Zone - being especially protective of the northern parts of it. ",
	},
	stalker = {
		name = "stalker",
		description = "The 'stalker' faction (also known as the 'Loners') are a loose faction of mostly independent individuals consisting of fortune-seekers, scavengers, artifact hunters and explorers. Their members entered the Zone illegally (e.g., by sneaking across the border, bribing a checkpoint guard etc.). Many are driven into the Zone out of desperation, although some are just thrill-seekers, fortune hunters or adventurers. They are plain-spoken, adaptive, optimistic, quietly authentic and emotionally scarred. ",
	},
	csky = {
		name = "Clear Sky",
		description = "Clear Sky are an independent paramilitary group with a scientific focus whose goal is to understand the Zone better. Their HQ 'Hidden Base' is located in the southern part of the Great Swamps - far from the other factions - and they tend to keep to themselves and avoid the faction politics in the center of the Zone. They have an ongoing conflict with the Renegade faction for territory in the swamps. They consist primarily of volunteers, and their members tend to be idealistic and driven, although cautious and emotionally fragile. ",
	},
	ecolog = {
		name = "Ecolog",
		description = "The Ecolog faction consists of scientists performing field research in The Zone, funded by the Ukrainian government and under the protection of the Ukrainian military. They are curious, open-minded, cautious and dislike violence. Most of them are woefully unprepared for the stresses and horrors of the Zone. ",
	},
	army = {
		name = "Army",
		description = "The Army faction are soldiers from the Ukranian army who are deployed to the Zone to keep the public out for their own safety, as well as to protect the government-funded scientists of the Ecolog faction. They are based out of Agroprom and are mostly active in the south, where they guard the perimiter of the Zone and have checkpoints set up to keep unauthorized people out. Some do venture further north, mainly to protect the Ecolog scientists doing field research. They have an uneasy truce and mutual understanding with the Duty faction, which contains many ex-soldiers and with whom they share the common goal of keeping civilians out of the Zone for their own good. Members of the Army faction tend to be reluctant, undisciplined, bitter and emotionally burned-out.",
	},
	renegade = {
		name = "Renegade",
		description = "The Renegades are violent criminals who have committed acts so despicable even the Bandit faction only barely tolerates them. They are based in the Great Swamps, where they are locked in a conflict for territory with Clear Sky. Their members are not just ruthless and violent but depraved, vile, crass, deplorable and erratic.",
	},
	trader = {
		name = "Trader",
		description = "The Traders are not a faction per se, but rather a term used to describe the faction-independent traders, merchants and service providers who work in the Zone selling goods and services to whoever is willing to pay. They avoid getting involved in faction politics, and are often seen as neutral. Most have a slightly greedy and opportunistic streak, and they tend to be persuasive, smooth-talking and not above using flattery to reel in customers. ",
	},
	greh = {
		name = "Sin",
		description = "The Sin are a religious sect, founded by the former prison inmate Chernobog who gained powers similar to a Controller mutant after being subjected to top-secret experiments in an underground lab in the Zone. Although Sin's interests are aligned with Monolith and they don't see each other as enemies, their beliefs differ. The Sin are not mind-controlled like the Monolith, and they don't worship the crystal - which they see a false illusion. Unlike Monolith they worship the **Zone itself**, which they believe to be of divine nature and see as humanity's path to ultimate redemption. Their goal is to make the Zone expand to one day cover the entire world. Some of their members are partly zombified, many others have been brainwashed by their charismatic leader Chernobog. Sin's members tend to be creepy, mystical and ritualistic. ",
	},
	isg = {
		name = "ISG",
		description = "The ISG, also called 'UNISG' (United Nations International Scientific Group), are an elite Spec Ops Recon unit under the United Nations gathering intel in the Zone. Despite their name indicating a scientific focus, they are a highly specialized military division whose purpose is to ensure the United Nations are always informed of the latest scientific findings worldwide, particularly as they relate to weapons and defense technology. While they do keep scientists at their HQ to interpret their findings, their field operatives are made up of elites handpicked and recruited into the ISG from various United Nations countries' special forces after proving themselves on active duty or passing a rigorous selection process. They are a small and tight-knit group watching out for each other, but are distrustful of other factions except Mercenaries. They are tactical and professional and treat people from non-Mercenary factions with elitism and hostility. ",
	},
	zombied = {
		name = "Zombied",
		description = "The Zombied are people zombified by psy energies to a mindless state where only fragments of memories and personality remains. Most are victims of psy-storms, though some are people who wandered into psy fields unprotected or ventured too close to the Brain Scorcher. A rare few of them are victims of Controller mutants. ",
	},
	monster = {
		name = "Monster",
		description = "The Monster faction are non-human mutants living in the zone. ",
	},
}
function get_faction_name(technical_name)
	-- Remove 'actor_' prefix if it exists
	local clean_name = technical_name:gsub("^actor_", "")
	local faction = factions[clean_name]
	if faction then
		return faction.name
	else
		return nil
	end
end

function get_faction_description(natural_name)
	for technical_name, faction in pairs(factions) do
		if faction.name == natural_name then
			return faction.description
		end
	end
	logger.debug("No faction found with name: " .. tostring(natural_name))
	return nil
end

return get_faction_name, get_faction_description

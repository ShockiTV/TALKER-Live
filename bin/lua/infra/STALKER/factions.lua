local logger = require('framework.logger')

local factions = {
    killer = {
        name = "Mercenary",
        style = "a member of the Mercenary faction, a Private Military Company from the US operating in the Zone where they offer their services to whoever is willing to pay. They are tactical, mercenary, morally flexible, confident, casual and respect nobody except other mercenaries and the UNISG. "
    },
    dolg = {
        name = "Duty",
        style = "a member of Duty, a faction that despises the Zone and wants to protect people from it. They are authoritarian, brusque and emotionally strained. "
    },
    freedom = {
        name = "Freedom",
        style = "a member of Freedom, a faction that dislikes authority and wants the Zone to be open to all. They are rebellious, relaxed and expressive. "
    },
    bandit = {
        name = "Bandit",
        style = "a member of the Bandit faction, a group of gopniks and a vatniks. They are vulgar and rude but like to crack jokes frequently, are opportunistic and lawless but often cowardly. "
    },
    monolith = {
        name = "Monolith",
        style = "a member of the Monolith faction. They are a brainwashed cult worshipping the Monolith and are fanatical, cryptic, zealous and emotionally void. They retain very little of their memories and personality from before their brainwashing. "
    },
    stalker = {
        name = "stalker",
        style = "a member of the Loner faction of scavengers, artifact hunters and explorers who are in the zone illegally. They are plain-spoken, adaptive, optimistic, quietly authentic and emotionally scarred. "
    },
    csky = {
        name = "Clear Sky",
        style = "a member of Clear Sky, a faction who want to understand the Zone better. They are idealistic, optimistic and cautious. "
    },
    ecolog = {
        name = "Ecolog",
        style = "a member of the Ecolog faction. They are scientists performing field research in The Zone and are curious, open-minded, cautious and dislike violence. " 
    },
    army = {
        name = "Army",
        style = "a member of the Army faction. They are soldiers in the Ukranian army who are deployed to the Zone to keep the public out for their own safety, as well as to protect the government-funded scientists of the Ecolog faction. They are reluctant, undisciplined, bitter and emotionally burned-out. Use military terminology, vernacular and slang. "
    },
    renegade = {
        name = "Renegade",
        style = "a member of the Renegade faction. They are violent criminals who have committed acts so despicable even the Bandit faction barely tolerates them. They are not just ruthless and violent but depraved, vile, crass, deplorable and erratic. Use explicit language. "
    },
    trader = {
        name = "Trader",
        style = "a trader and merchant and is persuasive, a little greedy and sometimes resorts to flattery. "
    },
    greh = {
        name = "Sin",
        style = "a member of the Sin faction, a religious sect of zombified stalkers worshipping the Zone. They believe the Zone is of divine nature and see it as humanity's path to ultimate redemption. They are creepy, possessed and ritualistic. "
    },
    isg = {
        name = "ISG",
        style = "a member the UNISG faction, an elite Spec Ops Recon unit under the United Nations gathering intel in the Zone. They are elitist, hostile, calculating and distrustful of other factions except Mercenaries. "
    },
    zombied = {
        name = "Zombied",
        style = "zombified by psy emissions to a mindless state where only fragments of memories and personality remains. Your response should be incoherent, groaning and barely intelligible. Make it sad and tragic. "
    },
    monster = {
        name = "Monster",
        style = "alien, cruel and emotionally surreal. "
    }
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

function get_faction_speaking_style(natural_name)
    for technical_name, faction in pairs(factions) do
        if faction.name == natural_name then
            return faction.style
        end
    end
    logger.warn("No faction found with name: " .. natural_name)
    return nil
end

return get_faction_name, get_faction_speaking_style

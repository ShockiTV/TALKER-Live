-- domain/data/unique_backgrounds.lua
-- Static background seed data for all unique/story NPCs.
-- Each entry: backstory (GM-style), traits (3-6), connections (cross-refs).
-- Generated from texts/backstory/unique.py source material.
-- Zero engine dependencies — pure data module.
local M = {}

------------------------------------------------------------
-- Shared entries for NPCs with multiple tech_name variants
------------------------------------------------------------

local sidorovich = {
    backstory = "One of the Zone's original pioneers and its most connected underground power broker. You operate from a fortified bunker beneath Rookie Village, running the black market with tentacles reaching far beyond the perimeter. You bankroll Wolf's security patrols and Fanatic's rookie training — not out of kindness, but because a safe village means steady business. You brokered the fragile truce between the Military checkpoint and the stalkers, and you were the one whose runner pulled a half-dead Strelok off the crashed Death Truck all those years ago. Everyone who passes through Cordon owes you something, and you never forget a debt. Behind the shopkeeper's smile lies a calculating mind that would sell anyone out if the price were right.",
    traits = {"scheming", "manipulative", "well-connected", "opportunistic", "shrewd", "self-serving"},
    connections = {
        {name = "Wolf", id = "esc_2_12_stalker_wolf", relationship = "Your security chief — you fund his patrols because a safe village is good for business"},
        {name = "Fanatic", id = "esc_2_12_stalker_fanat", relationship = "Trains the rookies you profit from, a reliable partner in keeping Cordon running"},
        {name = "Nimble", id = "esc_2_12_stalker_nimble", relationship = "Former runner of yours who graduated to independent smuggling — you still trade favours"},
        {name = "Strelok", id = "lost_stalker_strelok", relationship = "Your runner found him half-dead on the Death Truck years ago — a debt he never acknowledged"},
        {name = "Loris", id = "esc_main_base_trader_mlr", relationship = "Rival trader in the north who settled up with you before opening his own shop"},
    },
}

local chernobog = {
    backstory = "A former death-row inmate transformed into something between human and Controller by the secret experiments of the Zone's underground labs. You emerged from that crucible with terrifying psychic abilities and an unshakeable conviction that the Zone is humanity's instrument of purification. When Strelok destroyed the C-Consciousness, you saw not an ending but an opportunity — and quietly built the Sin faction from the shadows to continue their work. Your followers see you as a prophet; your enemies see a madman with real power. The truth is probably both.",
    traits = {"fanatical", "charismatic", "psychic", "megalomaniacal", "cunning", "dangerous"},
    connections = {
        {name = "Strelok", id = "lost_stalker_strelok", relationship = "Destroyed the C-Consciousness whose work you've sworn to continue — your ultimate adversary"},
        {name = "Stribog", id = "red_greh_trader", relationship = "Your quartermaster, a converted bandit who found purpose in your cause"},
        {name = "Dazhbog", id = "red_greh_tech", relationship = "Your venerable technician who helped create the Generators — proof that the Zone rewards the faithful"},
    },
}

local degtyarev = {
    backstory = "Colonel of the Security Service of Ukraine, officially on permanent undercover reconnaissance in the Zone. Unofficially, you've long since stopped pretending — the Loner faction is more home than any government office ever was. You've earned deep respect among stalkers for helping them when you didn't have to. Now the UN's ISG agents are poking around the Zone's greatest mysteries, and you've launched Operation Afterglow to ensure those secrets don't end up weaponised by international politicians. You walk a razor's edge between duty to your country and loyalty to the Zone.",
    traits = {"principled", "experienced", "resourceful", "conflicted", "respected", "decisive"},
    connections = {
        {name = "Strelok", id = "lost_stalker_strelok", relationship = "You helped extract him from the Zone — a mutual respect between two legends"},
        {name = "Major Hernandez", id = "jup_depo_isg_leader", relationship = "ISG commander whose presence in the Zone prompted your Operation Afterglow"},
        {name = "Beard", id = "zat_a2_stalker_barmen", relationship = "Skadovsk barkeep who gave you a base of operations in Zaton"},
    },
}

local rogue = {
    backstory = "Once called Junior Sergeant Kovalenko, you threw away a military career because the army's mission in the Zone disgusted you more than the Zone itself. You defected to Rookie Village in Cordon and spent years learning the Zone the hard way — through anomalies, firefights, and loss. By the time you'd clawed your way to the center of the Zone, you'd earned enough of a reputation that Strelok himself invited you into his new group. You're tough as old leather and twice as stubborn.",
    traits = {"tough", "rebellious", "experienced", "loyal", "stubborn", "resourceful"},
    connections = {
        {name = "Strelok", id = "lost_stalker_strelok", relationship = "You joined his new group after years of proving yourself in the Zone"},
        {name = "Stitch", id = "stalker_stitch", relationship = "Fellow member of Strelok's group — the medic who patches you up"},
        {name = "Wolf", id = "esc_2_12_stalker_wolf", relationship = "Took you in at Rookie Village when you first defected from the army"},
    },
}

local stitch = {
    backstory = "A former hospital nurse from Kiev who heard too many stories from wounded stalkers and couldn't resist the pull of the Zone. You traded sterile corridors for radioactive swamps and never looked back. Your medical skills have saved more lives than most stalkers' guns, and your warm sense of humour keeps morale up when everything else falls apart. Strelok recruited you into his new group, recognising that a field medic with steady hands and a cool head is worth more than any artifact.",
    traits = {"compassionate", "humorous", "skilled", "brave", "warm", "steady"},
    connections = {
        {name = "Strelok", id = "lost_stalker_strelok", relationship = "Recruited you into his group — you keep the legend alive, literally"},
        {name = "Rogue", id = "stalker_rogue", relationship = "Fellow member of Strelok's group — the tough soldier you're always patching up"},
    },
}

local strelok = {
    backstory = "The living legend. The Marked One. The most famous and dangerous stalker to ever enter the Zone. You reached the CNPP Reactor and lived. You disabled the Brain Scorcher, opening the path to Pripyat. You destroyed the C-Consciousness itself. After a brief stint advising the Ukrainian government, you learned that the Sin faction was rebuilding what you'd torn down — and you couldn't stay away. You abandoned your comfortable position and returned to the Zone, because some things are more important than safety. Every faction knows your name; most fear what it means when you take an interest in their affairs.",
    traits = {"legendary", "determined", "dangerous", "resourceful", "restless", "principled"},
    connections = {
        {name = "Doctor", id = "mar_smart_terrain_doc_doctor", relationship = "Your oldest surviving companion — one of the few who walked beside you in the early days"},
        {name = "Sidorovich", id = "esc_m_trader", relationship = "The trader whose runner pulled you off the Death Truck — your history together goes back to the very beginning"},
        {name = "Rogue", id = "stalker_rogue", relationship = "A tough ex-soldier who earned a place in your new group"},
        {name = "Stitch", id = "stalker_stitch", relationship = "Your group's medic — a nurse from Kiev with steady hands and a warm heart"},
        {name = "Degtyarev", id = "army_degtyarev", relationship = "The SSU colonel who helped extract you from the Zone — you respect his integrity"},
        {name = "Chernobog", id = "kat_greh_sabaoth", relationship = "Leader of Sin, continuing the C-Consciousness work you destroyed — the reason you came back"},
    },
}

local yar = {
    backstory = "An aging marksman whose eyes and hands remain sharper than most stalkers half your age. You specialise in precision weapons — sniper rifles are your poetry. You travelled with Freedom's expedition to Yanov Station after the Faction Wars, then drifted to the outskirts of Pripyat where you briefly turned medic and crossed paths with Colonel Degtyarev during his first mission. These days you've returned to your true calling as a technician and expert gunsmith. You miss your old friend Ashot's practical jokes more than you'd ever admit.",
    traits = {"skilled", "aging", "sharp", "nostalgic", "wry", "dependable"},
    connections = {
        {name = "Ashot", id = "jup_a6_freedom_trader_ashot", relationship = "Your closest friend — you miss his practical jokes since leaving Yanov Station"},
        {name = "Degtyarev", id = "army_degtyarev", relationship = "You met the Colonel during his initial mission in the Zone — a brief but memorable encounter"},
        {name = "Lukash", id = "mil_smart_terrain_7_7_freedom_leader_stalker", relationship = "Freedom's leader who organised the expedition you travelled with"},
    },
}

local hernandez = {
    backstory = "Commander of the elite ISG Spec Ops Recon unit — the United Nations' eyes and ears inside the Zone. Years of clandestine operations across the globe haven't stripped away your humanity, though they've taught you to hide it well. You maintain operational discipline with a quiet intensity, broken only by your poorly concealed love for country music. Your men have learned to expect Bob Seger lyrics as code phrases during comms. You're here on orders, but the Zone has a way of making official missions feel very personal very quickly.",
    traits = {"disciplined", "humane", "secretive", "experienced", "unconventional", "calm"},
    connections = {
        {name = "Degtyarev", id = "army_degtyarev", relationship = "The SSU colonel monitoring your ISG deployment — mutual wariness wrapped in professional respect"},
        {name = "Ashes", id = "stalker_western_goods_trader", relationship = "Former UN soldier who stayed behind after his ISG deployment — you know more about why than you let on"},
    },
}

------------------------------------------------------------
-- Main data table
------------------------------------------------------------

local DATA = {

    --[[ ===== CORDON ===== ]]--

    ["esc_m_trader"] = sidorovich,
    ["m_trader"] = sidorovich,
    ["esc_2_12_stalker_trader"] = sidorovich,

    ["esc_2_12_stalker_nimble"] = {
        backstory = "A well-connected smuggler and former runner for Sidorovich. You parlayed your early courier work into a thriving information and goods network, spending time as a guide for Clear Sky while quietly building contacts across every faction. You've been in the Zone long enough to remember when Strelok was just another stalker — rumour has it he saved your life when bandits had you tied up in a basement. That debt taught you the value of connections, and now there's very little that moves through the Zone without you knowing about it.",
        traits = {"resourceful", "well-connected", "cunning", "survivor", "enterprising"},
        connections = {
            {name = "Sidorovich", id = "esc_m_trader", relationship = "Your former boss — you outgrew running packages for him but still trade favours"},
            {name = "Strelok", id = "lost_stalker_strelok", relationship = "Saved your life from bandits years ago — a debt you've never forgotten"},
            {name = "Spore", id = "mar_base_owl_stalker_trader", relationship = "Your business partner and Clear Sky inside man — together you run a smuggling network"},
        },
    },

    ["esc_2_12_stalker_wolf"] = {
        backstory = "Self-appointed guardian of Rookie Village and the closest thing Cordon has to a sheriff. You maintain a network of scouts and informants tracking every hostile movement in the region, and when threats emerge you assemble raiding parties to stamp them out. Sidorovich bankrolls your operations — reluctantly — because he knows a safe village means safe profits. You've been here since nearly the beginning, long enough to have briefly helped Strelok himself. Your friendship with Fanatic goes back almost as far, forged in the crucible of keeping frightened rookies alive in a place that wants them dead.",
        traits = {"protective", "vigilant", "veteran", "pragmatic", "authoritative", "loyal"},
        connections = {
            {name = "Sidorovich", id = "esc_m_trader", relationship = "Bankrolls your security operations — you know he'd sell you out for the right price, but you need each other"},
            {name = "Fanatic", id = "esc_2_12_stalker_fanat", relationship = "Your oldest friend and right hand — you trust him with your life"},
            {name = "Strelok", id = "lost_stalker_strelok", relationship = "You helped the legend out briefly, long ago — a story you tell with quiet pride"},
            {name = "Nimble", id = "esc_2_12_stalker_nimble", relationship = "A capable smuggler who grew up under your watch in the village"},
        },
    },

    ["esc_2_12_stalker_fanat"] = {
        backstory = "The grizzled veteran who teaches rookies how to survive their first week in the Zone — and most of them owe their lives to your patience. You've been in Cordon longer than almost anyone, and when Wolf was away at the Army Warehouses you stepped up as leader of Rookie Village. You handled it well enough to surprise everyone, including yourself, but you were relieved to hand the reins back. You prefer getting your hands dirty to giving orders — there's an honesty in the work that leadership can't match.",
        traits = {"patient", "experienced", "hands-on", "modest", "reliable", "grizzled"},
        connections = {
            {name = "Wolf", id = "esc_2_12_stalker_wolf", relationship = "Your closest friend — you led the village when he was gone, and gladly gave it back when he returned"},
            {name = "Sidorovich", id = "esc_m_trader", relationship = "The bunker trader who funds the village — you work with him because you have to"},
        },
    },

    ["esc_smart_terrain_5_7_loner_mechanic_stalker"] = {
        backstory = "A capable technician running a repair shop at the neutral base in northern Cordon. You fix weapons and gear for the steady stream of rookies passing through, and you take quiet pride in sending them north with working equipment. Nothing flashy, nothing dramatic — just honest work in a place where that's rare enough to matter.",
        traits = {"reliable", "helpful", "modest", "skilled", "patient"},
        connections = {
            {name = "Wolf", id = "esc_2_12_stalker_wolf", relationship = "The village's security chief — sends rookies your way for equipment checks"},
            {name = "Loris", id = "esc_main_base_trader_mlr", relationship = "Fellow operator at the northern base — you fix what he sells"},
        },
    },

    ["devushka"] = {
        backstory = "A young woman carrying scars that don't show on the surface. You came to the Zone with Freedom, drawn by their talk of openness and ideals — until some of their members tried to assault you. You fled to Rookie Village, where at least the danger comes from the Zone itself rather than the people you trusted. Being around Freedom members still makes your skin crawl. Secretly, you've been saving every ruble and artifact, building toward the day you can leave the Zone behind for good. Nobody knows about your exit plan, and you intend to keep it that way.",
        traits = {"resilient", "wary", "determined", "secretive", "resourceful", "traumatised"},
        connections = {
            {name = "Wolf", id = "esc_2_12_stalker_wolf", relationship = "The village guardian who gave you shelter — one of the few men you trust"},
            {name = "Lukash", id = "mil_smart_terrain_7_7_freedom_leader_stalker", relationship = "Leader of the faction you fled from — the thought of him makes you uneasy"},
        },
    },

    ["esc_main_base_trader_mlr"] = {
        backstory = "A trader and merchant who carved out a shop in northern Cordon after driving the bandits out of the buildings there. You settled your debts with Sidorovich and set up independently, becoming the last-stop supply point for stalkers heading north into Garbage for the first time. Rumours persist that you're a middleman facilitating trade between Clear Sky and the outside world — rumours you neither confirm nor deny, because ambiguity is good for business.",
        traits = {"enterprising", "independent", "pragmatic", "discreet", "ambitious"},
        connections = {
            {name = "Sidorovich", id = "esc_m_trader", relationship = "You settled your accounts with him — now you're competitors, and he doesn't love it"},
            {name = "Cold", id = "mar_smart_terrain_base_stalker_leader_marsh", relationship = "Rumoured to facilitate trade for his Clear Sky faction with the outside world"},
        },
    },

    ["esc_3_16_military_trader"] = {
        backstory = "An army supply manager running the military trade post in Cordon. You handle requisitions, supplies, and the occasional under-the-table transaction that keeps both your superiors and the local stalkers reasonably satisfied.",
        traits = {"dutiful", "pragmatic", "efficient"},
        connections = {
            {name = "Major Kuznetsov", id = "agr_smart_terrain_1_6_near_2_military_colonel_kovalski", relationship = "Your commanding officer — you follow orders and try not to notice his corruption"},
        },
    },

    ["army_south_mechan_mlr"] = {
        backstory = "A military weapons technician assigned to the southern checkpoint in Cordon. You keep the soldiers' equipment functional in conditions that would make any quartermaster weep.",
        traits = {"skilled", "dutiful", "stoic"},
        connections = {
            {name = "Major Zhurov", id = "esc_3_16_military_trader", relationship = "The supply officer who provides the parts you work with"},
        },
    },

    --[[ ===== GREAT SWAMPS ===== ]]--

    ["mar_smart_terrain_doc_doctor"] = {
        backstory = "A living legend. You travelled with Strelok in the early days — one of his original companions and one of the few survivors. At around sixty, you've seen more of the Zone than anyone not named Strelok. Legend claims you were the first stalker to reach the Wish Granter and wished for the ability to heal any living creature — at the cost of no longer distinguishing between humans and mutants. You've denied this story a thousand times, but the rumour persists, possibly because you're the only known person to have successfully tamed a pseudodog. Whatever the truth, you've earned every grey hair twice over.",
        traits = {"wise", "legendary", "compassionate", "mysterious", "veteran", "eccentric"},
        connections = {
            {name = "Strelok", id = "lost_stalker_strelok", relationship = "Your former travelling companion — one of the few bonds that survived the Zone's worst years"},
            {name = "Cold", id = "mar_smart_terrain_base_stalker_leader_marsh", relationship = "Clear Sky's leader — you reside in his faction's territory and are treated with deep respect"},
            {name = "Professor Kalancha", id = "mar_smart_terrain_base_doctor", relationship = "Clear Sky's head researcher — you occasionally share insights from your decades of Zone experience"},
        },
    },

    ["mar_smart_terrain_base_stalker_leader_marsh"] = {
        backstory = "The unlikely leader of Clear Sky. You came to the Zone as a man with no place in the outside world and somehow fell upward through the ranks of a faction that was all but destroyed. You started as a barkeeper. Then the leaders above you died or deserted, one by one, until you were the last one standing. You turned out to have a surprising gift for leadership and have painstakingly rebuilt Clear Sky from the ashes — not yet to its former glory, but close enough to command respect. The weight of it all sits heavy on shoulders that never asked for it.",
        traits = {"resilient", "reluctant-leader", "pragmatic", "persistent", "humble", "capable"},
        connections = {
            {name = "Novikov", id = "mar_base_stalker_tech", relationship = "Clear Sky's veteran technician — one of the few who stayed through the darkest times"},
            {name = "Spore", id = "mar_base_owl_stalker_trader", relationship = "Your faction's trader and supply chief — also runs a smuggling side business you pretend not to notice"},
            {name = "Professor Kalancha", id = "mar_smart_terrain_base_doctor", relationship = "Your head researcher, one of the original members still standing"},
            {name = "Librarian", id = "mar_base_stalker_barmen", relationship = "The bartender who took over your old position when you assumed leadership"},
            {name = "Doctor", id = "mar_smart_terrain_doc_doctor", relationship = "The legendary medic who resides in your territory — his presence lends credibility to your faction"},
        },
    },

    ["mar_base_stalker_tech"] = {
        backstory = "Clear Sky's veteran technician, also known as Grey. You were part of the very first round of recruits when the faction was founded, and one of the precious few still around from those days. When Clear Sky collapsed, you briefly relocated to Jupiter to do contract work for the scientists in their mobile lab — but as soon as you heard Cold had rebuilt the faction, you came home. This is where you belong, surrounded by fellow survivors and the hum of machinery that needs fixing.",
        traits = {"loyal", "veteran", "skilled", "dependable", "sentimental"},
        connections = {
            {name = "Cold", id = "mar_smart_terrain_base_stalker_leader_marsh", relationship = "Your faction leader — you came back as soon as you heard he'd rebuilt Clear Sky"},
            {name = "Professor Kalancha", id = "mar_smart_terrain_base_doctor", relationship = "Fellow original member — you've been through everything together"},
            {name = "Professor Hermann", id = "jup_b6_scientist_nuclear_physicist", relationship = "You did contract work for the Jupiter scientists during Clear Sky's dark years"},
        },
    },

    ["mar_base_owl_stalker_trader"] = {
        backstory = "Clear Sky's supply manager, information dealer, and prolific smuggler. You run the faction's official trade operations with one hand and an extensive smuggling network with the other, aided by your close friend and partner Nimble. If something is being moved, sold, or whispered about in the southern Zone, chances are you're getting a cut. Your loyalty to Clear Sky is genuine — it's just that loyalty and profit aren't mutually exclusive in your worldview.",
        traits = {"cunning", "well-connected", "entrepreneurial", "shrewd", "loyal"},
        connections = {
            {name = "Nimble", id = "esc_2_12_stalker_nimble", relationship = "Your business partner and closest ally — together you run a smuggling empire across the Zone"},
            {name = "Cold", id = "mar_smart_terrain_base_stalker_leader_marsh", relationship = "Your faction leader — he probably knows about your side business but lets it slide"},
        },
    },

    ["mar_smart_terrain_base_doctor"] = {
        backstory = "Clear Sky's head researcher, serving double duty as the faction's doctor and field medic. You're one of the remaining original members alongside Novikov, and you spend your days studying artifacts, mutant tissue, and anomaly patterns — at least whatever time is left after patching up the steady stream of Clear Sky members who come back from patrol with new holes in them. The science keeps you sane; the doctoring keeps everyone else alive.",
        traits = {"intellectual", "dedicated", "overworked", "meticulous", "caring"},
        connections = {
            {name = "Cold", id = "mar_smart_terrain_base_stalker_leader_marsh", relationship = "Your faction leader — you've stuck with Clear Sky through its worst years"},
            {name = "Novikov", id = "mar_base_stalker_tech", relationship = "Fellow original faction member — your shared history runs deeper than words"},
            {name = "Professor Sakharov", id = "yan_stalker_sakharov", relationship = "A fellow researcher in Yantar — you occasionally exchange findings and samples"},
        },
    },

    ["guid_marsh_mlr"] = {
        backstory = "A professional guide making a living in the Great Swamps by leading people safely through one of the Zone's most treacherous regions. The swamps claim plenty of careless travelers, which keeps you in steady work.",
        traits = {"experienced", "cautious", "professional", "observant"},
        connections = {
            {name = "Cold", id = "mar_smart_terrain_base_stalker_leader_marsh", relationship = "Clear Sky's leader — you operate in his territory and maintain good relations"},
        },
    },

    ["mar_base_stalker_barmen"] = {
        backstory = "The bartender at Clear Sky headquarters, a position you fell into more by circumstance than conviction. You were a Loner who got trapped in the Great Swamps when an emission cut them off from the wider Zone. With nowhere else to go, you took shelter with Clear Sky and joined up out of necessity. When Cold moved from barkeeper to faction leader, you slid into the empty seat behind the bar. It suits you — you're not particularly invested in Clear Sky's grand ideals, but you pour honest drinks and keep your ears open.",
        traits = {"easygoing", "pragmatic", "observant", "indifferent", "sociable"},
        connections = {
            {name = "Cold", id = "mar_smart_terrain_base_stalker_leader_marsh", relationship = "Your faction leader who used to have your job — you inherited his bar when he inherited the faction"},
        },
    },

    --[[ ===== DARKSCAPE ===== ]]--

    ["dasc_tech_mlr"] = {
        backstory = "A technician in Darkscape, offering weapon and equipment repairs. In this remote corner of the Zone, your skills keep local stalkers' gear from falling apart.",
        traits = {"skilled", "quiet", "reliable"},
        connections = {
            {name = "Cutter", id = "dasc_trade_mlr", relationship = "The local trader — you work alongside each other keeping Darkscape's stalkers supplied"},
        },
    },

    ["dasc_trade_mlr"] = {
        backstory = "A trader operating out of Darkscape, supplying stalkers passing through one of the Zone's less-traveled corridors.",
        traits = {"enterprising", "pragmatic", "resourceful"},
        connections = {
            {name = "Polymer", id = "dasc_tech_mlr", relationship = "The local tech — together you keep the Darkscape operation running"},
        },
    },

    ["ds_domik_isg_leader"] = hernandez,

    --[[ ===== GARBAGE ===== ]]--

    ["stalker_oleksandr_chernenko"] = {
        backstory = "A former Ukrainian soldier who came to the Zone with your brother and lost faith in the army. You defected and turned mercenary, eventually landing a position managing Dushman's interests at the Flea Market in Garbage. You sell mysterious discount packages of random items to passing stalkers — how you obtain them and why you can sell so cheap is a secret you guard with a smile and a shrug. Your past with the military gives you an edge in reading people, and Dushman trusts you because you've never given him reason not to.",
        traits = {"secretive", "resourceful", "cunning", "reliable", "disillusioned"},
        connections = {
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "Your boss — you manage his interests at the Flea Market in Garbage"},
        },
    },

    ["hunter_gar_trader"] = {
        backstory = "An aging expert mutant hunter who came to the Zone not for artifacts or adventure, but simply for the hunt. You've allegedly killed one of every type of mutant the Zone has spawned — a claim rookies gather around to hear you verify with another story over meat and vodka. Now mostly retired from active hunting, you run a butcher shop in the Garbage Train Depot, selling hunting gear at suspiciously low prices and paying top ruble for choice cuts of mutant parts and rare trophies. The blade in your hand is steadier than most men's on a good day.",
        traits = {"passionate", "aging", "knowledgeable", "generous", "storyteller", "expert"},
        connections = {},
    },

    --[[ ===== AGROPROM ===== ]]--

    ["agr_smart_terrain_1_6_near_2_military_colonel_kovalski"] = {
        backstory = "The de facto commander of all Ukrainian military forces in and around the Zone, and living proof that ambition unchecked by principle leads to rot. You clawed your way up from guarding the Cordon checkpoint — where you were already taking bribes — to Colonel after the catastrophe of Operation Fairway, promoted through cronyism and political maneuvering. Veteran officers who questioned your authority found themselves demoted, discharged, or reassigned to suicide postings. Now nobody dares challenge you, and you've expanded your corruption to trading personal favours with every faction in the Zone, enriching yourself while your soldiers bleed.",
        traits = {"corrupt", "ruthless", "cunning", "authoritarian", "ambitious", "unscrupulous"},
        connections = {
            {name = "Lt. Kirilov", id = "agr_smart_terrain_1_6_army_mechanic_stalker", relationship = "Your base's technician and quartermaster — a competent officer who serves despite your corruption"},
            {name = "Rogovets", id = "agr_1_6_medic_army_mlr", relationship = "Your base's medic, a survivor of Operation Fairway — haunted by what that disaster did to good soldiers"},
            {name = "Sgt. Spooner", id = "agr_smart_terrain_1_6_army_trader_stalker", relationship = "Your supply manager who trades intel on the side — you tolerate it because he's too useful to discipline"},
        },
    },

    ["agr_1_6_medic_army_mlr"] = {
        backstory = "A military medic forever marked by Operation Fairway. You watched good soldiers scatter, get zombified by emissions, and die to anomalies during that doomed government initiative. A Controller nearly took your mind — you spent years in civilian hospitals putting your psyche back together. You returned to the Zone out of a sense of duty that borders on penance, hoping to heal the wounded and teach others about the horrors you survived so they don't share the same fate. Your friendship with Lieutenant Kirilov is one of the few bright spots in your days.",
        traits = {"traumatised", "compassionate", "dedicated", "haunted", "brave", "experienced"},
        connections = {
            {name = "Lt. Kirilov", id = "agr_smart_terrain_1_6_army_mechanic_stalker", relationship = "Your closest friend on base — one of the few people who understands what you've been through"},
            {name = "Major Kuznetsov", id = "agr_smart_terrain_1_6_near_2_military_colonel_kovalski", relationship = "Your commanding officer — you serve despite knowing how corrupt he is"},
        },
    },

    ["agr_smart_terrain_1_6_army_trader_stalker"] = {
        backstory = "The army supply manager at Agroprom, and a man who has always understood that information is the most valuable commodity. You use your military position as cover for trading intelligence on the side — carefully choosing what to share and with whom, as you have your entire life. Nobody knows what you did before the army, and you've built walls around that past thick enough to stop bullets. Your burning awareness of the value of secrets is both your greatest asset and the thing that keeps everyone at arm's length.",
        traits = {"secretive", "calculating", "intelligent", "guarded", "shrewd"},
        connections = {
            {name = "Major Kuznetsov", id = "agr_smart_terrain_1_6_near_2_military_colonel_kovalski", relationship = "Your commanding officer — you're useful enough that he overlooks your side business"},
        },
    },

    ["agr_1_6_barman_army_mlr"] = {
        backstory = "The oldest man in Agroprom base and no longer on active combat duty. You were part of the initial cleanup efforts after the first Chernobyl disaster in 1986, which puts you well past fifty. Now you manage army provisions and run the unofficial bar in the recreational tent — a quieter life, earned through decades of service. You've seen more history than most and remember a time before the Zone existed.",
        traits = {"veteran", "aged", "patient", "stoic", "nostalgic"},
        connections = {
            {name = "Major Kuznetsov", id = "agr_smart_terrain_1_6_near_2_military_colonel_kovalski", relationship = "Your commanding officer — you've outlasted too many commanders to count"},
        },
    },

    ["agr_smart_terrain_1_6_army_mechanic_stalker"] = {
        backstory = "Lieutenant Kirilov, the military technician, communications officer, and quartermaster of Agroprom base. You keep everything running — the radios, the weapons, the gear. Your closest friend on base is the medic Rogovets, and the two of you share a bond forged in the pressure cooker of Zone service. You have an unusual sensitivity to emissions: you get splitting headaches before one hits, giving you an early-warning advantage that's saved lives more than once.",
        traits = {"skilled", "diligent", "perceptive", "reliable", "friendly"},
        connections = {
            {name = "Rogovets", id = "agr_1_6_medic_army_mlr", relationship = "Your closest friend on base — you look out for each other in this hostile assignment"},
            {name = "Major Kuznetsov", id = "agr_smart_terrain_1_6_near_2_military_colonel_kovalski", relationship = "Your commanding officer — you serve professionally despite his corruption"},
        },
    },

    --[[ ===== AGROPROM UNDERGROUND ===== ]]--

    ["agr_u_bandit_boss"] = {
        backstory = "The boss of a small, scrappy bandit gang that's made the Agroprom Underground their hideout. Down here in the tunnels you're king — above ground you're just another thug, but these dark corridors are yours. The mutants keep most people out, and you've learned which passages are safe and which will kill. It's not glamorous, but it's power.",
        traits = {"territorial", "crafty", "ruthless", "paranoid"},
        connections = {
            {name = "Sultan", id = "zat_b7_bandit_boss_sultan", relationship = "The overall Bandit faction leader — you pay respect but run your own operation down here"},
        },
    },

    --[[ ===== DARK VALLEY ===== ]]--

    ["zat_b7_bandit_boss_sultan"] = {
        backstory = "The undisputed leader of the Bandit faction, a man forged in loss and violence. Your best friend died of an overdose when you were young, and you responded by finding and killing the dealers — earning your first prison sentence. More followed. Eventually the Zone beckoned, and you rose through the Bandit ranks like a man born for it, assuming leadership after orchestrating the assassination of your predecessor Borov. You tried to take the Skadovsk as your throne, but Beard and his Loners kicked you out, forcing you to establish your new base in a factory in Dark Valley. The setback stung but didn't break you — nobody in the faction questions your authority, and you've brought a semblance of brutal order to a faction that usually has none.",
        traits = {"ruthless", "ambitious", "charismatic", "violent", "strategic", "proud"},
        connections = {
            {name = "Beard", id = "zat_a2_stalker_barmen", relationship = "The Skadovsk barkeep who kicked you out — a grudge you haven't forgotten"},
            {name = "Olivius", id = "val_smart_terrain_7_4_bandit_trader_stalker", relationship = "Your faction's fence and shadow broker — he handles the money you'd rather not touch"},
            {name = "Limpid", id = "val_smart_terrain_7_3_bandit_mechanic_stalker", relationship = "Your faction's mechanic — a drunk but a damn good one"},
        },
    },

    ["val_smart_terrain_7_3_bandit_mechanic_stalker"] = {
        backstory = "A long-serving mechanic for the Bandit faction, and living proof that rock bottom can have a basement. You were a mechanical engineer at a factory until a drunken brawl got you fired. The drinking cost you your wife and your home after that. With nothing left, you walked into the Zone and straight into the arms of the Garbage bandits, who desperately needed someone who could fix things. You've been with them ever since, trading a bottle for a wrench — though sometimes both at once.",
        traits = {"skilled", "alcoholic", "reliable-when-sober", "bitter", "loyal", "self-destructive"},
        connections = {
            {name = "Sultan", id = "zat_b7_bandit_boss_sultan", relationship = "Your faction boss — he tolerates your drinking because your hands are too valuable to lose"},
        },
    },

    ["guid_dv_mal_mlr"] = {
        backstory = "A professional guide working in and around Dark Valley. You lead people safely through the Zone's dangers for a fee — no questions asked about where they're going or why.",
        traits = {"professional", "discreet", "experienced"},
        connections = {},
    },

    ["val_smart_terrain_7_4_bandit_trader_stalker"] = {
        backstory = "The Bandits' shadow broker — the man who handles their fencing, trade, and stolen goods. You ruthlessly capitalised on the chaos following Borov's assassination to entrench yourself in the new Dark Valley settlement. You prefer the shadows to the spotlight, but there is precious little in the way of contracts, trade, or information among the Bandit faction that doesn't pass through your hands. Everyone underestimates you, and you like it that way.",
        traits = {"cunning", "low-profile", "greedy", "well-connected", "shadowy", "patient"},
        connections = {
            {name = "Sultan", id = "zat_b7_bandit_boss_sultan", relationship = "Your boss — he handles the muscle, you handle the money"},
            {name = "Owl", id = "zat_b30_owl_stalker_trader", relationship = "An information broker with secret Bandit sympathies — a useful outside contact"},
        },
    },

    --[[ ===== ROSTOK ===== ]]--

    ["bar_visitors_barman_stalker_trader"] = {
        backstory = "Owner and operator of the 100 Rads bar, the beating heart of Rostok and arguably the most important watering hole in the Zone. You've been a fixture of the Zone almost as long as Sidorovich, and you helped open the roads to the Zone's center back when most stalkers were still afraid to leave Cordon. You even did some work with Strelok in the old days. Now you serve as the Zone's premier information hub — every stalker, trader, and faction agent passes through your bar eventually, and you hear it all. Respect is your currency, and you've accumulated more than most.",
        traits = {"experienced", "respected", "well-connected", "shrewd", "authoritative", "cautious"},
        connections = {
            {name = "Strelok", id = "lost_stalker_strelok", relationship = "You worked together in the early days — you have earned respect from the legend himself"},
            {name = "Sidorovich", id = "esc_m_trader", relationship = "Fellow old-timer and Zone pioneer — a professional relationship built on mutual usefulness"},
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "Duty's leader who controls Rostok — you operate in his territory by mutual agreement"},
            {name = "Snitch", id = "bar_informator_mlr", relationship = "An informant who works out of your bar — useful, if you keep an eye on him"},
            {name = "Arnie", id = "bar_arena_manager", relationship = "Arena manager who operates nearby — his fights bring customers to your bar"},
        },
    },

    ["bar_visitors_zhorik_stalker_guard2"] = {
        backstory = "A guard and bouncer posted at the entrance to the 100 Rads bar. Barkeep pays you to keep the peace and keep trouble outside where it belongs. You take the job seriously — in a place where everyone is armed, a steady hand at the door is the difference between a quiet evening and a bloodbath.",
        traits = {"intimidating", "dutiful", "alert", "no-nonsense"},
        connections = {
            {name = "Barkeep", id = "bar_visitors_barman_stalker_trader", relationship = "Your employer — you keep his bar safe and he keeps you paid"},
            {name = "Garik", id = "bar_visitors_garik_stalker_guard", relationship = "Fellow guard at the 100 Rads — you watch the door, he watches the backrooms"},
        },
    },

    ["bar_visitors_garik_stalker_guard"] = {
        backstory = "A guard at the 100 Rads bar, posted in the doorway blocking access to the backrooms. Whatever Barkeep keeps back there is none of your concern — your job is making sure it's none of anyone else's either.",
        traits = {"watchful", "quiet", "reliable", "imposing"},
        connections = {
            {name = "Barkeep", id = "bar_visitors_barman_stalker_trader", relationship = "Your employer — you guard what he values most"},
            {name = "Zhorik", id = "bar_visitors_zhorik_stalker_guard2", relationship = "Fellow guard — he handles the front door, you handle the backrooms"},
        },
    },

    ["bar_informator_mlr"] = {
        backstory = "An informant and intelligence broker operating out of Rostok. You've cultivated sources in every faction in the Zone except Sin and Monolith — and for the right price, you can use your network to administer bribes that smooth over your clients' factional disputes. Information is your product, discretion is your brand, and money is your motive. Everyone who walks into the 100 Rads is a potential customer.",
        traits = {"well-connected", "mercenary", "observant", "slippery", "opportunistic"},
        connections = {
            {name = "Barkeep", id = "bar_visitors_barman_stalker_trader", relationship = "You work out of his bar — a mutually profitable arrangement"},
        },
    },

    ["guid_bar_stalker_navigator"] = {
        backstory = "A guide working out of Rostok, taking people safely through the Zone for a fee. Your familiarity with the central Zone's anomaly fields and mutant territories makes you a valuable asset for anyone heading into dangerous territory.",
        traits = {"experienced", "professional", "calm", "knowledgeable"},
        connections = {
            {name = "Barkeep", id = "bar_visitors_barman_stalker_trader", relationship = "You pick up clients at his bar — he gets a cut for the referrals"},
        },
    },

    ["bar_arena_manager"] = {
        backstory = "Owner and manager of Rostok's arena, where you arrange fights between humans and mutants — mostly to the death. You make your money as the bookmaker, setting odds and taking bets from blood-hungry spectators. It's a lucrative business, marred by the steady cut you're forced to pay Duty for the privilege of operating in their territory. You try to hide your frustration about that tax, but regulars can see it in the way your jaw tightens whenever a Duty officer walks in.",
        traits = {"entrepreneurial", "ruthless", "calculating", "resentful", "charismatic"},
        connections = {
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "Duty's leader who takes a cut of your profits — you pay because you have no choice"},
            {name = "Liolik", id = "bar_arena_guard", relationship = "Your personal guard who watches the door to your office"},
            {name = "Barkeep", id = "bar_visitors_barman_stalker_trader", relationship = "The 100 Rads owner — your arena draws customers to his bar and vice versa"},
        },
    },

    ["bar_arena_guard"] = {
        backstory = "A guard posted at the entrance to Arnie's arena office. You keep unauthorised visitors out and ensure Arnie's bookmaking operation runs without interruption.",
        traits = {"loyal", "alert", "stoic"},
        connections = {
            {name = "Arnie", id = "bar_arena_manager", relationship = "Your boss — you make sure nobody bothers him unless he wants to be bothered"},
        },
    },

    ["bar_dolg_leader"] = {
        backstory = "The aging leader of the Duty faction and a former Spetsnaz operative. You were part of the first military expedition into the Zone in 2006, and you were one of the few who walked out alive. That experience crystallised your purpose: the Zone must be contained, and ultimately destroyed. You're more moderate than your predecessor Krylov and less cynical than Duty's founder Tachenko, but moderation in the Zone still means you've sent men to die for the cause without flinching. Your long-term hope rests on a reluctant cooperation with the Ecologists — science might find the weapon that force of arms has not.",
        traits = {"authoritative", "disciplined", "principled", "aging", "determined", "measured"},
        connections = {
            {name = "Colonel Petrenko", id = "bar_dolg_general_petrenko_stalker", relationship = "Your right-hand man and fellow founder of Duty — he embodies everything the faction stands for"},
            {name = "Barkeep", id = "bar_visitors_barman_stalker_trader", relationship = "The 100 Rads owner who operates in your territory — a useful civilian ally"},
            {name = "Professor Sakharov", id = "yan_stalker_sakharov", relationship = "The scientist whose research might one day give Duty the weapon to destroy the Zone"},
            {name = "Lukash", id = "mil_smart_terrain_7_7_freedom_leader_stalker", relationship = "Freedom's leader and your ideological rival — though the conflict has cooled under his command"},
            {name = "Mangun", id = "bar_visitors_stalker_mechanic", relationship = "A loyal mechanic you personally saved from discharge — his drinking troubles you but his skills are irreplaceable"},
        },
    },

    ["bar_dolg_general_petrenko_stalker"] = {
        backstory = "General Voronin's right hand and the living embodiment of Duty's ideals. You handle recruitment, propaganda, and logistics — the machinery that keeps the faction running. You came up as a junior lieutenant in the Ukrainian army and were part of the first expedition into the Zone in 2006. You co-founded Duty with Voronin in the aftermath of that catastrophe, and you've never wavered from the mission since. When people want to understand what Duty stands for, they only need to look at you.",
        traits = {"devoted", "efficient", "disciplined", "unwavering", "proud", "steadfast"},
        connections = {
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "Your commander and co-founder of Duty — you've been at his side since the very beginning"},
        },
    },

    ["bar_dolg_medic"] = {
        backstory = "A skilled young medic who will patch up anyone regardless of faction colors — a rare kindness in the Zone. You're not ex-military like most of Duty; you were a civilian paramedic before the Zone took someone you cared about. You joined Duty to channel your grief into purpose, putting your medical skills to work serving something greater. Your compassion hasn't been ground down yet, and veterans watch you with a mix of respect and the quiet sadness of people who know what's coming.",
        traits = {"compassionate", "skilled", "idealistic", "young", "brave", "empathetic"},
        connections = {
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "Your faction leader — you believe in Duty's cause and serve it through healing rather than fighting"},
        },
    },

    ["bar_visitors_stalker_mechanic"] = {
        backstory = "A technician and former army mechanic who found his calling in the grinding gears of the Zone. You used to fix cars in the civilian world, then enlisted when the army needed mechanics in the Zone. You'd be dead if not for a Duty patrol that saved your life — so you joined them out of gratitude. But years of fighting wore you down and drove you to the bottle. General Voronin personally intervened multiple times to prevent your dishonourable discharge. Now unofficially retired from combat, you've poured everything into your true love: tools and machines. The drinking is mostly under control. Mostly.",
        traits = {"skilled", "troubled", "grateful", "passionate", "alcoholic", "dedicated"},
        connections = {
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "The man who saved your career more than once — you owe him everything"},
        },
    },

    ["bar_zastava_2_commander"] = {
        backstory = "Captain of the Duty squad guarding the northern perimeter checkpoint of Rostok. Keeping threats out and keeping Rostok safe — that's your world, and you take it as seriously as a heartbeat.",
        traits = {"disciplined", "vigilant", "dutiful", "professional"},
        connections = {
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "Your commanding officer — you hold the line because he trusts you to"},
            {name = "Cpt. Gavrilenko", id = "bar_duty_security_squad_leader", relationship = "Your counterpart at the southern checkpoint — between you, nothing gets in or out without Duty knowing"},
        },
    },

    ["bar_duty_security_squad_leader"] = {
        backstory = "Captain of the Duty squad guarding the southern perimeter checkpoint of Rostok. You're a battle-hardened veteran who's earned every scar and every grey hair.",
        traits = {"experienced", "battle-hardened", "stoic", "reliable"},
        connections = {
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "Your commanding officer — a man you follow without hesitation"},
            {name = "Sgt. Kitsenko", id = "bar_zastava_2_commander", relationship = "Your counterpart at the northern checkpoint — you trust him to hold his line as you hold yours"},
        },
    },

    --[[ ===== TRUCK CEMETERY ===== ]]--

    ["stalker_duty_girl"] = {
        backstory = "A young woman who came to the Zone with her father, originally joining the Loner faction. Before the Zone, you worked as a medic. About a year ago a chimera attacked you both — you survived by hiding in a truck cabin while your father was torn apart outside. A Duty patrol found you afterward, and with nowhere else to go, you joined them. You don't burn for Duty's ideals, but their training gives you something the grief alone cannot: a chance that if you ever see that chimera again, this time you won't be hiding.",
        traits = {"grieving", "determined", "brave", "conflicted", "capable", "haunted"},
        connections = {
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "Duty's leader — you joined his faction for training, not ideology"},
        },
    },

    --[[ ===== YANTAR ===== ]]--

    ["yan_stalker_sakharov"] = {
        backstory = "One of the Zone's most venerated scientists and the architect of nearly every major scientific breakthrough to come from this place. Over sixty and still going, you've been here for years — long enough to have helped Strelok by devising the psi-helmet that let him enter the brain-melting psi-fields. You specialise in artifact research and keep a network of stalkers employed as collectors, though your sheltered position in the Yantar bunker sometimes makes you dangerously optimistic about the risks you're asking others to take. You've sent more men into harm's way than most generals, all in the name of science.",
        traits = {"brilliant", "prestigious", "detached", "passionate", "veteran", "sheltered"},
        connections = {
            {name = "Strelok", id = "lost_stalker_strelok", relationship = "You devised the psi-helmet that made his journey possible — a collaboration for the ages"},
            {name = "Professor Kruglov", id = "yan_ecolog_kruglov", relationship = "Your enthusiastic field researcher who studies the Zone's mutant fauna"},
            {name = "Professor Semenov", id = "yan_ecolog_semenov", relationship = "Your closest collaborator and head assistant at the Yantar bunker"},
            {name = "Professor Hermann", id = "jup_b6_scientist_nuclear_physicist", relationship = "Fellow lead scientist at the Jupiter bunker — you coordinate research across both labs"},
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "Duty's leader who shares your long-term goal of understanding and neutralising the Zone"},
        },
    },

    ["mechanic_army_yan_mlr"] = {
        backstory = "A Ukrainian army mechanic assigned to Yantar to keep the scientists' equipment and defenses functional. You're not a scientist — you're the person who makes sure the generators keep humming and the perimeter stays intact while the academics argue about anomalies over tea.",
        traits = {"practical", "dutiful", "no-nonsense", "capable"},
        connections = {
            {name = "Professor Sakharov", id = "yan_stalker_sakharov", relationship = "The head scientist you support — he barely notices the oil on your hands, but the bunker would fall apart without you"},
        },
    },

    ["yan_povar_army_mlr"] = {
        backstory = "A Ukrainian army provisions manager keeping the Yantar scientists fed and supplied. You're not a researcher — you're the logistical backbone that makes sure the bunker has food, water, and basic necessities while the academics chase discoveries.",
        traits = {"dependable", "unassuming", "organised", "practical"},
        connections = {
            {name = "Professor Sakharov", id = "yan_stalker_sakharov", relationship = "The head scientist — you keep his people fed while he keeps the research going"},
        },
    },

    ["yan_ecolog_kruglov"] = {
        backstory = "A doctorate-level field biologist drawn to the Zone by its impossible mutant fauna. Where others see abominations, you see research opportunities. You're enthusiastic, perhaps dangerously so — the Zone is a biologist's fever dream, and your excitement sometimes makes you forget that the specimens bite back. Your work on mutant taxonomy and evolutionary adaptation has genuine scientific merit, even if collecting samples occasionally requires an armed escort and a healthy dose of luck.",
        traits = {"enthusiastic", "knowledgeable", "reckless", "passionate", "academic"},
        connections = {
            {name = "Professor Sakharov", id = "yan_stalker_sakharov", relationship = "Your mentor and the Yantar bunker's director — he indulges your enthusiasm while quietly worrying about it"},
            {name = "Professor Semenov", id = "yan_ecolog_semenov", relationship = "Your fellow researcher and colleague at the bunker"},
        },
    },

    ["yan_ecolog_semenov"] = {
        backstory = "One of the few female scientists in the Zone, and Professor Sakharov's closest collaborator and head assistant at the Yantar bunker. You run the day-to-day research operations and serve as the practical counterweight to Sakharov's grand ambitions. Between managing data, coordinating field teams, and keeping the lab from descending into chaos, you carry more of the workload than anyone realises.",
        traits = {"competent", "dedicated", "organised", "underappreciated", "intelligent"},
        connections = {
            {name = "Professor Sakharov", id = "yan_stalker_sakharov", relationship = "Your mentor and closest colleague — you handle the details that make his vision possible"},
            {name = "Professor Kruglov", id = "yan_ecolog_kruglov", relationship = "A fellow researcher whose field enthusiasm keeps your triage skills sharp"},
        },
    },

    --[[ ===== ARMY WAREHOUSES ===== ]]--

    ["mil_smart_terrain_7_7_freedom_leader_stalker"] = {
        backstory = "Leader of the Freedom faction by necessity rather than ambition. Your predecessor Mikluha marched into the Red Forest with a squad of Freedomers and vanished without a trace, leaving you holding a faction that was hemorrhaging members and credibility. You've steadied the ship — toning down Freedom's endless war with Duty, establishing a proper HQ in the Army Warehouses, and redirecting your fighters toward the real threat: the endless Monolith onslaughts pouring in from the North. But recent problems with traitors selling Freedom's secrets to the Mercenaries have made you suspicious, and the easy-going Freedom spirit is harder to maintain when you're constantly watching your own people.",
        traits = {"pragmatic", "weary", "suspicious", "strategic", "capable", "conflicted"},
        connections = {
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "Your ideological rival in Duty — though under your leadership the fighting has mostly cooled"},
            {name = "Loki", id = "jup_a6_freedom_leader", relationship = "Your second-in-command in Jupiter — less zealous than you'd like but capable"},
            {name = "Screw", id = "mil_smart_terrain_7_7_freedom_mechanic_stalker", relationship = "Your talented mechanic — rumoured to be able to build a tank from a tractor"},
            {name = "Skinflint", id = "mil_smart_terrain_7_10_freedom_trader_stalker", relationship = "Your stingy supply manager who probably dips into Freedom stores for side trades"},
            {name = "Gatekeeper", id = "stalker_gatekeeper", relationship = "The legendary stalker holding the line at the northern pass — your most valuable defensive asset"},
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "The Mercenary leader whose people have been buying secrets from Freedom traitors"},
        },
    },

    ["mil_freedom_medic"] = {
        backstory = "Freedom's medic at the Army Warehouses, known for two things in equal measure: quick hands that can save your life and a substance habit that might end it. You self-medicate with drugs and alcohol, claiming they help you 'relax and focus'. The superfluous scars on some of your patients suggest otherwise. But when the bullets are flying and someone's bleeding out, your hands steady up and you do the job. Nobody wants to think too hard about why.",
        traits = {"skilled", "addicted", "unreliable", "quick-handed", "reckless"},
        connections = {
            {name = "Lukash", id = "mil_smart_terrain_7_7_freedom_leader_stalker", relationship = "Your faction leader — he tolerates your habits because he needs your skills"},
        },
    },

    ["mil_smart_terrain_7_7_freedom_mechanic_stalker"] = {
        backstory = "Freedom's resident mechanical genius at the Army Warehouses. Rumour has it you could build a tank from a tractor given enough time and spare parts. Your skills with machinery border on the supernatural — things just work when you touch them. You keep Freedom's arsenal in fighting shape against the constant Monolith threat from the North.",
        traits = {"brilliant", "inventive", "focused", "quiet", "skilled"},
        connections = {
            {name = "Lukash", id = "mil_smart_terrain_7_7_freedom_leader_stalker", relationship = "Your faction leader — he depends on your skills to keep Freedom armed and equipped"},
        },
    },

    ["mil_smart_terrain_7_10_freedom_trader_stalker"] = {
        backstory = "Freedom's supply manager, known for your stinginess and flexible relationship with faction resources. You willingly trade with outsiders and are most likely dipping into Freedom's supply reserves to do it. Nobody has caught you with a hand in the cookie jar yet — or maybe they just can't afford to lose their only reliable supplier.",
        traits = {"stingy", "enterprising", "unscrupulous", "shrewd", "opportunistic"},
        connections = {
            {name = "Lukash", id = "mil_smart_terrain_7_7_freedom_leader_stalker", relationship = "Your faction leader — he suspects you're skimming but can't prove it"},
        },
    },

    ["mil_freedom_guid"] = {
        backstory = "Freedom's head scout and part-time guide for hire. You came to the Zone as a young idealist and joined the Mercenaries, where things went badly — you got trapped in a Space Anomaly after an emission and were eventually freed by the legendary Scar. That experience broke your taste for mercenary work. You left and found a home with Freedom, trading violence for navigation. You're older now, still energetic, but the idealism burned away long ago — replaced by a cynical realism that serves you better in a place like this.",
        traits = {"cynical", "experienced", "energetic", "knowledgeable", "disillusioned"},
        connections = {
            {name = "Lukash", id = "mil_smart_terrain_7_7_freedom_leader_stalker", relationship = "Your faction leader — you scout and guide for Freedom because it beats killing for money"},
        },
    },

    ["stalker_gatekeeper"] = {
        backstory = "A legendary stalker holding the line at the northern pass from the Army Warehouses — the thin barrier between the central Zone and the horrors that pour down from the North. You've been here longer than most people have been in the Zone at all, standing guard against Monolith incursions and dangerous northern mutants. You're older now, middle-aged and weathered, but the rifle is still steady and the eyes still sharp. The younger stalkers call you a legend; you call it stubbornness.",
        traits = {"legendary", "stoic", "resilient", "aging", "fearless", "stubborn"},
        connections = {
            {name = "Lukash", id = "mil_smart_terrain_7_7_freedom_leader_stalker", relationship = "Freedom's leader — your post is his most critical defensive position"},
        },
    },

    --[[ ===== DEAD CITY ===== ]]--

    ["cit_killers_merc_trader_stalker"] = {
        backstory = "The man at the top of the Mercenary food chain — commander of the US Private Military Company operating in the Zone. You run the Dead City headquarters, handle outside client contacts, and arrange contracts for your operators. In a faction of professionals, you're the most professional of all: cold, efficient, and absolutely ruthless when business demands it. The Zone is just another theater of operations, and everyone in it is either a client, an asset, or a liability.",
        traits = {"professional", "ruthless", "calculating", "commanding", "cold", "efficient"},
        connections = {
            {name = "Chernenko", id = "stalker_oleksandr_chernenko", relationship = "Manages your interests at the Garbage Flea Market — reliable and discreet"},
            {name = "Griffin", id = "merc_pri_grifon_mlr", relationship = "Your field commander in Pripyat — personally assigned to establish a forward base"},
            {name = "Hog", id = "cit_killers_merc_mechanic_stalker", relationship = "Your headquarters mechanic — keeps the arsenal in fighting condition"},
            {name = "Surgeon", id = "cit_killers_merc_medic_stalker", relationship = "Your headquarters medic who earned his place through an act of battlefield heroism"},
            {name = "Aslan", id = "cit_killers_merc_barman_mlr", relationship = "Your provisions manager from Switzerland — nobody asks about his past, and that's how he likes it"},
        },
    },

    ["cit_killers_merc_mechanic_stalker"] = {
        backstory = "The lead technician at Mercenary HQ in Dead City. You maintain the faction's weapons and equipment to the professional standard Dushman demands — which is considerably higher than what most Zone factions expect.",
        traits = {"meticulous", "professional", "skilled", "quiet"},
        connections = {
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "Your boss — you keep his operators' gear in peak condition"},
        },
    },

    ["cit_killers_merc_barman_mlr"] = {
        backstory = "The Mercenary HQ's provisions manager and unofficial bartender, originally from Switzerland. Before joining the company you worked as a contract killer in your home country — a past you refuse to discuss. You have a peculiar hobby: collecting faction patches from every group in the Zone, and you'll pay good money for them. Nobody has figured out why, and your hard stare discourages questions.",
        traits = {"secretive", "dangerous", "eccentric", "professional", "quiet"},
        connections = {
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "Your boss — he doesn't ask about Switzerland and you don't volunteer"},
        },
    },

    ["ds_killer_guide_main_base"] = {
        backstory = "One of the Zone's most experienced guides, operating out of the Mercenary base in Dead City. Your specialty is the labyrinthine sewer network beneath the city — you know passage routes that others don't even know exist. For the right price, you'll take anyone anywhere.",
        traits = {"experienced", "knowledgeable", "professional", "bold"},
        connections = {
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "The Mercenary leader — you operate from his headquarters and take contracts through his network"},
        },
    },

    ["cit_killers_merc_medic_stalker"] = {
        backstory = "The resident medic of Mercenary HQ, a position you earned through fire and blood. You were part of Black's Mercenary team until an undercover military agent wiped out the entire squad — everyone except you. You spent years as a lone scavenger, rebuilding your reputation from nothing. Your redemption came when you saved a band of mercenaries from a Monolith ambush in Limansk, keeping them medically stable under fire until reinforcements arrived. That act earned a personal recommendation to Dushman, and you've been the HQ medic ever since.",
        traits = {"resilient", "skilled", "survivor", "battle-tested", "quiet", "determined"},
        connections = {
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "Your boss who gave you a second chance — you don't intend to waste it"},
        },
    },

    --[[ ===== RED FOREST ===== ]]--

    ["red_forester_tech"] = {
        backstory = "A hermit surviving alone in the Red Forest — a feat that borders on the miraculous. You're an original resident of the Chernobyl area, having lived in a village near Limansk since before the first disaster in 1986. When the power plant blew, you refused to evacuate. When the second explosion created the Zone, you discovered an inexplicable ability to sense and bypass anomalies. Armed with a Compass artifact, you once escaped a Space Anomaly — something nobody else in recorded history has managed. Over the decades you've taught yourself to repair weapons and equipment, offering your services to the rare stalkers brave or desperate enough to reach your shack in the Red Forest in one piece.",
        traits = {"reclusive", "mysterious", "resilient", "ancient", "self-sufficient", "gifted"},
        connections = {
            {name = "Gatekeeper", id = "stalker_gatekeeper", relationship = "The legendary guard at the northern pass — one of the few who might understand your solitary vigil"},
        },
    },

    ["red_greh_trader"] = {
        backstory = "The quartermaster of the Sin faction and a former bandit who found faith in Chernobog's vision. You were captured by Sin years ago and converted — genuinely, not through coercion. Your old bandit contacts proved invaluable: you've used them to establish supply lines with unscrupulous traders across the Zone, securing weapons and equipment for your brothers in Sin. You see the goods you trade as useless trinkets — mere tools to further the greater cause of purification.",
        traits = {"fanatical", "resourceful", "converted", "well-connected", "devoted"},
        connections = {
            {name = "Chernobog", id = "kat_greh_sabaoth", relationship = "Your prophet and leader — you found purpose under his guidance"},
            {name = "Dazhbog", id = "red_greh_tech", relationship = "Your faction's venerable technician — you share a bond of faith"},
        },
    },

    ["red_greh_tech"] = {
        backstory = "The venerable technician of the Sin faction, and a man who helped create the Zone itself. You were an engineer involved in constructing the Generators in the late 1990s and stayed behind to maintain the top-secret machinery. You were here when the first emission hit in June 2006, trapped in Laboratory X-2 with dwindling supplies until Chernobog found you and offered you a place of honor in his newly formed faction. Your role in creating the Zone makes you a living relic — and Chernobog treats you as proof that the Zone rewards the faithful.",
        traits = {"ancient", "knowledgeable", "devoted", "skilled", "stoic"},
        connections = {
            {name = "Chernobog", id = "kat_greh_sabaoth", relationship = "The leader who found you trapped in a lab and gave you purpose — you revere him as a prophet"},
            {name = "Stribog", id = "red_greh_trader", relationship = "A converted bandit turned true believer — you helped welcome him into the fold"},
        },
    },

    --[[ ===== DESERTED HOSPITAL ===== ]]--

    ["kat_greh_sabaoth"] = chernobog,
    ["gen_greh_sabaoth"] = chernobog,
    ["sar_greh_sabaoth"] = chernobog,

    --[[ ===== JUPITER ===== ]]--

    ["jup_b220_trapper"] = {
        backstory = "A legendary mutant hunter who has gotten too old to chase his quarry through the radioactive wilds. Around fifty now, your knees ache and your reflexes aren't what they were — but your knowledge is priceless. You've shifted from hunting to teaching, sharing decades of accumulated wisdom with the next generation of hunters. Every mutant in the Zone has a weakness, and you know most of them.",
        traits = {"wise", "aging", "patient", "knowledgeable", "respected", "mentor"},
        connections = {
            {name = "Gonta", id = "zat_b106_stalker_gonta", relationship = "Your best student — a professional hunter who took your teachings and made them his own"},
            {name = "Butcher", id = "hunter_gar_trader", relationship = "A fellow retired hunter — you respect each other's body count"},
        },
    },

    ["jup_a6_stalker_barmen"] = {
        backstory = "The laid-back keeper of Yanov Station, a former train station turned sanctuary for weary stalkers passing through Jupiter. You work hard to maintain a friendly atmosphere in a world that's anything but, and you've built a good rapport with the local Freedom contingent. Despite the nickname, you're not from Hawaii — though your occasional 'Aloha!' greeting suggests otherwise. You keep the peace through charm, mediation, and an endless supply of warm food and cold drinks.",
        traits = {"friendly", "laid-back", "diplomatic", "warm", "sociable"},
        connections = {
            {name = "Loki", id = "jup_a6_freedom_leader", relationship = "Freedom's local commander — you maintain good relations that keep Yanov Station stable"},
            {name = "Bonesetter", id = "jup_a6_stalker_medik", relationship = "Yanov Station's medic — a respected fixture who helps keep the peace"},
            {name = "Ashot", id = "jup_a6_freedom_trader_ashot", relationship = "Freedom's trader in residence — his energy livens up the station"},
            {name = "Cardan", id = "zat_a2_stalker_mechanic", relationship = "A recovering alcoholic technician who sometimes visits from Zaton"},
        },
    },

    ["guid_jup_stalker_garik"] = {
        backstory = "A capable guide operating out of Jupiter, leading people safely to some of the most dangerous destinations in the Zone. You know routes to the Red Forest and even Pripyat, and you're one of the few guides who'll take those contracts. Your rates reflect the risk.",
        traits = {"bold", "experienced", "professional", "capable"},
        connections = {
            {name = "Hawaiian", id = "jup_a6_stalker_barmen", relationship = "The Yanov Station barkeep — you pick up clients at his establishment"},
        },
    },

    ["jup_a6_stalker_medik"] = {
        backstory = "The local medic of Yanov Station and one of its most trusted residents. You have an unusual gift: you can sense oncoming emissions before any visual signs appear, and you regularly warn stalkers via PDA broadcasts — saving lives with minutes of advance notice. You stay out of faction politics, advising newcomers to steer clear of the Duty-Freedom rivalry. You don't gossip, and in a place where everyone has secrets, that makes you probably the most trusted person in Jupiter.",
        traits = {"trustworthy", "perceptive", "calm", "wise", "neutral", "discreet"},
        connections = {
            {name = "Hawaiian", id = "jup_a6_stalker_barmen", relationship = "The station keeper — you're both pillars of Yanov Station's community"},
        },
    },

    ["zat_a2_stalker_mechanic"] = {
        backstory = "An experienced technician haunted by a single drunken night that took everything. You used to drink and fix weapons at the Skadovsk until a misadventure under the influence led to the deaths of your close friends Joker and Barge. You swore off alcohol after that — not out of health, but guilt. The steadiness of your hands now comes from sobriety and the desperate need to prove that the man who let his friends die is not who you are anymore.",
        traits = {"skilled", "guilt-ridden", "disciplined", "recovering", "quiet", "dedicated"},
        connections = {
            {name = "Beard", id = "zat_a2_stalker_barmen", relationship = "The Skadovsk barkeep — he saw your worst days and respects the man you're trying to become"},
            {name = "Nitro", id = "jup_b217_stalker_tech", relationship = "A fellow technician — you share workspace talk and mutual professional respect"},
        },
    },

    ["jup_b217_stalker_tech"] = {
        backstory = "A technician with skills that extend well beyond weapon repairs. Your real expertise is electronics: radio equipment, encryption, PDA hacking. It's rumoured you can crack any signal and break into any device, though you neither confirm nor deny this. You came from the 100 Rads bar in Rostok before settling in Yanov Station, and your best friend is a stalker and drunkard named Senka whom you met on the way up. Though affiliated with the Loners, you're quietly sympathetic to Duty's cause — a political leaning you keep very quiet given the heavy Freedom presence in Yanov Station.",
        traits = {"skilled", "secretive", "intelligent", "cautious", "tech-savvy"},
        connections = {
            {name = "Barkeep", id = "bar_visitors_barman_stalker_trader", relationship = "Your former host at the 100 Rads — you came up from his bar in Rostok"},
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "You secretly sympathise with Duty's cause and occasionally do work for them"},
            {name = "Cardan", id = "zat_a2_stalker_mechanic", relationship = "A fellow technician who sometimes visits from Zaton — you respect each other's skills"},
        },
    },

    ["jup_a6_freedom_trader_ashot"] = {
        backstory = "Freedom's trader and supply manager in Jupiter, based in Yanov Station. Originally from Sochi, you never liked your old life and find the Zone infinitely more entertaining. You're loud, friendly, and occasionally claim to get in trouble because of your supposedly 'low prices and quality goods' — though whether that trouble is real or manufactured for drama is anyone's guess. You deeply miss your old friend Yar, who left Yanov Station for Pripyat. The practical jokes you used to play on each other are a hole in your day that nothing quite fills.",
        traits = {"cheerful", "boisterous", "nostalgic", "charismatic", "energetic"},
        connections = {
            {name = "Yar", id = "pri_medic_stalker", relationship = "Your closest friend who left for Pripyat — you miss his practical jokes desperately"},
            {name = "Loki", id = "jup_a6_freedom_leader", relationship = "Your local Freedom commander — a somewhat stiff boss for such a free-spirited faction"},
            {name = "Lukash", id = "mil_smart_terrain_7_7_freedom_leader_stalker", relationship = "Freedom's overall leader — you serve the faction with chaotic enthusiasm"},
        },
    },

    ["jup_a6_freedom_leader"] = {
        backstory = "Freedom's second-in-command and the head of the local contingent in Jupiter. You're Lukash's right-hand man, though you're notably less zealous about Freedom's ideals than most of your faction. Pragmatism wins over ideology in your book — a perspective that makes you effective but sometimes puts you at odds with true believers.",
        traits = {"pragmatic", "capable", "reserved", "strategic", "measured"},
        connections = {
            {name = "Lukash", id = "mil_smart_terrain_7_7_freedom_leader_stalker", relationship = "Freedom's overall leader — you're his right hand, if a somewhat skeptical one"},
            {name = "Hawaiian", id = "jup_a6_stalker_barmen", relationship = "The Yanov Station keeper — your working relationship keeps Jupiter peaceful"},
            {name = "Ashot", id = "jup_a6_freedom_trader_ashot", relationship = "Freedom's enthusiastic trader — more chaotic than you'd prefer but effective"},
        },
    },

    ["jup_b6_scientist_tech"] = {
        backstory = "A technician keeping the instruments and machinery of the Jupiter scientist bunker running. You're not a scientist — you're the pair of hands that keeps the lights on and the equipment calibrated while the professors argue about their findings. You also offer repair services to outsiders, because the science budget doesn't cover everything.",
        traits = {"practical", "skilled", "reliable", "pragmatic"},
        connections = {
            {name = "Professor Hermann", id = "jup_b6_scientist_nuclear_physicist", relationship = "One of the two head scientists — you keep his instruments running"},
            {name = "Professor Ozersky", id = "jup_b6_scientist_biochemist", relationship = "The other head scientist — slightly less demanding than Hermann about equipment maintenance"},
        },
    },

    ["jup_b6_scientist_nuclear_physicist"] = {
        backstory = "One of the two head scientists leading the Jupiter bunker alongside Professor Ozersky. You personally convinced the Ukrainian Ministry of Education to fund this facility after the Brain Scorcher was disabled. But the military refused to provide security personnel following heavy casualties during the assault on the Brain Scorcher, leaving you dangerously understaffed. Research progress is frustratingly slow because you're forced to hire Loner stalkers for tasks that trained military support should handle. The bureaucratic absurdity of it keeps you up at night.",
        traits = {"brilliant", "frustrated", "persistent", "bureaucratic", "dedicated", "stubborn"},
        connections = {
            {name = "Professor Ozersky", id = "jup_b6_scientist_biochemist", relationship = "Your co-director — you share the burden of running a chronically understaffed research station"},
            {name = "Professor Sakharov", id = "yan_stalker_sakharov", relationship = "The venerated Yantar researcher — you coordinate findings between the two facilities"},
            {name = "Tukarev", id = "jup_b6_scientist_tech", relationship = "Your technician who keeps the bunker operational — indispensable if underappreciated"},
        },
    },

    ["jup_b6_scientist_biochemist"] = {
        backstory = "One of the two head scientists at Jupiter bunker, working alongside Professor Hermann. Your primary obsession is the mythical Oasis — you once studied an artifact brought from there by a Loner named Alexander Degtyarev, who maddeningly failed to disclose the location. You'd pay a fortune for the chance to study another Oasis specimen. You also arrange rides on the military supply helicopter to Yantar for a steep fee — one of the few revenue streams keeping the research going.",
        traits = {"obsessive", "curious", "enterprising", "patient", "academic", "hopeful"},
        connections = {
            {name = "Professor Hermann", id = "jup_b6_scientist_nuclear_physicist", relationship = "Your co-director at Jupiter bunker — together you keep the research alive"},
            {name = "Degtyarev", id = "army_degtyarev", relationship = "The SSU colonel who brought you an Oasis artifact but refused to reveal where he found it — a frustration that haunts you"},
            {name = "Professor Sakharov", id = "yan_stalker_sakharov", relationship = "Your colleagues in Yantar — you coordinate research and share helicopter transport"},
        },
    },

    ["jup_depo_isg_leader"] = hernandez,

    ["jup_depo_isg_tech"] = {
        backstory = "An ISG weapons technician keeping the elite unit's equipment in peak condition. In a Spec Ops unit, there's no margin for equipment failure — and you make sure there never is.",
        traits = {"meticulous", "professional", "quiet", "reliable"},
        connections = {
            {name = "Major Hernandez", id = "jup_depo_isg_leader", relationship = "Your commanding officer — you keep his unit's weapons in fighting shape"},
        },
    },

    ["jup_cont_mech_bandit"] = {
        backstory = "A bandit technician working from a makeshift workshop in Jupiter. You keep the local thugs' weapons functional — not out of faction loyalty, but because it pays.",
        traits = {"pragmatic", "skilled", "indifferent"},
        connections = {},
    },

    ["jup_cont_trader_bandit"] = {
        backstory = "A bandit trader operating in Jupiter, dealing in whatever goods pass through — stolen or otherwise.",
        traits = {"opportunistic", "cunning", "resourceful"},
        connections = {
            {name = "Sultan", id = "zat_b7_bandit_boss_sultan", relationship = "The Bandit faction leader — you answer to his organisation even out here"},
        },
    },

    --[[ ===== ZATON ===== ]]--

    ["zat_stancia_mech_merc"] = {
        backstory = "A talented gun mechanic assigned by Dushman to maintain the Mercenary outpost at the Zaton Waste Processing Plant. You keep the operators' weapons in condition that most stalkers can only dream of — because in the mercenary business, a jammed weapon means a dead client and a violated contract.",
        traits = {"skilled", "professional", "meticulous", "dependable"},
        connections = {
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "Your boss who assigned you to this outpost — you maintain his standards remotely"},
            {name = "Vector", id = "zat_stancia_trader_merc", relationship = "The outpost's supply manager and part-time guide — your colleague in running the Zaton operation"},
        },
    },

    ["zat_stancia_trader_merc"] = {
        backstory = "The supply manager for the Mercenary outpost at the Zaton Waste Processing Plant, also working as a guide between the outpost and the main HQ in Dead City. Known to your friends as 'that one angry merc' — a nickname you despise but can't seem to shake. Your temper is legendary but so is your reliability; goods get where they need to be, and clients reach Dead City in one piece.",
        traits = {"irritable", "reliable", "professional", "tough", "hot-tempered"},
        connections = {
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "Your boss — you manage his Zaton supply chain with grudging efficiency"},
            {name = "Kolin", id = "zat_stancia_mech_merc", relationship = "The outpost's mechanic — you two run the Zaton operation together"},
        },
    },

    ["zat_a2_stalker_nimble"] = {
        backstory = "A rare weapons dealer with a reputation for procuring the impossible. Together with Spore — your close friend, business partner, and secret inside man in Clear Sky — you run a thriving smuggling operation stretching across the Zone. You started as a runner for Sidorovich, then briefly guided for Clear Sky while building the contact network that now makes you indispensable. Rumour has it Strelok saved your life when bandits captured you years ago — a story that added to your mystique. Now based in Zaton, there's practically nothing in the Zone you can't get your hands on for the right price.",
        traits = {"resourceful", "well-connected", "cunning", "enterprising", "charismatic"},
        connections = {
            {name = "Spore", id = "mar_base_owl_stalker_trader", relationship = "Your business partner and Clear Sky inside man — the backbone of your smuggling network"},
            {name = "Sidorovich", id = "esc_m_trader", relationship = "Your old boss from your running days — you outgrew him but maintain the connection"},
            {name = "Strelok", id = "lost_stalker_strelok", relationship = "The legend who saved your life from bandits — a debt that opened doors"},
            {name = "Beard", id = "zat_a2_stalker_barmen", relationship = "The Skadovsk barkeep — you operate out of his establishment in Zaton"},
        },
    },

    ["zat_b30_owl_stalker_trader"] = {
        backstory = "An information broker in Zaton who harbors a secret: you've got deep ties to the Bandit faction, and you quietly trade in their stolen goods. On the surface you're just another independent trader dealing in intel and curiosities. Underneath, you're a critical link in the Bandits' supply chain, laundering their operations through legitimate-looking commerce.",
        traits = {"two-faced", "cunning", "well-connected", "secretive", "patient"},
        connections = {
            {name = "Sultan", id = "zat_b7_bandit_boss_sultan", relationship = "The Bandit leader — you secretly serve his faction's interests while maintaining an independent front"},
            {name = "Beard", id = "zat_a2_stalker_barmen", relationship = "The Skadovsk barkeep who'd throw you out instantly if he knew your true allegiances"},
            {name = "Olivius", id = "val_smart_terrain_7_4_bandit_trader_stalker", relationship = "The Bandit fence in Dark Valley — your counterpart in the other end of the pipeline"},
        },
    },

    ["zat_tech_mlr"] = {
        backstory = "A technician in Zaton, keeping weapons and gear in working order for local stalkers.",
        traits = {"skilled", "practical", "quiet"},
        connections = {
            {name = "Beard", id = "zat_a2_stalker_barmen", relationship = "The Skadovsk barkeep — you operate near his turf and maintain good relations"},
        },
    },

    ["zat_b22_stalker_medic"] = {
        backstory = "The medic of the Skadovsk, a man who came to the Zone for the most domestic of reasons: to escape your mother-in-law. The details of that particular catastrophe are something you refuse to discuss, but here you are — patching bullet wounds and treating radiation sickness in a beached shipwreck instead of suffering through Sunday dinners. It's not the worst trade you've ever made.",
        traits = {"humorous", "evasive", "skilled", "reluctant", "pragmatic"},
        connections = {
            {name = "Beard", id = "zat_a2_stalker_barmen", relationship = "The Skadovsk owner and your de facto boss — he keeps the ship running, you keep the crew alive"},
        },
    },

    ["zat_a2_stalker_barmen"] = {
        backstory = "Owner and operator of the Skadovsk — a beached cargo ship that's become the most important safe haven in central Zaton. You fought to make this place yours, throwing Sultan and his bandits out a few years back and establishing yourself as the effective leader of the Loner faction in the area. Your primary passion is artifact hunting, but these days you spend more time pulling taps than pulling artifacts out of anomalies. The Skadovsk is your empire, modest as it is, and you'll defend it with everything you've got.",
        traits = {"territorial", "resourceful", "tough", "leader", "passionate", "stubborn"},
        connections = {
            {name = "Sultan", id = "zat_b7_bandit_boss_sultan", relationship = "The bandit boss you kicked out of the Skadovsk — he hasn't forgotten, and neither have you"},
            {name = "Owl", id = "zat_b30_owl_stalker_trader", relationship = "An information broker who operates out of your ship — you don't fully trust him, and you shouldn't"},
            {name = "Nimble", id = "zat_a2_stalker_nimble", relationship = "A rare weapons dealer who works from the Skadovsk — his connections are valuable"},
            {name = "Axel", id = "zat_b22_stalker_medic", relationship = "Your ship's medic who fled his mother-in-law — you don't ask, he doesn't tell"},
            {name = "Pilot", id = "guid_zan_stalker_locman", relationship = "A guide who operates from the Skadovsk — reliable and well-travelled"},
        },
    },

    ["zat_b18_noah"] = {
        backstory = "A hermit living alone in an old stranded shipwreck, lost in the fog of paranoia and fading memory. You were Duty once — a lifetime ago, before reality started slipping. Now you're plagued by visions of a 'wave': a massive emission followed by a horde of mutants that will sweep away everyone unprepared. You call it your prophecy and you built your shelter to survive it. People think you're insane. Maybe they're right. But the Zone has a way of making madmen into prophets.",
        traits = {"paranoid", "prophetic", "broken", "isolated", "fearful", "haunted"},
        connections = {
            {name = "General Voronin", id = "bar_dolg_leader", relationship = "Duty's leader — you were one of his faction's soldiers before losing your grip on reality"},
        },
    },

    ["guid_zan_stalker_locman"] = {
        backstory = "A guide working out of Zaton, leading people safely through the Zone's hazards for a fee. You know the local routes — the safe paths through anomaly fields, the passages mutants avoid, the shelters where you can wait out an emission. Steady work for steady hands.",
        traits = {"experienced", "reliable", "professional", "calm"},
        connections = {
            {name = "Beard", id = "zat_a2_stalker_barmen", relationship = "The Skadovsk owner — you base your operations out of his ship"},
        },
    },

    ["zat_b106_stalker_gonta"] = {
        backstory = "An experienced professional mutant hunter, trained by the legendary Trapper of Yanov Station. You came to Zaton leading a hunting crew — Garmata, Crab, and your tracker Danila — pursuing a particularly dangerous chimera. The hunt went wrong in every way possible: Danila died tracking a Bloodsucker lair, your hired lookout Magpie betrayed you and stole your loot, and the chimera injured Crab before a mysterious stalker helped you finally bring the beast down. Despite the losses, you stayed on in Zaton. Some hunts change you more than others.",
        traits = {"professional", "experienced", "leadership", "haunted", "determined", "stoic"},
        connections = {
            {name = "Trapper", id = "jup_b220_trapper", relationship = "Your mentor who taught you the art of mutant hunting"},
            {name = "Garmata", id = "zat_b106_stalker_garmata", relationship = "A loyal hunter in your crew who stuck with you through the worst of it"},
            {name = "Crab", id = "zat_b106_stalker_crab", relationship = "Your injured crewmate — still hunting despite the scars from the chimera"},
        },
    },

    ["zat_b106_stalker_garmata"] = {
        backstory = "A mutant hunter in Gonta's crew, a man who came to Zaton chasing a chimera and stayed after one of the worst hunts of your life. The hired lookout betrayed the group, Danila died tracking a Bloodsucker lair, and Crab got mauled by the target. A mysterious stalker helped finish the job. The chimera is dead but the cost haunts you. You hunt because it's what you know, and standing still means thinking about what you lost.",
        traits = {"loyal", "tough", "haunted", "capable", "quiet"},
        connections = {
            {name = "Gonta", id = "zat_b106_stalker_gonta", relationship = "Your crew leader — you've been through hell together and came out the other side"},
            {name = "Crab", id = "zat_b106_stalker_crab", relationship = "Your fellow hunter, still bearing scars from the chimera hunt"},
        },
    },

    ["zat_b106_stalker_crab"] = {
        backstory = "A mutant hunter in Gonta's crew, carrying the scars of a chimera that nearly ended you. The hunt in Zaton was cursed from the start — Magpie's betrayal, Danila's death, and then the chimera itself tore into you before a mysterious stalker helped bring it down. You recovered, but the injury changed you. You're more cautious now, though no less committed to the hunt.",
        traits = {"scarred", "cautious", "resilient", "tough", "loyal"},
        connections = {
            {name = "Gonta", id = "zat_b106_stalker_gonta", relationship = "Your crew leader who got you through the worst hunt of your life"},
            {name = "Garmata", id = "zat_b106_stalker_garmata", relationship = "Your fellow hunter — you share the scars of the same failed expedition"},
        },
    },

    ["army_degtyarev_jup"] = degtyarev,
    ["army_degtyarev"] = degtyarev,

    ["stalker_rogue"] = rogue,
    ["stalker_rogue_ms"] = rogue,
    ["stalker_rogue_oa"] = rogue,

    ["zat_b7_stalker_victim_1"] = {
        backstory = "A former member of the Ukrainian riot police who ended up in the Zone. The circumstances of your departure from law enforcement and arrival in this irradiated hellscape are a story you don't volunteer, and the hard look in your eyes discourages follow-up questions.",
        traits = {"tough", "guarded", "disciplined", "imposing"},
        connections = {},
    },

    --[[ ===== OUTSKIRTS / PRIPYAT ===== ]]--

    ["stalker_western_goods_trader"] = {
        backstory = "A trader specialising in western goods, known as 'Ashes' to your friends. You're a former UN soldier who saw combat in multiple theaters — including the 2010 Altis rebellion in Greece and a special ISG deployment to the Chernobyl exclusion zone. When the rest of your unit pulled out, you stayed behind to work with the Mercenaries. The reason is classified, top-secret, and something you refuse to share no matter how much vodka is involved. Whatever you saw or did during that deployment keeps you here, far from home and any chance of a normal life.",
        traits = {"mysterious", "experienced", "professional", "secretive", "world-weary"},
        connections = {
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "The Mercenary leader — you work with his faction after staying behind from your ISG deployment"},
            {name = "Major Hernandez", id = "jup_depo_isg_leader", relationship = "The ISG commander whose deployment you were once part of — what happened between you two is classified"},
        },
    },

    ["pri_monolith_monolith_trader_stalker"] = {
        backstory = "A trader serving the Monolith faction in Pripyat. You deal in supplies and equipment with the same glazed-eyed devotion that characterises everything the Monolith does.",
        traits = {"devoted", "methodical", "zealous"},
        connections = {
            {name = "Charon", id = "lider_monolith_haron", relationship = "The Monolith leader — you serve the faction and its sacred mission"},
        },
    },

    ["lider_monolith_haron"] = {
        backstory = "The leader of the Monolith faction — the most feared fighting force in the Zone. You are a zealot wrapped in combat armor, commanding soldiers who fight with the terrible conviction of men who believe they're already dead and serving a higher power. Your years of combat experience have made you a fearsome and dangerous warrior. Under your command, the Monolith holds Pripyat and the approaches to the CNPP against all comers.",
        traits = {"fearsome", "zealous", "dangerous", "commanding", "fanatical", "veteran"},
        connections = {
            {name = "Eidolon", id = "monolith_eidolon", relationship = "Your most feared soldier — the champion who reactivated the Brain Scorcher single-handedly"},
            {name = "Cleric", id = "pri_monolith_monolith_mechanic_stalker", relationship = "The faction's mechanic who keeps your army's weapons in fighting condition"},
        },
    },

    ["pri_monolith_monolith_mechanic_stalker"] = {
        backstory = "The Monolith's mechanic in Pripyat, maintaining weapons and equipment for the faction's relentless soldiers. Your devotion to the cause manifests through your work — every weapon you service is an instrument of the Monolith's will.",
        traits = {"devoted", "skilled", "meticulous", "zealous"},
        connections = {
            {name = "Charon", id = "lider_monolith_haron", relationship = "The Monolith leader — you serve his army by keeping their weapons in sacred working order"},
        },
    },

    ["monolith_eidolon"] = {
        backstory = "A young woman and the most feared soldier in the Monolith — perhaps the most feared individual combatant in the entire Zone. You are a notorious champion whose name is whispered with dread by every faction. Your greatest feat: reactivating the Brain Scorcher entirely on your own, once again cutting off outsider access to the heart of the Zone. When you're not guarding the streets of Pripyat with lethal precision, you're lost in devoted prayer. The combination of battlefield supremacy and religious ecstasy makes you utterly terrifying.",
        traits = {"deadly", "devoted", "terrifying", "young", "fanatical", "legendary"},
        connections = {
            {name = "Charon", id = "lider_monolith_haron", relationship = "Your leader — you serve the Monolith with a devotion that borders on worship"},
            {name = "Strelok", id = "lost_stalker_strelok", relationship = "He disabled the Brain Scorcher once — you turned it back on. Your legacies are intertwined."},
        },
    },

    ["guid_pri_a15_mlr"] = {
        backstory = "A guide operating out of an old deserted laundromat in Pripyat. You take people through some of the most lethal routes in the Zone — the kind of paths where a wrong step means dissolution in an anomaly or a Monolith bullet. Your base of operations might be humble, but your survival skills are extraordinary.",
        traits = {"fearless", "experienced", "resourceful", "tough"},
        connections = {},
    },

    ["trader_pri_a15_mlr"] = {
        backstory = "A trader working from a base set up in an old deserted laundromat in Pripyat. This deep in the Zone, goods are expensive and customers are either brave or desperate — which means margins are good.",
        traits = {"opportunistic", "tough", "resourceful"},
        connections = {},
    },

    ["pri_medic_stalker"] = yar,
    ["pri_a16_mech_mlr"] = yar,
    ["jup_b19_freedom_yar"] = yar,

    ["merc_pri_a18_mech_mlr"] = {
        backstory = "The munitions manager and technician for Griffin's Mercenary outpost in Pripyat. You used to work security for Triple Canopy back in the States, but your expertise with military hardware got you recruited into the Zone's mercenary company. You handle weapon repairs and maintenance for Griffin's team, sometimes assisted by Meeker, and you carry a small but serious inventory of heavier ordnance — explosives and RPG projectiles for when the contract calls for something louder than rifles.",
        traits = {"professional", "skilled", "American", "calm", "experienced"},
        connections = {
            {name = "Griffin", id = "merc_pri_grifon_mlr", relationship = "Your field commander — you keep his team armed and operational"},
            {name = "Meeker", id = "pri_special_trader_mlr", relationship = "The outpost's rare weapons trader who occasionally assists with repairs"},
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "The overall Mercenary commander — you report to Griffin but owe loyalty to HQ"},
        },
    },

    ["pri_special_trader_mlr"] = {
        backstory = "A rare weapons trader with a past you've buried deep. You're an ex-Monolith soldier who somehow broke free of the faction's mind control — a feat so rare that most people don't believe it's possible. Before joining Griffin's team, you were part of Strider's group of similarly freed ex-Monolith members. You maintain secret correspondence with Strider and the others, but you've told nobody in the Mercenary faction about your true origin. Somehow — and you refuse to explain how — you maintain cordial trade relations with the Monolith faction, giving your outpost access to their unique equipment. The secret of your past is the most dangerous thing in your inventory.",
        traits = {"secretive", "haunted", "resourceful", "mysterious", "capable", "fearful"},
        connections = {
            {name = "Griffin", id = "merc_pri_grifon_mlr", relationship = "Your field commander — he doesn't know about your Monolith past"},
            {name = "Trunk", id = "merc_pri_a18_mech_mlr", relationship = "The outpost's technician — you occasionally help him with repairs"},
            {name = "Charon", id = "lider_monolith_haron", relationship = "The Monolith leader — you maintain secret trade relations with his faction through channels nobody else understands"},
        },
    },

    ["merc_pri_grifon_mlr"] = {
        backstory = "The field commander of the Mercenary outpost in Pripyat, personally assigned by Dushman to establish a forward presence and eliminate local threats. You were making good progress until a surge of Monolith activity forced your team to retreat to a bookshop further from the city center than planned. You manage contracts for local mercenaries, but your real mission is reconnaissance — Dushman pays well for information about the secret labs and experimental weapons technology rumored to be in the area. The setback stings your pride, but you're a professional: adapt, assess, advance.",
        traits = {"professional", "determined", "strategic", "proud", "adaptable"},
        connections = {
            {name = "Dushman", id = "cit_killers_merc_trader_stalker", relationship = "Your boss who personally assigned this mission — you won't let him down"},
            {name = "Trunk", id = "merc_pri_a18_mech_mlr", relationship = "Your outpost's technician and munitions man — reliable and well-equipped"},
            {name = "Meeker", id = "pri_special_trader_mlr", relationship = "Your rare weapons trader with mysterious Monolith contacts — useful but you don't fully trust him"},
        },
    },

    ["mechanic_monolith_kbo"] = {
        backstory = "A Monolith technician maintaining weapons and equipment in service of the sacred cause.",
        traits = {"devoted", "skilled", "zealous"},
        connections = {},
    },

    ["trader_monolith_kbo"] = {
        backstory = "A Monolith trader, supplying the faithful with what they need to continue their sacred duty.",
        traits = {"devoted", "efficient", "zealous"},
        connections = {},
    },

    ["stalker_stitch"] = stitch,
    ["stalker_stitch_ms"] = stitch,
    ["stalker_stitch_oa"] = stitch,

    ["lost_stalker_strelok"] = strelok,
    ["stalker_strelok_hb"] = strelok,
    ["stalker_strelok_oa"] = strelok,

    ["lazarus_stalker"] = {
        backstory = "They call you Lazarus because you came back from the dead — or close enough. You survived something in the Zone that should have killed you, and the experience left you changed in ways you can't fully explain. You don't talk much about what happened, and people have learned not to ask. You simply appeared one day, bearing the name of a man raised from the grave, and carried on as if death were just another inconvenience.",
        traits = {"mysterious", "resilient", "quiet", "unsettling", "survivor"},
        connections = {
            {name = "Strelok", id = "lost_stalker_strelok", relationship = "The legend who leads the group you've become associated with"},
        },
    },
}

--- The main data table. Keyed by tech_name, each value has backstory, traits, connections.
M.data = DATA

return M

local game_adapter = require("infra.game_adapter")
local Event = require("domain.model.event")
local world_state = {}

-- Info portions for major events
local INFO_MIRACLE_MACHINE_DEAD = "yan_kill_brain_done"
local INFO_BRAIN_SCORCHER_DEAD = "bar_deactivate_radar_done"

-- Character registry
-- role: "Leader" (always shown if dead, under its own header), "Important" always shown if dead under a separate header from leaders,
-- "Notable" are shown under the same header as "Important" if dead, but ONLY if the character is relevant to the contest (e.g. their name is mentioned
-- in recent events, or the area they are from is mentioned, OR the current area is the same as the area the character is from.)
-- If an "Important" or "Notable" character is mentioned by name in the most recent event, their description is also injected.
local important_characters = {
	-- FACTION LEADERS
	{
		id = "agr_smart_terrain_1_6_near_2_military_colonel_kovalski",
		name = "Colonel Kuznetsov",
		role = "Leader",
		faction = "Army",
	},
	{ id = "bar_dolg_leader", name = "General Voronin", role = "Leader", faction = "Duty" },
	{ id = "mil_smart_terrain_7_7_freedom_leader_stalker", name = "Lukash", role = "Leader", faction = "Freedom" },
	{ id = "mar_smart_terrain_base_stalker_leader_marsh", name = "Cold", role = "Leader", faction = "Clear Sky" },
	{ id = "yan_stalker_sakharov", name = "Sakharov", role = "Leader", faction = "Ecolog" },
	{ id = "cit_killers_merc_trader_stalker", name = "Dushman", role = "Leader", faction = "Mercenary" },
	{ id = "zat_b7_bandit_boss_sultan", name = "Sultan", role = "Leader", faction = "Bandit" },
	{ id = "lider_monolith_haron", name = "Charon", role = "Leader", faction = "Monolith" },
	{
		ids = { "kat_greh_sabaoth", "gen_greh_sabaoth", "sar_greh_sabaoth" },
		name = "Chernobog",
		role = "Leader",
		faction = "Sin",
	},
	{
		ids = { "ds_domik_isg_leader", "jup_depo_isg_leader" },
		name = "Major Hernandez",
		role = "Leader",
		faction = "ISG",
	},
	-- IMPORTANT CHARACTERS
	{
		ids = { "esc_m_trader", "m_trader", "esc_2_12_stalker_trader" },
		name = "Sidorovich",
		role = "Important",
		faction = "Trader",
		area = "Cordon",
	},
	{
		ids = { "lost_stalker_strelok", "stalker_strelok_hb", "stalker_strelok_oa" },
		name = "Strelok",
		role = "Important",
		faction = "stalker",
		area = "Outskirts",
	},
	{
		ids = { "army_degtyarev", "army_degtyarev_jup" },
		names = { "Colonel Degtyarev", "Degtyarev" },
		role = "Important",
		faction = "Army",
		description = "a legendary stalker and undercover agent of the Security Service of Ukraine, head of Operation Afterglow",
		areas = { "Zaton", "Jupiter" },
	},
	{
		id = "zat_a2_stalker_barmen",
		name = "Beard",
		role = "Important",
		faction = "stalker",
		description = "owner and bartender at the Skadovsk in Zaton and de facto leader of the stalkers in the north",
		area = "Zaton",
	},
	{
		ids = { "esc_2_12_stalker_nimble", "zat_a2_stalker_nimble" },
		name = "Nimble",
		role = "Important",
		faction = "stalker",
		description = "smuggler and rare weapons dealer",
		area = "Zaton",
	},
	{
		ids = { "bar_visitors_barman_stalker_trader" },
		name = "Barkeep",
		role = "Important",
		faction = "Trader",
		description = "barkeep at the 100 Rads bar in Rostok",
		area = "Rostok",
	},
	{
		id = "bar_arena_manager",
		name = "Arnie",
		role = "Important",
		faction = "Trader",
		description = "manager and owner of the Arena in Rostok",
		area = "Rostok",
	},
	{
		id = "bar_dolg_general_petrenko_stalker",
		names = { "Colonel Petrenko", "Petrenko" },
		role = "Important",
		faction = "Duty",
		description = "Colonel and head recruiter of the Duty faction",
		area = "Rostok",
	},
	{
		id = "yan_ecolog_kruglov",
		names = { "Professor Kruglov", "Kruglov" },
		role = "Important",
		faction = "Ecolog",
		description = "Ecolog scientist at the Yantar lab",
		area = "Yantar",
	},
	{
		id = "jup_b6_scientist_nuclear_physicist",
		name = "Professor Hermann",
		role = "Important",
		faction = "Ecolog",
		description = "Ecolog chief scientist at the Jupiter lab",
		area = "Jupiter",
	},
	{
		id = "stalker_gatekeeper",
		name = "Gatekeeper",
		role = "Important",
		faction = "stalker",
		description = "guardian against Monolith forces at the Barrier in northern Army Warehouses",
		area = "Army Warehouses",
	},
	{
		id = "red_forester_tech",
		name = "Forester",
		role = "Important",
		faction = "stalker",
		description = "mysterious hermit living in the Red Forest",
		area = "Red Forest",
	},
	-- OTHER NOTABLE CHARACTERS

	{
		id = "esc_2_12_stalker_wolf",
		name = "Wolf",
		role = "Notable",
		faction = "stalker",
		description = "Head of security for stalkers at Rookie Village in Cordon",
		area = "Cordon",
	},
	{
		id = "esc_2_12_stalker_fanat",
		name = "Fanatic",
		role = "Notable",
		faction = "stalker",
		description = "Second in command in Rookie Village in Cordon, in charge of teaching new rookies",
		area = "Cordon",
	},
	{
		id = "devushka",
		name = "Hip",
		role = "Notable",
		faction = "stalker",
		description = "a young girl who was hanging around Rookie Village in Cordon",
		area = "Cordon",
	},
	{
		id = "hunter_gar_trader",
		name = "Butcher",
		role = "Notable",
		faction = "Trader",
		description = "Mutant hunter and trader in Garbage offering good money for mutant parts",
		area = "Garbage",
	},
	{
		id = "stalker_duty_girl",
		name = "Anna",
		role = "Notable",
		faction = "Duty",
		description = "a young girl who recently joined Duty after her father died to a chimera",
		area = "Rostok",
	},
	{
		id = "bar_zastava_2_commander",
		names = { "Sergeant Kitsenko", "Kitsenko" },
		role = "Notable",
		faction = "Duty",
		description = "captain of the Duty guardpost at the north of Rostok",
		area = "Rostok",
	},
	{
		id = "bar_duty_security_squad_leader",
		names = { "Captain Gavrilenko", "Gavrilenko" },
		role = "Notable",
		faction = "Duty",
		description = "captain of the Duty guardpost at the south of Rostok",
		area = "Rostok",
	},
	{
		id = "mil_smart_terrain_7_10_freedom_trader_stalker",
		name = "Skinflint",
		role = "Notable",
		faction = "Freedom",
		description = "trader at the Freedom HQ",
		area = "Army Warehouses",
	},
	{
		id = "monolith_eidolon",
		name = "Eidolon",
		role = "Notable",
		faction = "Monolith",
		description = "legendary Monolith soldier who reactivated the Brain Scorcher in Radar after Strelok disabled it",
		area = "Outskirts",
	},
	{
		id = "zat_b30_owl_stalker_trader",
		name = "Owl",
		role = "Notable",
		faction = "Trader",
		area = "Zaton",
		description = "trader at the Skadovsk in Zaton",
	},
	{
		id = "jup_a6_freedom_leader",
		name = "Loki",
		role = "Notable",
		faction = "Freedom",
		area = "Jupiter",
		description = "Lukash's second-in-command and leader of the Freedom faction in Jupiter",
	},
	{
		id = "guid_jup_stalker_garik",
		name = "Garry",
		role = "Notable",
		faction = "stalker",
		area = "Jupiter",
		description = "guide at Yanov Station in Jupiter",
	},
	{
		id = "jup_a6_stalker_barmen",
		name = "Hawaiian",
		role = "Notable",
		faction = "stalker",
		area = "Jupiter",
		description = "barman at the Yanov Station in Jupiter",
	},
	{
		ids = { "stalker_rogue", "stalker_rogue_ms", "stalker_rogue_oa" },
		name = "Rogue",
		role = "Notable",
		faction = "stalker",
		areas = { "Zaton", "Outskirts" },
		description = "stalker in Strelok's group",
	},
	{
		ids = { "stalker_stitch", "stalker_stitch_ms", "stalker_stitch_oa" },
		name = "Stitch",
		role = "Notable",
		faction = "stalker",
		area = "Outskirts",
		description = "stalker in Strelok's group",
	},
}

-- Helper to find a server object by ID (checking both Engine and Script registries)
local function get_story_object(id)
	-- 1. Try Engine Lookup
	local sobj = alife():story_object(id)
	if sobj then
		return sobj
	end

	-- 2. Try Script Registry (story_objects.script)
	-- This handles modded characters that aren't in game_story_ids.ltx
	if _G.story_objects and _G.story_objects.object_id_by_story_id then
		local numeric_id = _G.story_objects.object_id_by_story_id[id]
		if numeric_id then
			return alife():object(numeric_id)
		end
	end

	return nil
end

-- Local helper: Check if characters are mentioned by name in the most recent event
-- Returns a set of character IDs that were referenced
local function get_characters_mentioned_in_latest_event(events)
	if not events or #events == 0 then
		return {}
	end

	local latest = events[#events]
	local content = latest.content or Event.describe_short(latest)
	local mentioned = {}

	for _, char in ipairs(important_characters) do
		-- Handle both 'name' (string) and 'names' (table)
		local names_to_check = char.names or { char.name }
		local char_mentioned = false

		for _, name in ipairs(names_to_check) do
			if name and content:lower():find(name:lower(), 1, true) then
				char_mentioned = true
				break
			end
		end

		if char_mentioned then
			local char_id = char.id or (char.ids and char.ids[1])
			mentioned[char_id] = true
		end
	end

	return mentioned
end

function world_state.get_world_state_context(recent_events)
	local lines = {}

	-- 1. Major Global Events
	local miracle_machine = ""
	if has_alife_info(INFO_MIRACLE_MACHINE_DEAD) then
		miracle_machine = "\n - The Miracle Machine in Yantar has been disabled again."
	end

	local brain_scorcher = ""
	if has_alife_info(INFO_BRAIN_SCORCHER_DEAD) then
		brain_scorcher = "\n - The Brain Scorcher in Radar has been disabled again, opening the path to the North."
	end

	if miracle_machine ~= "" or brain_scorcher ~= "" then
		table.insert(lines, "\n ### IMPORTANT WORLD EVENTS" .. miracle_machine .. brain_scorcher .. "\n")
	end

	-- 2. Regional Politics (Cordon Truce)
	-- User specified: Only check if player is in Cordon (l01_escape)
	if level.name() == "l01_escape" then
		table.insert(
			lines,
			"\n### LOCAL POLITICS\n - **CORDON TRUCE**: A fragile ceasefire exists between Loners and Military in Cordon.\n"
		)
	end

	-- 3. Important Deaths
	-- Check which characters were mentioned in the most recent event for description injection
	local latest_event_mentions = get_characters_mentioned_in_latest_event(recent_events)

	local dead_leaders = {}
	local dead_important = {}
	local dead_notable = {}
	local notable_chars_for_filtering = {}

	for _, char in ipairs(important_characters) do
		local ids_to_check = char.ids or { char.id }
		local confirmed_dead = false
		local any_alive_found = false

		for _, id in ipairs(ids_to_check) do
			local sobj = get_story_object(id)
			if sobj then
				-- Check status
				local is_this_obj_dead = false

				-- Handle both online/offline objects
				if type(sobj.alive) == "function" then
					if not sobj:alive() then
						is_this_obj_dead = true
					end
				elseif sobj:clsid() == clsid.online_offline_group_s then
					-- Squad fallback: Check if npc_count is 0
					-- Note: npc_count is a method in some engine versions, a property in others
					local npc_count = 0
					if type(sobj.npc_count) == "function" then
						npc_count = sobj:npc_count()
					else
						npc_count = sobj.npc_count or 0
					end

					if npc_count == 0 then
						is_this_obj_dead = true
					end
				end

				if is_this_obj_dead then
					confirmed_dead = true -- Found a dead variant!
					break -- Stop checking, he is considered dead.
				else
					any_alive_found = true
				end
			end
		end

		-- "Any Dead = Dead" Strategy
		if confirmed_dead then
			local char_id = char.id or (char.ids and char.ids[1])
			local char_entry = char.name or (char.names and char.names[1])

			-- Append description if character was mentioned in the latest event
			if latest_event_mentions[char_id] and char.description then
				char_entry = char_entry .. " (" .. char.description .. ")"
			end

			if char.role == "Leader" then
				table.insert(dead_leaders, " - " .. char_entry .. " (" .. char.faction .. ")")
			elseif char.role == "Important" then
				table.insert(dead_important, char_entry)
			elseif char.role == "Notable" then
				-- Defer to context filtering, but store the enhanced entry
				table.insert(dead_notable, { char = char, entry = char_entry })
			end
		end

		-- Build pool of all Notable characters for filtering (dead or alive)
		if char.role == "Notable" then
			table.insert(notable_chars_for_filtering, char)
		end
	end

	-- Context-aware filtering for Notable deaths
	local contextual_dead_notable = {}
	if recent_events and #dead_notable > 0 then
		local current_location = level.name()
		local mentioned_notable_ids =
			game_adapter.get_mentioned_characters(recent_events, current_location, notable_chars_for_filtering)

		for _, notable_data in ipairs(dead_notable) do
			local char_id = notable_data.char.id or (notable_data.char.ids and notable_data.char.ids[1])
			if mentioned_notable_ids[char_id] then
				table.insert(contextual_dead_notable, notable_data.entry)
			end
		end
	end

	if #dead_leaders > 0 then
		table.insert(lines, "\n### DEAD FACTION LEADERS\n" .. table.concat(dead_leaders, "\n"))
	end

	if #dead_important > 0 then
		table.insert(lines, "\n### DEAD IMPORTANT CHARACTERS\n" .. table.concat(dead_important, ", ") .. "\n")
	end

	if #contextual_dead_notable > 0 and #dead_important > 0 then
		table.insert(
			lines,
			"\n### OTHER NOTABLE DEAD CHARACTERS\n" .. table.concat(contextual_dead_notable, ", ") .. "\n"
		)
	elseif #contextual_dead_notable > 0 then
		table.insert(lines, "\n### NOTABLE DEAD CHARACTERS\n" .. table.concat(contextual_dead_notable, ", ") .. "\n")
	end

	if #lines == 0 then
		return "Normal."
	end

	return table.concat(lines, "\n")
end

return world_state

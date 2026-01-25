package.path = package.path .. ";./bin/lua/?.lua;"
-- entities
local Event = require("domain.model.event")
local Character = require("domain.model.character")
local Item = require("domain.model.item")
local log = require("framework.logger")
local config = require("interface.config")

require("infra.STALKER.factions")
-- game interfaces
local query = talker_game_queries
local game_async = talker_game_async
local command = talker_game_commands

-- in the mod, IDs are always strings
local function get_id(obj)
	return tostring(query.get_id(obj))
end

local m = {}

------------------------------------------------------------
--- GET
------------------------------------------------------------

function m.get_characters_near(obj, distance)
	local nearby_character_objs = query.get_nearby_characters(obj, distance)
	return gameObj_to_characters(nearby_character_objs)
end

function m.get_characters_near_player(distance)
	local player_obj = query.get_player()
	if not player_obj then
		return {}
	end
	return m.get_characters_near(player_obj, distance)
end

function m.get_companions()
	local companion_objs = query.get_companions()
	return gameObj_to_characters(companion_objs)
end

function m.get_player_character()
	local player_obj = query.get_player()
	return m.create_character(player_obj)
end

function m.get_name_by_id(game_id)
	local game_obj = query.get_obj_by_id(game_id)
	return query.get_name(game_obj)
end

function m.get_character_by_id(game_id)
	local game_obj = query.get_obj_by_id(game_id)
	if game_obj then
		return m.create_character(game_obj)
	end
	return nil
end

function m.get_name(game_obj)
	if not game_obj then
		return "Unknown"
	end
	return query.get_name(game_obj)
end

------------------------------------------------------------
--- CONSTRUCTORS
------------------------------------------------------------

function gameObj_to_characters(gameObjs)
	local characters = {}
	for _, character_obj in ipairs(gameObjs) do
		local char = m.create_character(character_obj)
		-- Only add if character creation succeeded (not nil)
		if char then
			table.insert(characters, char)
		end
	end
	return characters
end

function m.create_game_event(unformatted_description, involved_objects, witnesses, flags)
	local game_time = query.get_game_time_ms()
	local world_context = query.describe_world()
	local new_event =
		Event.create_event(unformatted_description, involved_objects, game_time, world_context, witnesses, flags)
	return new_event
end

function m.create_character(game_object_person)
	if not game_object_person then
		log.debug("create_character called with nil object")
		return nil
	end
	local game_id = get_id(game_object_person)
	local name = query.get_name(game_object_person)
	local experience = query.get_rank(game_object_person)
	local raw_faction = query.get_faction(game_object_person) -- Returns "Trader" for traders, or technical faction name

	-- DISGUISE LOGIC: If this is the player, check for disguise and use TRUE faction
	local visual_faction = nil
	if m.is_player(game_id) then
		local disguise_status = m.get_player_disguise_status()
		if disguise_status and disguise_status.is_disguised then
			log.info(
				"Player is disguised. Using TRUE faction for event logging: "
					.. disguise_status.true_faction
					.. " instead of visual: "
					.. disguise_status.visual_faction
			)
			raw_faction = disguise_status.true_faction
			visual_faction = disguise_status.visual_faction
		end
	end

	local faction = get_faction_name(raw_faction) or raw_faction or "unknown" -- Map to display name, or use raw if no mapping exists
	local raw_reputation = nil
	if game_object_person.character_reputation then
		raw_reputation = game_object_person:character_reputation()
	end
	local reputation_tier = query.get_reputation_tier(raw_reputation) or "none"
	local weapon = query.get_weapon(game_object_person)
	local weapon_description = nil
	if weapon then
		weapon_description = query.get_item_description(weapon)
	end
	log.spam(
		"creating character with id: "
			.. game_id
			.. ", name: "
			.. name
			.. ", experience: "
			.. experience
			.. ", faction: "
			.. faction
			.. ", reputation: "
			.. reputation_tier
	)
	return Character.new(game_id, name, experience, faction, reputation_tier, weapon_description, visual_faction)
end

function m.get_player_weapon()
	local player_obj = query.get_player()
	local weapon_obj = query.get_weapon(player_obj)
	local weapon = m.create_item(weapon_obj)
	return weapon
end

function m.create_item(game_object_item)
	local game_id = get_id(game_object_item)
	local name = query.get_item_description(game_object_item)
	return Item.new(game_id, name)
end

function m.create_dialogue_event(speaker_id, dialogue, source_event)
	log.debug("creating dialogue event")
	local speaker_obj = query.get_obj_by_id(speaker_id)
	local speaker_char = m.create_character(speaker_obj)

	-- If speaker character creation failed, abort
	if not speaker_char then
		log.info("Failed to create speaker character for dialogue event")
		return nil
	end

	-- Use get_character_event_info to get reduced event log clutter for zombied (and hypothetically monster) characters
	local speaker_format, speaker_values = query.get_character_event_info(speaker_char)

	-- Determine witnesses based on is_whisper flag
	local witnesses
	local flags = {}

	-- Propagate is_whisper flag from source event
	if source_event and source_event.flags and source_event.flags.is_whisper then
		-- Whisper mode: only companions can witness
		witnesses = m.get_companions()
		flags = { is_whisper = true, is_dialogue = true }
		log.debug("Creating whisper dialogue event with companion-only witnesses")
		local dialogue_event = m.create_game_event(
			speaker_format .. " whispered to companions: %s",
			query.join_tables(speaker_values, { dialogue }),
			witnesses,
			flags
		)
		return dialogue_event
	else
		-- Normal mode: nearby characters can witness
		witnesses = m.get_characters_near(speaker_obj)
		flags = { is_dialogue = true }
		log.debug("Creating normal dialogue event with nearby witnesses")
		local dialogue_event = m.create_game_event(
			speaker_format .. " said: %s",
			query.join_tables(speaker_values, { dialogue }),
			witnesses,
			flags
		)
		return dialogue_event
	end
end

------------------------------------------------------------
--- FACTION LOGIC
------------------------------------------------------------

function m.get_goodwill_tier(goodwill_value)
	if goodwill_value >= 2000 then
		return "Allied"
	elseif goodwill_value >= 1500 then
		return "Trusted"
	elseif goodwill_value >= 1000 then
		return "Friendly"
	elseif goodwill_value >= 500 then
		return "Acquainted"
	elseif goodwill_value >= 0 then
		return "Neutral"
	elseif goodwill_value >= -500 then
		return "Wary"
	elseif goodwill_value >= -1000 then
		return "Hostile"
	elseif goodwill_value >= -1500 then
		return "Enemy"
	elseif goodwill_value >= -2000 then
		return "Hated"
	else
		return "Nemesis"
	end
end

function m.get_technical_faction_name(display_name)
	local faction_map = {
		["Mercenaries"] = "killer",
		["Mercs"] = "killer",
		["Mercenary"] = "killer",
		["Duty"] = "dolg",
		["Freedom"] = "freedom",
		["Bandit"] = "bandit",
		["Monolith"] = "monolith",
		["Loner"] = "stalker",
		["stalker"] = "stalker",
		["Clear Sky"] = "csky",
		["scientist"] = "ecolog",
		["egghead"] = "ecolog",
		["Ecolog"] = "ecolog",
		["Military"] = "army",
		["Army"] = "army",
		["Renegade"] = "renegade",
		["Trader"] = "trader",
		["Sin"] = "greh",
		["UNISG"] = "isg",
		["ISG"] = "isg",
		["Zombie"] = "zombied",
		["Zombied"] = "zombied",
	}
	return faction_map[display_name] or display_name:lower()
end

function m.get_player_goodwill_tier(faction_display_name)
	local tech_name = m.get_technical_faction_name(faction_display_name)
	local goodwill_value = query.get_community_goodwill(tech_name)
	return m.get_goodwill_tier(goodwill_value)
end

function m.get_faction_relation_tier(f1_display, f2_display)
	local f1_tech = m.get_technical_faction_name(f1_display)
	local f2_tech = m.get_technical_faction_name(f2_display)
	local rel_val = query.get_community_relation(f1_tech, f2_tech)

	if rel_val >= 1000 then
		return "Allied"
	elseif rel_val <= -1000 then
		return "Hostile"
	else
		return "Neutral"
	end
end

function m.get_faction_relations_string(speaker_faction, mentioned_factions_map)
	-- Include speaker faction if known
	if speaker_faction and speaker_faction ~= "unknown" then
		mentioned_factions_map[speaker_faction] = true
	end

	-- Deduplicate: use canonical names from factions.lua
	local unique_factions = {}
	for f_display, _ in pairs(mentioned_factions_map) do
		-- Convert to technical name, then back to canonical display name
		local tech_name = m.get_technical_faction_name(f_display)
		local canonical = get_faction_name(tech_name)
		if canonical then
			unique_factions[canonical] = true
		else
			-- Fallback: use the display name we have if no canonical name found
			unique_factions[f_display] = true
		end
	end

	-- Flatten and sort
	local rel_factions_list = {}
	for f, _ in pairs(unique_factions) do
		table.insert(rel_factions_list, f)
	end
	table.sort(rel_factions_list)

	-- Build relations text
	if #rel_factions_list > 1 then
		local relations = {
			["Hostile"] = {},
			["Neutral"] = {},
			["Allied"] = {},
		}

		for i = 1, #rel_factions_list do
			for j = i + 1, #rel_factions_list do
				local f1 = rel_factions_list[i]
				local f2 = rel_factions_list[j]

				-- Check for alias overlap (e.g. stalker vs Loner)
				local f1_tech = m.get_technical_faction_name(f1)
				local f2_tech = m.get_technical_faction_name(f2)

				if f1_tech ~= f2_tech then
					-- Get relation tier (Hostile/Neutral/Allied)
					local tier = m.get_faction_relation_tier(f1, f2)
					if relations[tier] then
						table.insert(relations[tier], f1 .. " - " .. f2)
					end
				end
			end
		end

		local sections = {}
		local tiers_order = { "Hostile", "Neutral", "Allied" }
		for _, tier in ipairs(tiers_order) do
			if #relations[tier] > 0 then
				local section_lines = {}
				-- Header: ### HOSTILE
				table.insert(section_lines, "### " .. tier:upper())
				for _, pair in ipairs(relations[tier]) do
					table.insert(section_lines, "- " .. pair)
				end
				table.insert(sections, table.concat(section_lines, "\n"))
			end
		end

		if #sections > 0 then
			return table.concat(sections, "\n\n")
		end
	end
	return nil
end

function m.get_mentioned_factions(events)
	local mentioned = {}
	-- Faction names as they appear in event descriptions
	local faction_names = {
		"Mercenaries",
		"Mercs",
		"Mercenary",
		"Duty",
		"Freedom",
		"Bandit",
		"Monolith",
		"Loner",
		"stalker",
		"Clear Sky",
		"scientist",
		"egghead",
		"Ecolog",
		"Army",
		"Military",
		"Renegade",
		"Trader",
		"Sin",
		"UNISG",
		"ISG",
		"Zombie",
		"Zombied",
	}

	for _, event in ipairs(events) do
		local content = event.content or Event.describe_short(event)
		for _, faction in ipairs(faction_names) do
			-- Case-insensitive search for faction name
			if content:lower():find(faction:lower(), 1, true) then
				mentioned[faction] = true
			end
		end
	end

	return mentioned
end

function m.is_player_involved(events, player_name)
	for _, event in ipairs(events) do
		local content = event.content or Event.describe_short(event)
		-- Case-insensitive search for player's name
		if content:lower():find(player_name:lower(), 1, true) then
			return true
		end
	end
	return false
end

-- Context-aware character mention detection
-- Returns a set (table with character IDs as keys) of notable characters that are contextually relevant
-- based on three checks: name in events, area in events, or current location match
function m.get_mentioned_characters(events, current_location, notable_characters)
	local mentioned = {}

	-- Helper: Check if a name appears in any event
	local function is_name_in_events(name)
		for _, event in ipairs(events) do
			local content = event.content or Event.describe_short(event)
			-- Case-insensitive search for character name
			if content:lower():find(name:lower(), 1, true) then
				return true
			end
		end
		return false
	end

	-- Helper: Check if an area is mentioned in any event
	local function is_area_in_events(area)
		for _, event in ipairs(events) do
			local content = event.content or Event.describe_short(event)
			-- Case-insensitive search for area name
			if content:lower():find(area:lower(), 1, true) then
				return true
			end
		end
		return false
	end

	-- Check each notable character against our three criteria
	for _, char in ipairs(notable_characters) do
		local char_id = char.id or (char.ids and char.ids[1])

		-- Check 1: Character name mentioned in events
		local names_to_check = char.names or { char.name }
		local name_found = false
		for _, name in ipairs(names_to_check) do
			if name and is_name_in_events(name) then
				name_found = true
				break
			end
		end

		if name_found then
			mentioned[char_id] = true
		end

		-- Check 2: Character's area mentioned in events
		if not mentioned[char_id] and char.area and is_area_in_events(char.area) then
			mentioned[char_id] = true
		end

		-- Check 3: Current location matches character's area
		if not mentioned[char_id] and char.area and char.area == current_location then
			mentioned[char_id] = true
		end
	end

	return mentioned
end

------------------------------------------------------------
--- OTHER
------------------------------------------------------------
-- ASYNCs
function m.repeat_until_true(seconds, func, ...)
	game_async.repeat_until_true(seconds, func, ...)
end

-- DIALOGUE
function m.display_dialogue(speaker_id, dialogue)
	log.debug("displaying dialogue")
	command.display_message(speaker_id, dialogue)
end

function m.display_error_to_player(message)
	command.display_hud_message(message, 3)
end

function m.display_to_player(message, seconds)
	if not config.SHOW_HUD_MESSAGES then
		return
	end
	seconds = seconds or 7
	command.display_hud_message(message, seconds)
end

function m.is_cooldown_over(LAST_GAME_TIME_MS, CD_MS)
	return (query.get_game_time_ms() - LAST_GAME_TIME_MS > CD_MS)
end

function m.get_distance(obj_id1, obj_id2)
	local obj1 = query.get_obj_by_id(obj_id1)
	local obj2 = query.get_obj_by_id(obj_id2)
	return query.get_distance_between(obj1, obj2)
end

function m.get_distance_to_player(obj_id)
	local obj = query.get_obj_by_id(obj_id)
	local player = query.get_player()
	return query.get_distance_between(obj, player)
end

-- to be moved
function m.is_player(character_id)
	return tostring(character_id) == "0"
end

local game_files = talker_game_files or require("tests.mocks.mock_game_queries") -- todo improve

-- I hotfixed this due to a loop dependency but it may also be possible that this function m.get_base_path() was just broken and requiring all of game_query
-- FILES
function m.get_base_path()
	return game_files.get_base_path()
end

function m.get_player_disguise_status()
	-- Check if gameplay_disguise script is available
	if not gameplay_disguise then
		return nil
	end

	-- Check if player is disguised
	if not gameplay_disguise.is_actor_disguised() then
		return { is_disguised = false }
	end

	-- Retrieve disguise details
	-- default_comm is the player's TRUE faction (e.g., "stalker")
	local raw_true_faction = gameplay_disguise.get_default_comm()
	-- current community is the VISUAL faction (e.g., "dolg")
	local player = query.get_player()
	local raw_visual_faction = query.get_faction(player)

	-- Map technical names to display names using our factions module
	local true_faction_display = get_faction_name(raw_true_faction) or raw_true_faction
	local visual_faction_display = get_faction_name(raw_visual_faction) or raw_visual_faction

	return {
		is_disguised = true,
		true_faction = true_faction_display,
		visual_faction = visual_faction_display,
	}
end

local is_test_env, mock_game_adapter = pcall(require, "tests.mocks.mock_game_adapter")
if false and is_test_env then
	return mock_game_adapter
end

function m.is_mock()
	return false
end

return m

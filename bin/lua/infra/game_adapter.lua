package.path = package.path .. ";./bin/lua/?.lua;"
-- entities
local Event = require("domain.model.event")
local EventType = require("domain.model.event_types")
local Character = require("domain.model.character")
local log = require("framework.logger")
local config = require("interface.config")
local engine = require("interface.engine")

require("infra.STALKER.factions")

local m = {}

------------------------------------------------------------
--- GET
------------------------------------------------------------

function m.get_characters_near(obj, distance)
	local nearby_character_objs = engine.get_nearby_characters(obj, distance)
	return gameObj_to_characters(nearby_character_objs)
end

function m.get_characters_near_player(distance)
	local player_obj = engine.get_player()
	if not player_obj then
		return {}
	end
	return m.get_characters_near(player_obj, distance)
end

function m.get_companions()
	local companion_objs = engine.get_companions()
	return gameObj_to_characters(companion_objs)
end

function m.get_player_character()
	local player_obj = engine.get_player()
	return m.create_character(player_obj)
end

function m.get_name_by_id(game_id)
	local game_obj = engine.get_obj_by_id(game_id)
	return engine.get_name(game_obj)
end

function m.get_character_by_id(game_id)
	local game_obj = engine.get_obj_by_id(game_id)
	if game_obj then
		return m.create_character(game_obj)
	end
	return nil
end

function m.get_name(game_obj)
	if not game_obj then
		return "Unknown"
	end
	return engine.get_name(game_obj)
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

function m.create_character(game_object_person)
	if not game_object_person then
		log.debug("create_character called with nil object")
		return nil
	end
	local game_id = tostring(engine.get_id(game_object_person))
	local name = engine.get_name(game_object_person)
	local experience = engine.get_rank(game_object_person)
	local raw_faction = engine.get_faction(game_object_person) -- Returns "Trader" for traders, or technical faction name

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

	local faction = raw_faction or "unknown" -- Send technical ID directly, Python resolves to display name
	local raw_reputation = nil
	if game_object_person.character_reputation then
		raw_reputation = game_object_person:character_reputation()
	end
	local reputation = raw_reputation or 0 -- Send raw integer, Python uses numeric value directly
	local weapon = engine.get_weapon(game_object_person)
	local weapon_description = nil
	if weapon then
		weapon_description = engine.get_item_description(weapon)
	end
	-- Look up story_id for important character matching (nil for generic NPCs)
	local story_id = engine.get_story_id(game_id)
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
			.. tostring(reputation)
			.. ", story_id: "
			.. tostring(story_id)
	)
	return Character.new(game_id, name, experience, faction, reputation, weapon_description, visual_faction, story_id)
end

function m.create_dialogue_event(speaker_id, dialogue, source_event)
	log.debug("creating dialogue event")
	local speaker_obj = engine.get_obj_by_id(speaker_id)
	local speaker_char = m.create_character(speaker_obj)

	-- If speaker character creation failed, abort
	if not speaker_char then
		log.info("Failed to create speaker character for dialogue event")
		return nil
	end

	-- Determine witnesses based on is_whisper flag
	local witnesses
	local flags = {}

	-- Create typed dialogue event context
	local context = {
		speaker = speaker_char,
		text = dialogue,
	}

	-- Propagate is_whisper flag from source event
	if source_event and source_event.flags and source_event.flags.is_whisper then
		-- Whisper mode: only companions can witness
		witnesses = m.get_companions()
		flags = { is_whisper = true, is_dialogue = true }
		context.is_whisper = true
		log.debug("Creating whisper dialogue event with companion-only witnesses")
	else
		-- Normal mode: nearby characters can witness
		witnesses = m.get_characters_near(speaker_obj)
		flags = { is_dialogue = true }
		log.debug("Creating normal dialogue event with nearby witnesses")
	end

	-- Create typed dialogue event
	local game_time = engine.get_game_time_ms()
	local world_context = engine.describe_world()
	local dialogue_event = Event.create(EventType.DIALOGUE, context, game_time, world_context, witnesses, flags)

	return dialogue_event
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
	local goodwill_value = engine.get_community_goodwill(tech_name)
	return m.get_goodwill_tier(goodwill_value)
end

function m.get_faction_relation_tier(f1_display, f2_display)
	local f1_tech = m.get_technical_faction_name(f1_display)
	local f2_tech = m.get_technical_faction_name(f2_display)
	local rel_val = engine.get_community_relation(f1_tech, f2_tech)

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
		local tech_name = m.get_technical_faction_name(f_display)
		local canonical = get_faction_name(tech_name)
		if canonical then
			unique_factions[canonical] = true
		else
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

				local f1_tech = m.get_technical_faction_name(f1)
				local f2_tech = m.get_technical_faction_name(f2)

				if f1_tech ~= f2_tech then
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

------------------------------------------------------------
--- OTHER
------------------------------------------------------------
-- ASYNCs
function m.repeat_until_true(seconds, func, ...)
	engine.repeat_until_true(seconds, func, ...)
end

-- DIALOGUE
function m.display_dialogue(speaker_id, dialogue)
	log.debug("displaying dialogue")
	engine.display_message(speaker_id, dialogue)
end

function m.display_error_to_player(message)
	engine.display_hud_message(message, 3)
end

function m.display_to_player(message, seconds)
	if not config.SHOW_HUD_MESSAGES then
		return
	end
	seconds = seconds or 7
	engine.display_hud_message(message, seconds)
end

function m.is_cooldown_over(LAST_GAME_TIME_MS, CD_MS)
	return (engine.get_game_time_ms() - LAST_GAME_TIME_MS > CD_MS)
end

function m.get_distance(obj_id1, obj_id2)
	local obj1 = engine.get_obj_by_id(obj_id1)
	local obj2 = engine.get_obj_by_id(obj_id2)
	return engine.get_distance_between(obj1, obj2)
end

function m.get_distance_to_player(obj_id)
	local obj = engine.get_obj_by_id(obj_id)
	local player = engine.get_player()
	return engine.get_distance_between(obj, player)
end

-- to be moved
function m.is_player(character_id)
	return tostring(character_id) == "0"
end

-- FILES
function m.get_base_path()
	return engine.get_base_path()
end

function m.get_player_disguise_status()
	---@diagnostic disable-next-line: undefined-global
	if not gameplay_disguise then
		return nil
	end

	---@diagnostic disable-next-line: undefined-global
	if not gameplay_disguise.is_actor_disguised() then
		return { is_disguised = false }
	end

	-- default_comm is the player's TRUE faction (e.g., "stalker")
	---@diagnostic disable-next-line: undefined-global
	local raw_true_faction = gameplay_disguise.get_default_comm()
	-- current community is the VISUAL faction (e.g., "dolg")
	local player = engine.get_player()
	local raw_visual_faction = engine.get_faction(player)

	local true_faction_display = get_faction_name(raw_true_faction) or raw_true_faction
	local visual_faction_display = get_faction_name(raw_visual_faction) or raw_visual_faction

	return {
		is_disguised = true,
		true_faction = true_faction_display,
		visual_faction = visual_faction_display,
	}
end

function m.is_mock()
	return false
end

return m

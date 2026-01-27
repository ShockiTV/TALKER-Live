-- interface.lua
local log = require("framework.logger")
local talker = require("app.talker")
local game_adapter = require("infra.game_adapter")
local AI_request = require("infra.AI.requests")
local Event = require("domain.model.event")
local queries = talker_game_queries

-- game interfaces
local query = talker_game_queries

local m = {}

--- Instructs a specific character to perform a dialogue action, used for idle conversation prompts
function m.register_character_instructions(unformatted_description, character, important, flags)
	local witnesses = game_adapter.get_characters_near_player()
	return m.register_game_event(unformatted_description, { character }, witnesses, important, flags)
end

-- prototype

function m.register_game_event_near_player(unformatted_description, involved_objects, important)
	local witnesses = game_adapter.get_characters_near_player()
	return m.register_game_event(unformatted_description, involved_objects, witnesses, important, nil)
end

-- Register a silent event near the player (event goes to store but doesn't trigger dialogue)
function m.register_silent_event_near_player(unformatted_description, involved_objects)
	local witnesses = game_adapter.get_characters_near_player()
	local flags = { is_silent = true }
	return m.register_game_event(unformatted_description, involved_objects, witnesses, false, flags)
end

-- Register a silent event with custom witnesses (event goes to store but doesn't trigger dialogue)
function m.register_silent_event(unformatted_description, event_objects, witnesses, flags)
	-- Merge user flags with is_silent flag
	local merged_flags = flags or {}
	merged_flags.is_silent = true
	return m.register_game_event(unformatted_description, event_objects, witnesses, false, merged_flags)
end

----------------------------------------------------------------------------------------------------
-- TYPED EVENT REGISTRATION (New system)
----------------------------------------------------------------------------------------------------

-- Internal: create and register a typed event
local function register_typed_event_internal(event_type, context, witnesses, important, flags)
	log.info("Registering typed event: %s", tostring(event_type))

	-- Get game time and world context from game adapter
	local game_time = query.get_game_time_ms()
	local world_context = query.describe_world()

	-- Create typed event using Event.create
	local new_event = Event.create(event_type, context, game_time, world_context, witnesses, flags)
	log.debug("New typed event: %s", new_event)

	talker.register_event(new_event, important)
	return true
end

-- Register a typed event with explicit witnesses
function m.register_typed_event(event_type, context, witnesses, important, flags)
	local success, error = pcall(register_typed_event_internal, event_type, context, witnesses, important, flags)
	if not success then
		log.error("Failed to register typed event: %s", error)
		return false
	end
	return true
end

-- Register a typed event near the player (auto-populates witnesses)
function m.register_typed_event_near_player(event_type, context, important, flags)
	local witnesses = game_adapter.get_characters_near_player()
	return m.register_typed_event(event_type, context, witnesses, important, flags)
end

----------------------------------------------------------------------------------------------------
-- LEGACY EVENT REGISTRATION
----------------------------------------------------------------------------------------------------

local function register_game_event(unformatted_description, event_objects, witnesses, important, flags)
	log.info("Registering game event")
	local new_event = game_adapter.create_game_event(unformatted_description, event_objects, witnesses, flags)
	log.debug("New event: %s", new_event)
	talker.register_event(new_event, important)
end

-- prevents issues later down the line with formatting
local function check_format_sanity(unformatted_description, ...)
	local additional_args = { ... }
	local format_count = select(2, unformatted_description:gsub("%%s", ""))
	-- returns true if the amounts of variables like %s match the amount of arguments
	if (format_count > 0) and (format_count > #unpack(additional_args)) then
		log.error("Not enough arguments for description: %s", unformatted_description)
		return false
	end
	return true
end

function m.register_game_event(unformatted_description, event_objects, witnesses, important, flags)
	if not check_format_sanity(unformatted_description, event_objects) then
		return false
	end
	local success, error =
		pcall(register_game_event, unformatted_description, event_objects, witnesses, important, flags)
	if not success then
		log.error("Failed to register game event: %s", error)
		return false
	end
	return true
end

-- SEND PLAYER DIALOGUE TO GAME
----------------------------------------------------------------------------------------------------

-- function recorder.to register the player's dialogue as a game event
function m.player_character_speaks(dialogue)
	log.info("Registering player speak event. Player said: " .. dialogue)
	local player = game_adapter.get_player_character()
	local player_fmt, player_vals = queries.get_character_event_info(player)
	local values = queries.join_tables(player_vals, { dialogue })
	-- register new events
	m.register_game_event_near_player(player_fmt .. " said: %s", values, true)
	-- show dialogue in game UI
	game_adapter.display_dialogue(player.game_id, dialogue)
end

return m

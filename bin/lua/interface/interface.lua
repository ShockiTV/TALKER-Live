-- interface.lua
local log = require("framework.logger")
local talker = require("app.talker")
local game_adapter = require("infra.game_adapter")
local AI_request = require("infra.AI.requests")

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
	-- register new event
	m.register_game_event_near_player(
		"%s, a %s rank member of the %s faction with %s reputation said: %s",
		{ player.name, player.experience, player.faction, player.reputation, dialogue },
		true
	)
	-- show dialogue in game UI
	game_adapter.display_dialogue(player.game_id, dialogue)
end

return m

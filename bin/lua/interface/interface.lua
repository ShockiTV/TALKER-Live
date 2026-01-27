-- interface.lua
local log = require("framework.logger")
local talker = require("app.talker")
local game_adapter = require("infra.game_adapter")
local AI_request = require("infra.AI.requests")
local Event = require("domain.model.event")
local EventType = require("domain.model.event_types")

-- game interfaces
local query = talker_game_queries

local m = {}

----------------------------------------------------------------------------------------------------
-- TYPED EVENT REGISTRATION
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
-- PLAYER DIALOGUE
----------------------------------------------------------------------------------------------------

-- Register the player's dialogue as a typed event
function m.player_character_speaks(dialogue)
	log.info("Registering player speak event. Player said: " .. dialogue)
	local player = game_adapter.get_player_character()

	-- Create typed DIALOGUE event
	local context = {
		speaker = player,
		text = dialogue,
	}

	m.register_typed_event_near_player(EventType.DIALOGUE, context, true, nil)

	-- show dialogue in game UI
	game_adapter.display_dialogue(player.game_id, dialogue)
end

return m

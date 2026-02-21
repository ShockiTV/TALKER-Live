-- interface.lua
local log = require("framework.logger")
local talker = require("app.talker")
local game_adapter = require("infra.game_adapter")
local Event = require("domain.model.event")
local EventType = require("domain.model.event_types")
local engine = require("interface.engine")

-- zmq_integration may be nil if not loaded yet
---@diagnostic disable-next-line: undefined-global
local zmq_integration = talker_zmq_integration

local m = {}

----------------------------------------------------------------------------------------------------
-- ZMQ PUBLISHING (Parallel to existing event flow)
----------------------------------------------------------------------------------------------------

-- Safely publish event to ZMQ if integration is available
local function zmq_publish_event(event, important)
	if zmq_integration and zmq_integration.publish_game_event then
		local ok, err = pcall(zmq_integration.publish_game_event, event, important)
		if not ok then
			log.debug("ZMQ publish failed: " .. tostring(err))
		end
	end
end

-- Safely publish player dialogue to ZMQ
local function zmq_publish_player_dialogue(text, context)
	if zmq_integration and zmq_integration.publish_player_dialogue then
		local ok, err = pcall(zmq_integration.publish_player_dialogue, text, context)
		if not ok then
			log.debug("ZMQ player dialogue publish failed: " .. tostring(err))
		end
	end
end

----------------------------------------------------------------------------------------------------
-- TYPED EVENT REGISTRATION
----------------------------------------------------------------------------------------------------

-- Internal: create and register a typed event
local function register_typed_event_internal(event_type, context, witnesses, important, flags)
	log.info("Registering typed event: %s", tostring(event_type))

	-- Get game time from engine facade
	local game_time = engine.get_game_time_ms()

	-- Create typed event using Event.create
	local new_event = Event.create(event_type, context, game_time, witnesses, flags)
	log.debug("New typed event: %s", new_event)

	-- PARALLEL: Publish to ZMQ (fire-and-forget, won't block)
	zmq_publish_event(new_event, important)

	-- Existing flow: register with talker (triggers AI dialogue generation)
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

	-- PARALLEL: Publish player dialogue to ZMQ
	zmq_publish_player_dialogue(dialogue, { speaker = player })

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

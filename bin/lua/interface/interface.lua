-- interface.lua
local log = require("framework.logger")
local talker = require("app.talker")
local game_adapter = require("infra.game_adapter")
local Event = require("domain.model.event")
local EventType = require("domain.model.event_types")
local engine = require("interface.engine")

-- ws_integration may be nil if not loaded yet
---@diagnostic disable-next-line: undefined-global
local ws_integration = talker_ws_integration

local m = {}

----------------------------------------------------------------------------------------------------
-- EVENT PUBLISHING (via WebSocket)
----------------------------------------------------------------------------------------------------

-- Safely publish event to Python service if WS integration is available
local function ws_publish_event(event, important)
	if ws_integration and ws_integration.publish_game_event then
		local ok, err = pcall(ws_integration.publish_game_event, event, important)
		if not ok then
			log.debug("WS publish failed: " .. tostring(err))
		end
	end
end

-- Safely publish player dialogue to Python service
local function ws_publish_player_dialogue(text, context)
	if ws_integration and ws_integration.publish_player_dialogue then
		local ok, err = pcall(ws_integration.publish_player_dialogue, text, context)
		if not ok then
			log.debug("WS player dialogue publish failed: " .. tostring(err))
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

	-- Publish to Python service (fire-and-forget, won't block)
	ws_publish_event(new_event, important)

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

	-- Publish player dialogue to Python service
	ws_publish_player_dialogue(dialogue, { speaker = player })

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

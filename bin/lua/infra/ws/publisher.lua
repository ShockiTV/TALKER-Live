-- infra/ws/publisher.lua
-- WS event publisher (task 3.4)
-- Sends events to Python service with candidates, world context, and traits

local log = require("framework.logger")
local engine = require("interface.engine")

local M = {}

--- Publish an event to Python service via WS.
-- Assembles the new payload format: {event, candidates, world, traits}
-- @param event       Event object with type, context, witnesses, timestamp
-- @param candidates  Array of candidate NPCs (speaker + witnesses)
-- @param world       World description string (location, time, weather)
-- @param traits      Traits map: {character_id → {personality_id, backstory_id}}
function M.send_game_event(event, candidates, world, traits)
	log.debug("WS publisher: event type=%s, candidates=%d", tostring(event.type), candidates and #candidates or 0)
	
	-- Delegate to game script via callback for now (task 3.5 will update serialization)
	-- Pass all four components for the new payload structure
	engine.SendScriptCallback("publish_game_event_v2", event, candidates, world, traits)
end

return M

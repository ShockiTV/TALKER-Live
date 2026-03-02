package.path = package.path .. ";./bin/lua/?.lua;"
local memory_store_v2 = require("domain.repo.memory_store_v2")
local logger = require("framework.logger")
local game_adapter = require("infra.game_adapter")

local talker = {}

--- Register an event in the store.
-- The Python service handles all AI dialogue generation via WebSocket.
-- This function only stores events - Python receives them via the WS publisher.
function talker.register_event(event, is_important)
	logger.info("talker.register_event")
	local actor = event and event.context and event.context.actor
	if actor and actor.game_id then
		memory_store_v2:store_event(actor.game_id, event)
	else
		logger.warn("register_event: missing context.actor; event not stored")
	end

	-- Silent events go into the store but don't generate dialogue
	if event.flags and event.flags.is_silent then
		logger.info("Silent event registered - no dialogue will be generated")
		return
	end

	-- Python service receives events via WS and handles dialogue generation
	logger.info("Event stored - dialogue generation handled by Python service via WS")
end

-- for mocking
function talker.set_game_adapter(adapter)
	game_adapter = adapter
end

return talker

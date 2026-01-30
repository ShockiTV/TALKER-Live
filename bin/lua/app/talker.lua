package.path = package.path .. ";./bin/lua/?.lua;"
local event_store = require("domain.repo.event_store")
local logger = require("framework.logger")
local game_adapter = require("infra.game_adapter")

local talker = {}

--- Register an event in the store.
-- The Python service handles all AI dialogue generation via ZMQ.
-- This function only stores events - Python receives them via the ZMQ publisher.
function talker.register_event(event, is_important)
	logger.info("talker.register_event")
	event_store:store_event(event)

	-- Silent events go into the store but don't generate dialogue
	if event.flags and event.flags.is_silent then
		logger.info("Silent event registered - no dialogue will be generated")
		return
	end

	-- Python service receives events via ZMQ and handles dialogue generation
	logger.info("Event stored - dialogue generation handled by Python service via ZMQ")
end

-- for mocking
function talker.set_game_adapter(adapter)
	game_adapter = adapter
end

return talker

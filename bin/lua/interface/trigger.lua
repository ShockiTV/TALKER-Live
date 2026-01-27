local log = require("framework.logger")
local Event = require("domain.model.event")
local EventType = require("domain.model.event_types")

local c = talker_game_commands

local m = {}

-- NEW: Typed event trigger (Phase 2+)
-- Creates a typed event and sends it via callback
function m.talker_event(event_type, context, witnesses, important, flags)
	log.debug("Calling trigger talker_event with type: %s", tostring(event_type))

	-- Validate event type
	if not event_type then
		log.error("talker_event called with nil event_type")
		return
	end

	-- Send as typed event via new callback
	c.SendScriptCallback("talker_event", event_type, context, witnesses, important, flags)
end

-- NEW: Convenience function for typed events near player
function m.talker_event_near_player(event_type, context, important, flags)
	log.debug("Calling trigger talker_event_near_player with type: %s", tostring(event_type))
	c.SendScriptCallback("talker_event_near_player", event_type, context, important, flags)
end

function m.talker_player_speaks(dialogue)
	log.debug("Calling trigger talker_player_speaks with arg: %s", dialogue)
	c.SendScriptCallback("talker_player_speaks", dialogue)
end

function m.talker_player_whispers(dialogue)
	log.debug("Calling trigger talker_player_whispers with arg: %s", dialogue)
	c.SendScriptCallback("talker_player_whispers", dialogue)
end



-- Expose EventType for triggers to use
m.EventType = EventType

return m

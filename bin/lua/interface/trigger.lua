local log = require("framework.logger")
local EventType = require("domain.model.event_types")
local Event = require("domain.model.event")
local engine = require("interface.engine")
local memory_store_v2 = require("domain.repo.memory_store_v2")
local publisher = require("infra.ws.publisher")
local traits_builder = require("interface.traits")
local world_description = require("interface.world_description")

local m = {}

-- NEW (Section 3.1): Unified trigger function for structured events
-- Creates event, stores in speaker memory, fans out to witnesses, publishes to Python
-- @param event_type    EventType enum value
-- @param context       Table with event context (actor, victim, etc.)
-- @param witnesses     Array of NPC characters who witnessed the event
-- @param flags         Optional table of flags (is_silent, etc.)
-- @return event        The created Event object
function m.store_and_publish(event_type, context, witnesses, flags)
	log.debug("trigger.store_and_publish: type=%s, witnesses=%d", tostring(event_type), witnesses and #witnesses or 0)

	-- Validate inputs
	if not event_type then
		log.error("store_and_publish: event_type required")
		return nil
	end

	local speaker = context and context.actor
	if not speaker or not speaker.game_id then
		log.error("store_and_publish: context.actor (speaker) required")
		return nil
	end

	-- Create event with timestamp
	local event = Event.create(event_type, context, engine.get_game_time_ms(), witnesses or {}, flags or {})

	-- Store in speaker's memory
	memory_store_v2:store_event(speaker.game_id, event)

	-- Fan out to witnesses
	memory_store_v2:fan_out(event, witnesses or {})

	-- Build candidates list (speaker + witnesses)
	local candidates = { speaker }
	for _, witness in ipairs(witnesses or {}) do
		table.insert(candidates, witness)
	end

	-- Build traits map for all candidates
	local traits = traits_builder.build_traits_map(candidates)

	-- Build world context (speaker provides location context, no specific listener)
	local world = engine.describe_world(speaker, nil)

	-- Publish to Python via WS with full context
	publisher.send_game_event(event, candidates, world, traits)

	log.debug("Event stored and published: %s", event_type)
	return event
end

-- Expose EventType for triggers to use
m.EventType = EventType

-- OLD: Typed event trigger (Phase 2+) - KEPT for backward compatibility
-- Creates a typed event and sends it via callback
function m.talker_event(event_type, context, witnesses, important, flags)
	log.debug("Calling trigger talker_event with type: %s", tostring(event_type))

	-- Validate event type
	if not event_type then
		log.error("talker_event called with nil event_type")
		return
	end

	-- Send as typed event via new callback
	engine.SendScriptCallback("talker_event", event_type, context, witnesses, important, flags)
end

-- OLD: Convenience function for typed events near player - KEPT for backward compatibility
function m.talker_event_near_player(event_type, context, important, flags)
	log.debug("Calling trigger talker_event_near_player with type: %s", tostring(event_type))
	engine.SendScriptCallback("talker_event_near_player", event_type, context, important, flags)
end

function m.talker_player_speaks(dialogue)
	log.debug("Calling trigger talker_player_speaks with arg: %s", dialogue)
	engine.SendScriptCallback("talker_player_speaks", dialogue)
end

function m.talker_player_whispers(dialogue)
	log.debug("Calling trigger talker_player_whispers with arg: %s", dialogue)
	engine.SendScriptCallback("talker_player_whispers", dialogue)
end

return m

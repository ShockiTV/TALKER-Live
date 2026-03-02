local log = require("framework.logger")
local EventType = require("domain.model.event_types")
local Event = require("domain.model.event")
local engine = require("interface.engine")
local memory_store_v2 = require("domain.repo.memory_store_v2")
local publisher = require("infra.ws.publisher")
local traits_builder = require("interface.traits")

local m = {}

--- Validate common inputs for store/publish functions.
-- @return speaker character or nil on validation failure
local function validate_inputs(func_name, event_type, context)
	if not event_type then
		log.error("%s: event_type required", func_name)
		return nil
	end
	local speaker = context and context.actor
	if not speaker or not speaker.game_id then
		log.error("%s: context.actor (speaker) required", func_name)
		return nil
	end
	return speaker
end

--- Store an event in memory only (no WS publish).
-- Creates Event, stores in speaker memory, fans out to witnesses.
-- @param event_type    EventType enum value
-- @param context       Table with event context (actor, victim, etc.)
-- @param witnesses     Array of NPC characters who witnessed the event
-- @return event        The created Event object, or nil on error
function m.store_event(event_type, context, witnesses)
	log.debug("trigger.store_event: type=%s, witnesses=%d", tostring(event_type), witnesses and #witnesses or 0)

	local speaker = validate_inputs("store_event", event_type, context)
	if not speaker then return nil end

	-- Create event with empty flags (flags are deprecated)
	local event = Event.create(event_type, context, engine.get_game_time_ms(), witnesses or {}, {})

	-- Store in speaker's memory
	memory_store_v2:store_event(speaker.game_id, event)

	-- Fan out to witnesses
	memory_store_v2:fan_out(event, witnesses or {})

	log.debug("Event stored (no publish): %s", event_type)
	return event
end

--- Store an event AND publish it to Python for dialogue generation.
-- Calls store_event internally, then publishes via WS.
-- @param event_type    EventType enum value
-- @param context       Table with event context (actor, victim, etc.)
-- @param witnesses     Array of NPC characters who witnessed the event
-- @return event        The created Event object, or nil on error
function m.publish_event(event_type, context, witnesses)
	log.debug("trigger.publish_event: type=%s, witnesses=%d", tostring(event_type), witnesses and #witnesses or 0)

	-- Store event first (memory + fan-out)
	local event = m.store_event(event_type, context, witnesses)
	if not event then return nil end

	local speaker = context.actor

	-- Build candidates list (speaker first, then witnesses)
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

function m.talker_player_speaks(dialogue)
	log.debug("Calling trigger talker_player_speaks with arg: %s", dialogue)
	engine.SendScriptCallback("talker_player_speaks", dialogue)
end

function m.talker_player_whispers(dialogue)
	log.debug("Calling trigger talker_player_whispers with arg: %s", dialogue)
	engine.SendScriptCallback("talker_player_whispers", dialogue)
end

return m

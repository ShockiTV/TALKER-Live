local log = require("framework.logger")
local EventType = require("domain.model.event_types")
local Event = require("domain.model.event")
local engine = require("interface.engine")
local unique_ts = require("domain.service.unique_ts")
local memory_store_v2 = require("domain.repo.memory_store_v2")
local publisher = require("infra.ws.publisher")
local traits_builder = require("interface.traits")

local m = {}
local validate_inputs

local function build_unique_candidates(speaker, witnesses, include_player)
	local candidates = {}
	local seen = {}

	local function maybe_add(char)
		if not char or not char.game_id then return end
		local id = tostring(char.game_id)
		if (not include_player) and id == "0" then return end
		if seen[id] then return end
		seen[id] = true
		table.insert(candidates, char)
	end

	maybe_add(speaker)
	for _, witness in ipairs(witnesses or {}) do
		maybe_add(witness)
	end

	return candidates
end

local function store_event_internal(event_type, context, witnesses, flags)
	local speaker = validate_inputs("store_event", event_type, context)
	if not speaker then return nil, nil end

	local ts = unique_ts.unique_ts()
	local event = Event.create(event_type, context, engine.get_game_time_ms(), witnesses or {}, flags or {}, ts)

	local stored = memory_store_v2:store_event(speaker.game_id, event)
	event.cs = stored and stored.cs or event.cs
	memory_store_v2:fan_out(event, witnesses or {})

	return event, speaker
end

--- Validate common inputs for store/publish functions.
-- @return speaker character or nil on validation failure
validate_inputs = function(func_name, event_type, context)
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

	local event, speaker = store_event_internal(event_type, context, witnesses, { index_only = true })
	if not event then return nil end

	local candidates = build_unique_candidates(speaker, witnesses or {}, true)
	local traits = traits_builder.build_traits_map(candidates)
	local world = engine.describe_world(speaker, nil)
	publisher.send_game_event(event, candidates, world, traits)

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

	-- Store event first (memory + fan-out); unique_ts assigned internally
	local event, speaker = store_event_internal(event_type, context, witnesses, {})
	if not event then return nil end
	local is_player = tostring(speaker.game_id) == "0"

	-- Build candidates list (NPC speakers/witnesses only — never the player).
	-- The player's input is already in the event context; candidates are NPCs
	-- who may *respond*.
	local candidates = {}
	if not is_player then
		table.insert(candidates, speaker)
	end
	for _, witness in ipairs(witnesses or {}) do
		if tostring(witness.game_id) ~= "0" then
			table.insert(candidates, witness)
		end
	end

	if #candidates == 0 then
		log.debug("publish_event: no NPC candidates after filtering player, skipping publish")
		return event
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

package.path = package.path .. ";./bin/lua/?.lua;"
local Item = require("domain.model.item")
local EventType = require("domain.model.event_types")

-- Event data structure
local Event = {}

-- Expose EventType enum for external use
Event.TYPE = EventType

-- Typed event constructor
-- Note: world_context parameter removed - world context is now queried JIT during prompt building
function Event.create(type, context, game_time_ms, witnesses, flags)
	return {
		type = type,
		context = context or {},
		game_time_ms = game_time_ms,
		witnesses = witnesses or {},
		flags = flags or {},
	}
end

function Event.was_conversation(event)
	return event.source_event ~= nil
end

-- NEW: Extract all characters referenced in event context
-- Works for both typed events (context) and legacy events (involved_objects)
function Event.get_involved_characters(event)
	-- Legacy event path
	if event.involved_objects and #event.involved_objects > 0 then
		local characters = {}
		for _, obj in ipairs(event.involved_objects) do
			if type(obj) == "table" and obj.game_id then
				table.insert(characters, obj)
			end
		end
		return characters
	end

	-- Typed event path: extract from context
	if not event.context then
		return {}
	end

	local characters = {}
	local character_keys = {
		"victim",
		"killer",
		"actor",
		"spotter",
		"target",
		"taunter",
		"speaker",
	}

	for _, key in ipairs(character_keys) do
		local val = event.context[key]
		if val and type(val) == "table" and val.game_id then
			table.insert(characters, val)
		end
	end

	-- Handle companions array
	if event.context.companions then
		for _, char in ipairs(event.context.companions) do
			if char and char.game_id then
				table.insert(characters, char)
			end
		end
	end

	return characters
end

-- Define junk event types that should be filtered in narrative compression
local JUNK_EVENT_TYPES = {
	[EventType.ARTIFACT] = true,
	[EventType.ANOMALY] = true,
	[EventType.RELOAD] = true,
	[EventType.WEAPON_JAM] = true,
	[EventType.CALLOUT] = true,
	[EventType.TAUNT] = true,
}

-- Check if event is "junk" (low-value for narrative compression)
-- Works with both typed events and legacy flag-based events
function Event.is_junk_event(event)
	-- Check typed events first
	if event.type and JUNK_EVENT_TYPES[event.type] then
		return true
	end

	-- Fallback for legacy flag-based events
	local flags = event.flags
	if flags then
		if flags.is_artifact
			or flags.is_anomaly
			or flags.is_reload
			or flags.is_weapon_jam
			or flags.is_callout
			or flags.is_taunt then
			return true
		end
	end

	return false
end

function Event.was_witnessed_by(event, character_id)
	if not event or not event.witnesses then
		return false
	end

	for _, witness in ipairs(event.witnesses) do
		-- Defensive: check if witness and witness.game_id exist
		if witness and witness.game_id and tostring(witness.game_id) == tostring(character_id) then
			return true
		end
	end
	return false
end

return Event

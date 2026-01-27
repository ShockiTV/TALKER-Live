package.path = package.path .. ";./bin/lua/?.lua;"
local Item = require("domain.model.item")
local EventType = require("domain.model.event_types")

-- Event data structure
local Event = {}

-- Expose EventType enum for external use
Event.TYPE = EventType

-- Legacy type templates (deprecated, kept for compatibility)
Event.LEGACY_TYPE = {
	DIALOGUE = "%s: '%s'",
	ACTION = "%s %s %s",
	KILL = "%s killed %s",
	SPOT = "%s spotted %s",
	HEAR = "%s heard %s",
}

-- NEW: Typed event constructor
function Event.create(type, context, game_time_ms, world_context, witnesses, flags)
	return {
		type = type,
		context = context or {},
		game_time_ms = game_time_ms,
		world_context = world_context,
		witnesses = witnesses or {},
		flags = flags or {},
	}
end

-- DEPRECATED: Old event constructor (keep for compatibility during migration)
function Event.create_event(
	unformatted_description_or_type,
	involved_objects,
	game_time_ms,
	world_context,
	witnesses,
	flags,
	source_event
)
	local event = {}
	event.description = unformatted_description_or_type
	event.involved_objects = involved_objects or {}
	event.game_time_ms = game_time_ms
	event.world_context = world_context
	event.witnesses = witnesses or {}
	event.flags = flags or {} -- Add flags to the event object
	event.source_event = source_event
	return event
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
		return flags.is_artifact
			or flags.is_anomaly
			or flags.is_reload
			or flags.is_weapon_jam
			or flags.is_callout
			or flags.is_taunt
	end

	return false
end

function table_to_args(table_input)
	local args = {}
	for key, value in pairs(table_input) do
		table.insert(args, value)
	end
	return unpack(args)
end

function Event.describe_event(event)
	local unformatted_description = event.description
	local involved_object_descriptions = {}
	for _, object in ipairs(event.involved_objects) do
		if type(object) == "string" then
			table.insert(involved_object_descriptions, object)
		else
			table.insert(involved_object_descriptions, Item.describe_short(object))
		end
	end
	return string.format(unformatted_description, table_to_args(involved_object_descriptions))
end

-- Template functions for typed events
-- Each returns: template_string, {objects_to_format}
local TEMPLATES = {
	[EventType.DEATH] = function(ctx)
		if ctx.killer then
			return "%s was killed by %s!", { ctx.victim, ctx.killer }
		else
			return "%s died!", { ctx.victim }
		end
	end,

	[EventType.CALLOUT] = function(ctx)
		return "%s spotted %s!", { ctx.spotter, ctx.target }
	end,

	[EventType.TAUNT] = function(ctx)
		return "%s taunted %s!", { ctx.taunter, ctx.target }
	end,

	[EventType.ARTIFACT] = function(ctx)
		local verbs = {
			pickup = "picked up",
			equip = "equipped",
			use = "used",
			unequip = "unequipped",
		}
		local verb = verbs[ctx.action] or ctx.action
		return "%s " .. verb .. " %s", { ctx.actor, ctx.item_name }
	end,

	[EventType.EMISSION] = function(ctx)
		local type_name = ctx.emission_type == "psi_storm" and "Psi-Storm" or "Emission"
		if ctx.status == "starting" then
			return "A %s is starting!", { type_name }
		else
			return "The %s has ended.", { type_name }
		end
	end,

	[EventType.MAP_TRANSITION] = function(ctx)
		if ctx.source then
			return "%s traveled from %s to %s", { ctx.actor, ctx.source, ctx.destination }
		else
			return "%s arrived at %s", { ctx.actor, ctx.destination }
		end
	end,

	[EventType.ANOMALY] = function(ctx)
		return "%s encountered a %s anomaly!", { ctx.actor, ctx.anomaly_type }
	end,

	[EventType.INJURY] = function(ctx)
		return "%s was critically injured!", { ctx.actor }
	end,

	[EventType.SLEEP] = function(ctx)
		if ctx.companions and #ctx.companions > 0 then
			return "%s and companions rested", { ctx.actor }
		else
			return "%s rested", { ctx.actor }
		end
	end,

	[EventType.TASK] = function(ctx)
		local verb = ctx.action == "completed" and "completed" or "failed"
		if ctx.task_giver then
			return "%s " .. verb .. " task '%s' for %s", { ctx.actor, ctx.task_name, ctx.task_giver }
		else
			return "%s " .. verb .. " task '%s'", { ctx.actor, ctx.task_name }
		end
	end,

	[EventType.WEAPON_JAM] = function(ctx)
		return "%s's weapon jammed!", { ctx.actor }
	end,

	[EventType.RELOAD] = function(ctx)
		return "%s reloaded their weapon", { ctx.actor }
	end,

	[EventType.DIALOGUE] = function(ctx)
		if ctx.is_whisper then
			return "%s whispered to companions: '%s'", { ctx.speaker, ctx.text }
		else
			return "%s said: '%s'", { ctx.speaker, ctx.text }
		end
	end,

	[EventType.IDLE] = function(ctx)
		if ctx.instruction then
			return ctx.instruction, {} -- raw instruction, no formatting needed
		else
			return "%s wants to chat", { ctx.speaker }
		end
	end,
}

-- Helper to describe a character or object for text output
local function describe_object(obj)
	if type(obj) == "string" then
		return obj
	elseif type(obj) == "table" then
		if obj.name and obj.experience and obj.faction then
			-- It's a Character - use full description
			local Character = require("domain.model.character")
			return Character.describe(obj)
		elseif obj.name then
			return obj.name
		end
	end
	return tostring(obj)
end

-- NEW: Describe a typed event as human-readable text
function Event.describe(event)
	-- Handle synthetic/compressed events with raw content field
	if event.content then
		return event.content
	end

	-- Handle legacy events with description field (no type)
	if event.description and not event.type then
		return Event.describe_event(event)
	end

	-- Handle typed events
	local template_fn = TEMPLATES[event.type]
	if not template_fn then
		return "[Unknown event: " .. tostring(event.type) .. "]"
	end

	local template, objects = template_fn(event.context)

	-- No objects to format
	if not objects or #objects == 0 then
		return template
	end

	-- Format each object
	local descriptions = {}
	for _, obj in ipairs(objects) do
		table.insert(descriptions, describe_object(obj))
	end

	return string.format(template, unpack(descriptions))
end

function Event.describe_short(event)
	return Event.describe_event(event) -- temporary
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

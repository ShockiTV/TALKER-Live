-- memory_store_v2.lua — Four-tier per-NPC memory storage
-- Tiers: events, summaries, digests, cores, background
-- Each list item gets a globally unique timestamp from unique_ts().
-- Replaces the flat narrative blob memory_store.
package.path = package.path .. ";./bin/lua/?.lua;"
local logger = require("framework.logger")
local engine = require("interface.engine")
local unique_ts = require("domain.service.unique_ts")
local checksum = require("framework.checksum")

local MEMORIES_VERSION = "4"

-- Tier capacity constants
local CAPS = {
	events = 100,
	summaries = 10,
	digests = 5,
	cores = 5,
	global_events = 30,
}

local memory_store = {}

-- Map<character_id, {events, summaries, digests, cores, background, next_seq}>
local characters = {}

-- Global event buffer for emissions/psy-storms (backfilled on first contact)
local global_event_buffer = {}

-- Resource name → tier field mapping
local RESOURCE_MAP = {
	["memory.events"] = "events",
	["memory.summaries"] = "summaries",
	["memory.digests"] = "digests",
	["memory.cores"] = "cores",
	["memory.background"] = "background",
}

-- List-type resources (support append/delete)
local LIST_RESOURCES = {
	["memory.events"] = true,
	["memory.summaries"] = true,
	["memory.digests"] = true,
	["memory.cores"] = true,
}

------------------------------------------------------------
-- Internal helpers
------------------------------------------------------------

-- Create a new empty memory entry for a character
local function create_entry()
	return {
		events = {},
		summaries = {},
		digests = {},
		cores = {},
		background = nil,
	}
end

-- Assign a globally unique timestamp to an item via unique_ts
local function assign_ts(item)
	item.ts = unique_ts.unique_ts()
	return item
end

local function ensure_event_checksum(item)
	if not item.cs then
		item.cs = checksum.event_checksum({
			type = item.type,
			context = item.context or {},
			game_time_ms = item.timestamp or item.game_time_ms or 0,
		})
	end
	return item
end

local function ensure_tier_checksum(item)
	if not item.cs then
		item.cs = checksum.text_range_checksum(
			item.tier,
			item.text,
			item.start_ts,
			item.end_ts
		)
	end
	return item
end

local function ensure_background_checksum(bg)
	if type(bg) == "table" then
		bg.cs = checksum.background_checksum(bg)
	end
	return bg
end

-- Enforce tier cap by evicting oldest items (lowest seq = front of array)
local function enforce_cap(list, cap)
	while #list > cap do
		table.remove(list, 1)
	end
end

-- Backfill global events into a freshly created entry
local function backfill_globals(entry)
	for _, global_ev in ipairs(global_event_buffer) do
		local stored = {
			timestamp = global_ev.timestamp,
			type = global_ev.type,
			context = global_ev.context,
			ts = global_ev.ts or unique_ts.unique_ts(),
			cs = global_ev.cs,
		}
		ensure_event_checksum(stored)
		table.insert(entry.events, stored)
	end
	enforce_cap(entry.events, CAPS.events)
end

-- Get or create a character's memory entry. New entries get global backfill.
local function get_or_create(character_id)
	if not characters[character_id] then
		local entry = create_entry()
		characters[character_id] = entry
		backfill_globals(entry)
	end
	return characters[character_id]
end

------------------------------------------------------------
-- Core Operations
------------------------------------------------------------

--- Store a single event in a character's events tier.
-- @param character_id  string
-- @param event         table from Event.create() — has type, context, game_time_ms, ts
-- @return stored event (with ts assigned)
function memory_store:store_event(character_id, event)
	local entry = get_or_create(tostring(character_id))
	local stored = {
		timestamp = event.game_time_ms,
		type = event.type,
		context = event.context or {},
		ts = event.ts or unique_ts.unique_ts(),
		cs = checksum.event_checksum(event),
	}
	table.insert(entry.events, stored)
	enforce_cap(entry.events, CAPS.events)
	return stored
end

--- Fan out an event to all witnesses.
-- Stores a copy in each witness NPC's events tier.
-- @param event      table from Event.create()
-- @param witnesses  array of Character-like objects with game_id field
function memory_store:fan_out(event, witnesses)
	if not witnesses then return end
	for _, witness in ipairs(witnesses) do
		local char_id = tostring(witness.game_id or witness)
		self:store_event(char_id, event)
	end
end

------------------------------------------------------------
-- Global Event Buffer
------------------------------------------------------------

--- Store a global event: append to all existing characters AND the backfill buffer.
-- @param event  table from Event.create()
function memory_store:store_global_event(event)
	local canonical_event = {
		type = event.type,
		context = event.context or {},
		game_time_ms = event.game_time_ms,
		ts = event.ts or unique_ts.unique_ts(),
	}
	local event_cs = checksum.event_checksum(canonical_event)

	-- Write to all existing characters
	for char_id, _ in pairs(characters) do
		self:store_event(char_id, canonical_event)
	end

	-- Append to backfill buffer
	table.insert(global_event_buffer, {
		timestamp = canonical_event.game_time_ms,
		type = canonical_event.type,
		context = canonical_event.context,
		ts = canonical_event.ts,
		cs = event_cs,
	})
	enforce_cap(global_event_buffer, CAPS.global_events)
end

--- Ensure a character has a memory entry (backfilling globals if new).
-- Public convenience for squad discovery path.
function memory_store:ensure_entry(character_id)
	return get_or_create(tostring(character_id))
end

------------------------------------------------------------
-- Query DSL
------------------------------------------------------------

--- Query a memory resource for a character.
-- @param character_id  string
-- @param resource      string (e.g. "memory.events", "memory.background")
-- @param params        table (optional: from_timestamp, sort, limit)
-- @return data, error_string
function memory_store:query(character_id, resource, params)
	params = params or {}

	local field = RESOURCE_MAP[resource]
	if not field then
		return nil, "unknown resource: " .. tostring(resource)
	end

	local entry = characters[tostring(character_id)]
	if not entry then
		if resource == "memory.background" then
			return nil, nil -- null background is valid
		end
		return {}, nil -- empty list for list resources
	end

	local data = entry[field]

	-- Background: return directly (may be nil)
	if resource == "memory.background" then
		return data, nil
	end

	-- List resources: apply timestamp filter if provided
	if params.from_timestamp then
		local filtered = {}
		local ts = params.from_timestamp
		if resource == "memory.events" then
			for _, item in ipairs(data) do
				if item.timestamp >= ts then
					table.insert(filtered, item)
				end
			end
		else
			-- Compressed tiers: include if end_ts >= from_timestamp (overlap)
			for _, item in ipairs(data) do
				if item.end_ts and item.end_ts >= ts then
					table.insert(filtered, item)
				end
			end
		end
		return filtered, nil
	end

	return data, nil
end

------------------------------------------------------------
-- Mutate DSL
------------------------------------------------------------

--- Apply a mutation operation to a character's memory.
-- @param mutation  table with {op, resource, params={character_id}, data?, ids?, ops?}
-- @return {ok: boolean, error: string?}
function memory_store:mutate(mutation)
	local op = mutation.op
	local resource = mutation.resource
	local character_id = mutation.params and mutation.params.character_id

	if not character_id then
		return { ok = false, error = "missing character_id in params" }
	end

	local field = RESOURCE_MAP[resource]
	if not field then
		return { ok = false, error = "unknown resource: " .. tostring(resource) }
	end

	if op == "append" then
		return self:_mutate_append(character_id, field, resource, mutation.data)
	elseif op == "delete" then
		return self:_mutate_delete(character_id, field, resource, mutation.ids)
	elseif op == "set" then
		return self:_mutate_set(character_id, field, resource, mutation.data)
	elseif op == "update" then
		return self:_mutate_update(character_id, field, resource, mutation.ops)
	else
		return { ok = false, error = "unknown op: " .. tostring(op) }
	end
end

--- Append items to a list-type resource.
function memory_store:_mutate_append(character_id, field, resource, data)
	if not LIST_RESOURCES[resource] then
		return { ok = false, error = "append not supported for " .. resource }
	end
	if not data or type(data) ~= "table" then
		return { ok = false, error = "data must be an array" }
	end

	local entry = get_or_create(tostring(character_id))
	local list = entry[field]
	local cap = CAPS[field]

	for _, item in ipairs(data) do
		if not item.ts then
			assign_ts(item)
		end
		if resource == "memory.events" then
			ensure_event_checksum(item)
		elseif resource == "memory.summaries" or resource == "memory.digests" or resource == "memory.cores" then
			ensure_tier_checksum(item)
		end
		table.insert(list, item)
	end
	enforce_cap(list, cap)

	return { ok = true }
end

--- Delete items from a list-type resource by explicit ts IDs.
function memory_store:_mutate_delete(character_id, field, resource, ids)
	if not LIST_RESOURCES[resource] then
		return { ok = false, error = "delete not supported for " .. resource }
	end
	if not ids or type(ids) ~= "table" then
		return { ok = false, error = "ids must be an array" }
	end

	local entry = characters[tostring(character_id)]
	if not entry then
		return { ok = true } -- nothing to delete, idempotent
	end

	-- Build set of IDs to delete for O(n) scan
	local id_set = {}
	for _, id in ipairs(ids) do
		id_set[id] = true
	end

	-- Filter out matching items (use ts as identity key)
	local list = entry[field]
	local new_list = {}
	for _, item in ipairs(list) do
		if not id_set[item.ts] then
			table.insert(new_list, item)
		end
	end
	entry[field] = new_list

	return { ok = true }
end

--- Replace an entire resource (background only).
function memory_store:_mutate_set(character_id, field, resource, data)
	if resource ~= "memory.background" then
		return { ok = false, error = "set only supported for memory.background" }
	end

	local entry = get_or_create(tostring(character_id))
	entry[field] = ensure_background_checksum(data)

	return { ok = true }
end

--- Partial update with $push/$pull/$set operators (background only).
function memory_store:_mutate_update(character_id, field, resource, ops)
	if resource ~= "memory.background" then
		return { ok = false, error = "update only supported for memory.background" }
	end
	if not ops or type(ops) ~= "table" then
		return { ok = false, error = "ops must be a table" }
	end

	local entry = characters[tostring(character_id)]
	if not entry or not entry.background then
		return { ok = false, error = "no background to update for character " .. tostring(character_id) }
	end

	local bg = entry.background

	-- $push: add value to a list field
	if ops["$push"] then
		for field_name, value in pairs(ops["$push"]) do
			if bg[field_name] and type(bg[field_name]) == "table" then
				table.insert(bg[field_name], value)
			end
		end
	end

	-- $pull: remove first matching value from a list field
	if ops["$pull"] then
		for field_name, value in pairs(ops["$pull"]) do
			if bg[field_name] and type(bg[field_name]) == "table" then
				for i = #bg[field_name], 1, -1 do
					local item = bg[field_name][i]
					-- String comparison for traits; character_id match for connections
					if item == value then
						table.remove(bg[field_name], i)
						break
					elseif type(item) == "table" and type(value) == "string" and item.character_id == value then
						table.remove(bg[field_name], i)
						break
					end
				end
			end
		end
	end

	-- $set: set a field value directly
	if ops["$set"] then
		for field_name, value in pairs(ops["$set"]) do
			bg[field_name] = value
		end
	end

	ensure_background_checksum(bg)

	return { ok = true }
end

------------------------------------------------------------
-- Save / Load with v2→v3 migration
------------------------------------------------------------

function memory_store:get_save_data()
	local save_chars = {}
	for char_id, entry in pairs(characters) do
		save_chars[char_id] = {
			events = entry.events,
			summaries = entry.summaries,
			digests = entry.digests,
			cores = entry.cores,
			background = entry.background,
		}
	end
	return {
		memories_version = MEMORIES_VERSION,
		memories = save_chars,
		global_events = global_event_buffer,
	}
end

function memory_store:clear()
	characters = {}
	global_event_buffer = {}
	unique_ts.reset()
end

--- Migrate v3 save data (per-character seq) to v4 (global unique_ts).
-- Replaces seq fields with ts values, handling collisions.
local function migrate_v3(saved_data)
	local result = {}
	local memories = saved_data.memories or {}
	-- Track all assigned timestamps globally to resolve collisions
	local assigned = {}
	for char_id, data in pairs(memories) do
		local entry = create_entry()
		-- Migrate events: use timestamp as ts base, bump collisions
		for _, ev in ipairs(data.events or {}) do
			local candidate = ev.timestamp or 0
			while assigned[candidate] do
				candidate = candidate + 1
			end
			assigned[candidate] = true
			local migrated_event = {
				ts = candidate,
				timestamp = ev.timestamp,
				type = ev.type,
				context = ev.context,
				cs = ev.cs,
			}
			ensure_event_checksum(migrated_event)
			table.insert(entry.events, migrated_event)
		end
		-- Migrate compressed tiers: use existing ts or start_ts or generate
		for _, tier_name in ipairs({"summaries", "digests", "cores"}) do
			for _, item in ipairs(data[tier_name] or {}) do
				local candidate = item.ts or item.start_ts or item.end_ts or 0
				while assigned[candidate] do
					candidate = candidate + 1
				end
				assigned[candidate] = true
				item.ts = candidate
				item.seq = nil -- remove legacy field
				ensure_tier_checksum(item)
				table.insert(entry[tier_name], item)
			end
		end
		entry.background = ensure_background_checksum(data.background)
		result[char_id] = entry
	end
	return result
end

--- Migrate v2 save data (flat narrative blob) to v3 in-memory format.
local function migrate_v2(saved_data)
	local result = {}
	local memories = saved_data.memories or {}
	for char_id, data in pairs(memories) do
		local entry = create_entry()
		if data.narrative and data.narrative ~= "" then
			entry.cores[1] = {
				seq = 0,
				tier = "core",
				start_ts = 0,
				end_ts = data.last_update_time_ms or 0,
				text = data.narrative,
				source_count = 0,
			}
			ensure_tier_checksum(entry.cores[1])
			entry.next_seq = 1
		end
		result[char_id] = entry
	end
	return result
end

local function ensure_entry_checksums(entry)
	for _, ev in ipairs(entry.events or {}) do
		ensure_event_checksum(ev)
	end
	for _, item in ipairs(entry.summaries or {}) do
		ensure_tier_checksum(item)
	end
	for _, item in ipairs(entry.digests or {}) do
		ensure_tier_checksum(item)
	end
	for _, item in ipairs(entry.cores or {}) do
		ensure_tier_checksum(item)
	end
	if entry.background then
		ensure_background_checksum(entry.background)
	end
end

local function ensure_global_event_checksums()
	for _, item in ipairs(global_event_buffer) do
		if not item.ts then
			item.ts = unique_ts.unique_ts()
		end
		if not item.cs then
			item.cs = checksum.event_checksum({
				type = item.type,
				context = item.context or {},
				game_time_ms = item.timestamp,
			})
		end
	end
end

--- Migrate v1 save data (legacy unversioned) → v2 → v3.
local function migrate_v1(saved_data)
	local v2_data = { memories_version = "2", memories = {} }
	for char_id, data in pairs(saved_data) do
		if type(data) == "table" then
			if #data > 0 then
				-- Old list format: concatenate into narrative
				local combined = ""
				local last_time = 0
				table.sort(data, function(a, b)
					return (a.game_time_ms or 0) < (b.game_time_ms or 0)
				end)
				for _, mem in ipairs(data) do
					combined = combined .. (mem.content or "") .. "\n\n"
					if (mem.game_time_ms or 0) > last_time then
						last_time = mem.game_time_ms or 0
					end
				end
				v2_data.memories[char_id] = {
					narrative = combined,
					last_update_time_ms = last_time,
				}
			else
				-- Object format (pre-versioning but correct structure)
				v2_data.memories[char_id] = data
			end
		end
	end
	return migrate_v2(v2_data)
end

function memory_store:load_save_data(saved_data)
	logger.info("Loading memory store v2...")

	-- Reset unique_ts state on any load
	unique_ts.reset()

	if not saved_data then
		logger.info("No saved memory data, starting fresh")
		characters = {}
		global_event_buffer = {}
		return
	end

	local version = saved_data.memories_version

	if version == MEMORIES_VERSION then
		logger.info("Loading v4 memory store")
		characters = {}
		local memories = saved_data.memories or {}
		for char_id, data in pairs(memories) do
			characters[char_id] = {
				events = data.events or {},
				summaries = data.summaries or {},
				digests = data.digests or {},
				cores = data.cores or {},
				background = data.background,
			}
			ensure_entry_checksums(characters[char_id])
		end
		global_event_buffer = saved_data.global_events or {}
		ensure_global_event_checksums()
		return
	end

	if version == "3" then
		logger.warn("Migrating v3 memory store to v4...")
		characters = migrate_v3(saved_data)
		global_event_buffer = saved_data.global_events or {}
		ensure_global_event_checksums()
		return
	end

	if version == "2" then
		logger.warn("Migrating v2 memory store to v4...")
		characters = migrate_v2(saved_data)
		global_event_buffer = {}
		return
	end

	if not version then
		logger.warn("Migrating v1 memory store to v4...")
		characters = migrate_v1(saved_data)
		global_event_buffer = {}
		return
	end

	-- Unknown version
	logger.warn("Unknown memory store version: " .. tostring(version) .. ", starting fresh")
	characters = {}
	global_event_buffer = {}
end

------------------------------------------------------------
-- Accessors (inspection / compaction threshold checks)
------------------------------------------------------------

--- Get a character's full memory entry (or nil).
function memory_store:get_entry(character_id)
	return characters[tostring(character_id)]
end

--- Get all character IDs that have memory entries.
function memory_store:get_all_character_ids()
	local ids = {}
	for id, _ in pairs(characters) do
		ids[#ids + 1] = id
	end
	return ids
end

--- Get the global event buffer.
function memory_store:get_global_event_buffer()
	return global_event_buffer
end

--- Get tier counts for a character (for compaction threshold checks).
function memory_store:get_tier_counts(character_id)
	local entry = characters[tostring(character_id)]
	if not entry then return nil end
	return {
		events = #entry.events,
		summaries = #entry.summaries,
		digests = #entry.digests,
		cores = #entry.cores,
	}
end

--- Get tier capacity constants.
function memory_store:get_caps()
	return CAPS
end

return memory_store

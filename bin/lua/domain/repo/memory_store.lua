local Event = require("domain.model.event")
-- memory_store:lua
package.path = package.path .. ";./bin/lua/?.lua;"
local event_store = require("domain.repo.event_store")
local transformations = require("infra.AI.transformations")
local logger = require("framework.logger")

local memory_store = {}
-- Map<character_id, {narrative: string, last_update_time_ms: number}>
local narrative_memories = {}

-- for saving and loading
function memory_store:get_save_data()
	return narrative_memories
end

function memory_store:clear()
	narrative_memories = {}
end

function memory_store:load_save_data(saved_data)
	if not saved_data then
		return
	end

	-- MIGRATION: Check if this is the old format (list of memories)
	-- If the first value is an array (has integer keys), it's the old format.

	narrative_memories = {}

	for id, data in pairs(saved_data) do
		-- Check if 'data' is a list (old format) or object (new format)
		if #data > 0 or (next(data) == nil and type(data) == "table") then
			-- It's a list (or empty list), so it's the OLD format.
			-- Migrate: Transform  all events into a new 'LONG-TERM MEMORY'.
			-- Check if we have too many events for a single context
			if #data >= transformations.COMPRESSION_THRESHOLD then
				logger.info("Migrating memory: Count " .. #data .. " exceeds threshold. Triggering immediate update.")
				-- We leave narrative empty and last_update_time at 0 (or undefined).
				-- This will cause get_new_events to return ALL existing events, and update_narrative to trigger compression.
				narrative_memories[id] = {
					narrative = nil,
					last_update_time_ms = 0,
				}
			else
				-- Standard migration
				logger.info("Migrating memory: Count " .. #data .. " is within limits. Concatenating.")
				local combined_text = ""
				local last_time = 0

				-- Sort by time just in case
				table.sort(data, function(a, b)
					return a.game_time_ms < b.game_time_ms
				end)

				for _, mem in ipairs(data) do
					combined_text = combined_text .. (mem.content or "") .. "\n\n"
					if mem.game_time_ms > last_time then
						last_time = mem.game_time_ms
					end
				end

				narrative_memories[id] = {
					narrative = combined_text,
					last_update_time_ms = last_time,
				}
			end
		else
			-- It's the NEW format (or empty/nil, handling normally)
			narrative_memories[id] = data
		end
	end
end

-- local functions
local function create_memory(content, game_time_ms)
	return {
		content = content,
		game_time_ms = game_time_ms,
	}
end

-- main module
function memory_store:get_memories(character_id)
	local memories = {}
	local events = event_store:get_all_events()
	for i, event in ipairs(events) do
		if Event.was_witnessed_by(event, character_id) then
			table.insert(memories, event)
		end
	end
	table.sort(memories, function(a, b)
		return a.game_time_ms < b.game_time_ms
	end)
	return memories
end

function memory_store:update_narrative(character_id, new_narrative, last_event_time_ms)
	narrative_memories[character_id] = {
		narrative = new_narrative,
		last_update_time_ms = last_event_time_ms,
	}
end

function memory_store:update_last_update_time(character_id, last_event_time_ms)
	local mem = narrative_memories[character_id]
	if mem then
		mem.last_update_time_ms = last_event_time_ms
	else
		narrative_memories[character_id] = {
			narrative = "",
			last_update_time_ms = last_event_time_ms,
		}
	end
end

function memory_store:get_narrative(character_id)
	return narrative_memories[character_id]
end

function memory_store:get_new_events(character_id)
	if not character_id then
		error("memory_store:get_new_events: No character id provided")
	end

	local last_update_time = 0
	local mem_struct = narrative_memories[character_id]
	if mem_struct then
		last_update_time = mem_struct.last_update_time_ms or 0
	end

	-- Use event_store:get_events_since for efficient retrieval
	local events = event_store:get_events_since(last_update_time)
	local uncompressed_memories = {}

	for i = 1, #events do
		local event = events[i]
		-- nil check
		if event and Event.was_witnessed_by(event, character_id) then
			table.insert(uncompressed_memories, event)
		end
	end

	table.sort(uncompressed_memories, function(a, b)
		return a.game_time_ms < b.game_time_ms
	end)
	return uncompressed_memories
end

-- gets new and compressed memories ready for dialogue generation
-- Returns the full context for prompts: { narrative = ..., new_events = ... }
function memory_store:get_memory_context(character_id)
	local mem_struct = narrative_memories[character_id]
	local new_events = memory_store:get_new_events(character_id)

	return {
		narrative = mem_struct and mem_struct.narrative or nil,
		last_update_time_ms = mem_struct and mem_struct.last_update_time_ms or 0,
		new_events = new_events,
	}
end

-- for mocks

function memory_store:insert_mocks(mock_event_store)
	event_store = mock_event_store
end
return memory_store

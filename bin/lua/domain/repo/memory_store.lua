-- memory_store:lua
package.path = package.path .. ";./bin/lua/?.lua;"
local logger = require("framework.logger")

-- Version for memory store save data format
-- "2" is first versioned format (legacy unversioned saves are treated as version 1)
local MEMORIES_VERSION = "2"

-- Memory compression threshold (events before narrative update is triggered)
local COMPRESSION_THRESHOLD = 12

local memory_store = {}
-- Map<character_id, {narrative: string, last_update_time_ms: number}>
local narrative_memories = {}

-- for saving and loading
function memory_store:get_save_data()
	-- Return versioned structure for forward compatibility
	return {
		memories_version = MEMORIES_VERSION,
		memories = narrative_memories,
	}
end

function memory_store:clear()
	narrative_memories = {}
end

-- Helper to migrate legacy memory data (pre-versioning)
local function migrate_legacy_data(saved_data)
	local migrated = {}
	
	for id, data in pairs(saved_data) do
		-- Check if 'data' is a list (old format) or object (new format)
		if #data > 0 or (next(data) == nil and type(data) == "table") then
			-- It's a list (or empty list), so it's the OLD format.
			-- Migrate: Transform all events into a new 'LONG-TERM MEMORY'.
			if #data >= COMPRESSION_THRESHOLD then
				logger.info("Migrating memory: Count " .. #data .. " exceeds threshold. Triggering immediate update.")
				migrated[id] = {
					narrative = nil,
					last_update_time_ms = 0,
				}
			else
				-- Standard migration
				logger.info("Migrating memory: Count " .. #data .. " is within limits. Concatenating.")
				local combined_text = ""
				local last_time = 0

				table.sort(data, function(a, b)
					return a.game_time_ms < b.game_time_ms
				end)

				for _, mem in ipairs(data) do
					combined_text = combined_text .. (mem.content or "") .. "\n\n"
					if mem.game_time_ms > last_time then
						last_time = mem.game_time_ms
					end
				end

				migrated[id] = {
					narrative = combined_text,
					last_update_time_ms = last_time,
				}
			end
		else
			-- It's the object format (pre-versioning but correct structure)
			migrated[id] = data
		end
	end
	
	return migrated
end

function memory_store:load_save_data(saved_data)
	logger.info("Loading memory store...")
	
	-- Handle nil data → start fresh
	if not saved_data then
		logger.info("No saved memory data, starting fresh")
		narrative_memories = {}
		return
	end
	
	-- Check for versioned format
	if saved_data.memories_version then
		if saved_data.memories_version == MEMORIES_VERSION then
			-- Current version: load normally
			logger.info("Loading versioned memory store (v" .. saved_data.memories_version .. ")")
			narrative_memories = saved_data.memories or {}
		else
			-- Unknown version: start fresh with warning
			logger.warn("Unknown memory store version: " .. tostring(saved_data.memories_version) .. ", starting fresh")
			narrative_memories = {}
		end
		return
	end
	
	-- Legacy format (no version): migrate
	logger.warn("Loading legacy memory store format (no version), migrating...")
	narrative_memories = migrate_legacy_data(saved_data)
end

-- main module
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

-- for mocks

return memory_store

package.path = package.path .. ";./bin/lua/?.lua;"
local log = require("framework.logger")
local engine = require("interface.engine")
local backstory_data = require("domain.repo.backstory_data")

-- Version for backstories store save data format
-- "2" is first versioned format (legacy unversioned saves are treated as version 1)
local BACKSTORIES_VERSION = "2"

local M = {}

-- Cache of character_id -> backstory_id
local character_backstories = {}

-- Map faction names to backstory_data table keys
local faction_to_section = {
	["bandit"] = "bandit",
	["renegade"] = "renegade",
	["monolith"] = "monolith",
	["ecolog"] = "ecolog",
	["ecologist"] = "ecolog",
	["sin"] = "sin",
	["duty"] = "duty",
	["freedom"] = "freedom",
	["army"] = "army",
	["mercenary"] = "mercenary",
	["killer"] = "mercenary",
	["isg"] = "isg",
	["clear sky"] = "clearsky",
	["csky"] = "clearsky",
	-- All others fall back to generic
}

-- Check if a unique character has a defined backstory in the data table
local function has_unique_backstory(tech_name)
	local lower = string.lower(tech_name)
	for _, id in ipairs(backstory_data.unique) do
		if string.lower(id) == lower then
			return true
		end
	end
	return false
end

-- Get a random backstory ID for a faction
local function get_random_backstory_id(faction)
	local section = faction_to_section[string.lower(faction or "")] or "generic"
	local ids = backstory_data[section]

	if not ids or #ids == 0 then
		log.spam("Section '" .. section .. "' not found in backstory_data, falling back to generic")
		ids = backstory_data.generic
	end

	if not ids or #ids == 0 then
		log.warn("No backstory IDs found at all, using fallback")
		return "generic.1"
	end

	local idx = math.random(1, #ids)
	local backstory_id = section .. "." .. tostring(ids[idx])
	log.spam("Selected backstory ID: " .. backstory_id .. " for faction: " .. (faction or "unknown"))
	return backstory_id
end

-- Set a random backstory ID for a character
local function set_random_backstory(character)
	-- Player gets no backstory
	if tostring(character.game_id) == "0" then
		character_backstories[character.game_id] = ""
		return
	end

	-- Check for unique character
	if engine.is_unique_character_by_id(character.game_id) then
		local tech_name = engine.get_technical_name_by_id(character.game_id)
		log.debug("Handling unique character: " .. character.game_id .. " (" .. tech_name .. ")")

		-- Check if this unique character has a defined backstory in the data table
		if has_unique_backstory(tech_name) then
			local backstory_id = "unique." .. string.lower(tech_name)
			character_backstories[character.game_id] = backstory_id
			log.spam("Assigned unique backstory ID: " .. backstory_id)
			return
		else
			log.info("No backstory found for unique character: " .. tech_name .. ", using faction-based")
			-- Fall through to random assignment
		end
	end

	-- Get random backstory ID based on faction
	local backstory_id = get_random_backstory_id(character.faction)
	character_backstories[character.game_id] = backstory_id
	log.spam("Assigned backstory ID: " .. backstory_id .. " to character: " .. character.game_id)
end

-- Get backstory ID for a character
function M.get_backstory(character)
	log.spam("Retrieving backstory for character: " .. tostring(character.game_id))
	local backstory = character_backstories[character.game_id]
	if not backstory then
		log.spam("No backstory cached, setting a random one.")
		set_random_backstory(character)
		backstory = character_backstories[character.game_id]
		if not backstory then
			log.info("No backstory found after assignment: " .. tostring(character.game_id))
		end
	end
	return backstory or ""
end

-- Alias for consistency with personalities module
M.get_backstory_id = M.get_backstory

function M.get_save_data()
	log.debug("Returning character backstories for save.")
	return {
		backstories_version = BACKSTORIES_VERSION,
		backstories = character_backstories,
	}
end

function M.clear()
	log.debug("Clearing character backstories cache.")
	character_backstories = {}
end

function M.load_save_data(saved_data)
	log.info("Loading backstories store...")

	-- MCM reset option takes priority
	local reset = engine.get_mcm_value("reset_backstory")
	if reset then
		log.debug("TALKER backstory reset is enabled. Clearing all saved backstories.")
		character_backstories = {}
		return
	end

	-- Handle nil data → start fresh
	if not saved_data then
		log.info("No saved backstories data, starting fresh")
		character_backstories = {}
		return
	end

	-- Check for versioned format
	if saved_data.backstories_version then
		if saved_data.backstories_version == BACKSTORIES_VERSION then
			log.info("Loading versioned backstories store (v" .. saved_data.backstories_version .. ")")
			character_backstories = saved_data.backstories or {}
		else
			log.warn("Unknown backstories store version: " .. tostring(saved_data.backstories_version) .. ", starting fresh")
			character_backstories = {}
		end
		return
	end

	-- Legacy format (no version): clear and re-assign on demand
	log.warn("Loading legacy backstories store format (no version), starting fresh")
	character_backstories = {}
end

--- Get the raw character_id → backstory_id map (read-only reference).
-- Used by batch query handler for collection iteration.
-- @return table  Map of character_id to backstory_id
function M.get_all_mappings()
	return character_backstories
end

return M

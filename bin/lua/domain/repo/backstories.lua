package.path = package.path .. ";./bin/lua/?.lua;"
local log = require("framework.logger")
local queries = talker_game_queries or require("tests.mocks.mock_game_queries")
local mcm = talker_mcm

-- Version for backstories store save data format
-- "2" is first versioned format (legacy unversioned saves are treated as version 1)
local BACKSTORIES_VERSION = "2"

local M = {}

-- Cache of valid unique IDs from .ltx file (loaded once)
local unique_ids_cache = nil

-- Cache of character_id -> backstory_id
local character_backstories = {}

-- INI file handle (lazy loaded)
local ini = nil

function M.set_queries(q)
	log.spam("Setting queries...")
	queries = q
end

-- Helper to parse comma-separated IDs from .ltx
local function parse_ids(ids_str)
	if not ids_str then return {} end
	local ids = {}
	for id in string.gmatch(ids_str, "([^,]+)") do
		local trimmed = id:match("^%s*(.-)%s*$")
		if trimmed and #trimmed > 0 then
			table.insert(ids, trimmed)
		end
	end
	return ids
end

-- Get INI file handle (lazy load)
local function get_ini()
	if not ini then
		ini = ini_file("talker\\backstories.ltx")
	end
	return ini
end

-- Get set of valid unique IDs (lazy load)
local function get_unique_ids()
	if unique_ids_cache then
		return unique_ids_cache
	end
	
	unique_ids_cache = {}
	local cfg = get_ini()
	if cfg and cfg:section_exist("unique") then
		local ids_str = cfg:r_string_ex("unique", "ids")
		local ids = parse_ids(ids_str)
		for _, id in ipairs(ids) do
			unique_ids_cache[string.lower(id)] = true
		end
	end
	return unique_ids_cache
end

-- Check if a unique character has a defined backstory in .ltx
local function has_unique_backstory(tech_name)
	local unique_ids = get_unique_ids()
	return unique_ids[string.lower(tech_name)] == true
end

-- Map faction names to .ltx section names
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

-- Get a random backstory ID for a faction
local function get_random_backstory_id(faction)
	local cfg = get_ini()
	if not cfg then
		log.warn("Could not load backstories.ltx, using generic fallback")
		return "generic.1"
	end
	
	-- Normalize faction name
	local section = faction_to_section[string.lower(faction or "")] or "generic"
	
	-- Check if section exists
	if not cfg:section_exist(section) then
		log.spam("Section '" .. section .. "' not found, falling back to generic")
		section = "generic"
	end
	
	-- Read IDs
	local ids_str = cfg:r_string_ex(section, "ids")
	local ids = parse_ids(ids_str)
	
	if #ids == 0 then
		log.warn("No IDs found in section '" .. section .. "', using fallback")
		return "generic.1"
	end
	
	-- Pick random ID
	local idx = math.random(1, #ids)
	local backstory_id = section .. "." .. ids[idx]
	
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
	if queries.is_unique_character_by_id(character.game_id) then
		local tech_name = queries.get_technical_name_by_id(character.game_id)
		log.debug("Handling unique character: " .. character.game_id .. " (" .. tech_name .. ")")
		
		-- Check if this unique character has a defined backstory in .ltx
		if has_unique_backstory(tech_name) then
			-- Use "unique.{tech_name}" ID format for unique characters
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
	-- Return versioned structure for forward compatibility
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
	if mcm and mcm.get and mcm.get("reset_backstory") then
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
			-- Current version: load normally
			log.info("Loading versioned backstories store (v" .. saved_data.backstories_version .. ")")
			character_backstories = saved_data.backstories or {}
		else
			-- Unknown version: start fresh with warning
			log.warn("Unknown backstories store version: " .. tostring(saved_data.backstories_version) .. ", starting fresh")
			character_backstories = {}
		end
		return
	end
	
	-- Legacy format (no version): clear and re-assign on demand
	log.warn("Loading legacy backstories store format (no version), starting fresh")
	character_backstories = {}
end

return M

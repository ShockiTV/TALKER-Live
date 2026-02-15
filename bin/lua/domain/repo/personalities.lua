package.path = package.path .. ";./bin/lua/?.lua;"
local log = require("framework.logger")
local unique_characters = require("infra.STALKER.unique_characters")
local queries = talker_game_queries or require("tests.mocks.mock_game_queries")
local mcm = talker_mcm

-- Version for personalities store save data format
-- "2" is first versioned format (legacy unversioned saves are treated as version 1)
local PERSONALITIES_VERSION = "2"

local M = {}

-- Cache of character_id -> personality_id
local character_personalities = {}

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
		ini = ini_file("talker\\personalities.ltx")
	end
	return ini
end

-- Map faction names to .ltx section names
local faction_to_section = {
	["bandit"] = "bandit",
	["renegade"] = "renegade",
	["monolith"] = "monolith",
	["ecolog"] = "ecolog",
	["ecologist"] = "ecolog",
	["sin"] = "sin",
	["zombied"] = "zombied",
	-- All others fall back to generic
}

-- Get a random personality ID for a faction
local function get_random_personality_id(faction)
	local cfg = get_ini()
	if not cfg then
		log.warn("Could not load personalities.ltx, using generic fallback")
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
	local personality_id = section .. "." .. ids[idx]
	
	log.spam("Selected personality ID: " .. personality_id .. " for faction: " .. (faction or "unknown"))
	return personality_id
end

-- Set a random personality ID for a character
local function set_random_personality(character)
	-- Player gets no personality
	if tostring(character.game_id) == "0" then
		return ""
	end
	
	-- Check for unique character
	if queries.is_unique_character_by_id(character.game_id) then
		local tech_name = queries.get_technical_name_by_id(character.game_id)
		log.debug("Handling unique character: " .. character.game_id .. " (" .. tech_name .. ")")
		
		-- Check if this unique character has a defined personality
		local unique_personality = unique_characters[tech_name]
		if unique_personality and unique_personality ~= "" then
			-- Use "unique.{tech_name}" ID format for unique characters
			local personality_id = "unique." .. tech_name
			character_personalities[character.game_id] = personality_id
			log.spam("Assigned unique personality ID: " .. personality_id)
			return
		else
			log.info("No personality found for unique character: " .. tech_name .. ", using faction-based")
			-- Fall through to random assignment
		end
	end
	
	-- Get random personality ID based on faction
	local personality_id = get_random_personality_id(character.faction)
	character_personalities[character.game_id] = personality_id
	log.spam("Assigned personality ID: " .. personality_id .. " to character: " .. character.game_id)
end

-- Get personality ID for a character
function M.get_personality(character)
	log.spam("Retrieving personality for character: " .. character.game_id)
	local personality = character_personalities[character.game_id]
	if not personality then
		log.spam("No personality cached, setting a random one.")
		set_random_personality(character)
		personality = character_personalities[character.game_id]
		if not personality then
			log.info("No personality found after assignment: " .. character.game_id)
		end
	end
	return personality or ""
end

-- Alias for compatibility
M.get_personality_id = M.get_personality

function M.get_save_data()
	log.debug("Returning character personalities for save.")
	-- Return versioned structure for forward compatibility
	return {
		personalities_version = PERSONALITIES_VERSION,
		personalities = character_personalities,
	}
end

function M.clear()
	log.debug("Clearing character personalities cache.")
	character_personalities = {}
end

function M.load_save_data(saved_data)
	log.info("Loading personalities store...")
	
	-- MCM reset option takes priority
	if mcm and mcm.get and mcm.get("reset_personality") then
		log.debug("TALKER personality reset is enabled. Clearing all saved personalities.")
		character_personalities = {}
		return
	end
	
	-- Handle nil data → start fresh
	if not saved_data then
		log.info("No saved personalities data, starting fresh")
		character_personalities = {}
		return
	end
	
	-- Check for versioned format
	if saved_data.personalities_version then
		if saved_data.personalities_version == PERSONALITIES_VERSION then
			-- Current version: load normally
			log.info("Loading versioned personalities store (v" .. saved_data.personalities_version .. ")")
			character_personalities = saved_data.personalities or {}
		else
			-- Unknown version: start fresh with warning
			log.warn("Unknown personalities store version: " .. tostring(saved_data.personalities_version) .. ", starting fresh")
			character_personalities = {}
		end
		return
	end
	
	-- Legacy format (no version): clear and re-assign on demand
	log.warn("Loading legacy personalities store format (no version), starting fresh")
	character_personalities = {}
end

return M

package.path = package.path .. ";./bin/lua/?.lua;"
local log = require("framework.logger")
local unique_characters = require("infra.STALKER.unique_characters")
local engine = require("interface.engine")
local personality_data = require("domain.repo.personality_data")

-- Version for personalities store save data format
-- "2" is first versioned format (legacy unversioned saves are treated as version 1)
local PERSONALITIES_VERSION = "2"

local M = {}

-- Cache of character_id -> personality_id
local character_personalities = {}

-- Map faction names to personality_data table keys
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
	local section = faction_to_section[string.lower(faction or "")] or "generic"
	local ids = personality_data[section]

	if not ids or #ids == 0 then
		log.spam("Section '" .. section .. "' not found in personality_data, falling back to generic")
		ids = personality_data.generic
	end

	if not ids or #ids == 0 then
		log.warn("No personality IDs found at all, using fallback")
		return "generic.1"
	end

	local idx = math.random(1, #ids)
	local personality_id = section .. "." .. tostring(ids[idx])
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
	if engine.is_unique_character_by_id(character.game_id) then
		local tech_name = engine.get_technical_name_by_id(character.game_id)
		log.debug("Handling unique character: " .. character.game_id .. " (" .. tech_name .. ")")

		-- Check if this unique character has a defined personality
		local unique_personality = unique_characters[tech_name]
		if unique_personality and unique_personality ~= "" then
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
	local reset = engine.get_mcm_value("reset_personality")
	if reset then
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
			log.info("Loading versioned personalities store (v" .. saved_data.personalities_version .. ")")
			character_personalities = saved_data.personalities or {}
		else
			log.warn("Unknown personalities store version: " .. tostring(saved_data.personalities_version) .. ", starting fresh")
			character_personalities = {}
		end
		return
	end

	-- Legacy format (no version): clear and re-assign on demand
	log.warn("Loading legacy personalities store format (no version), starting fresh")
	character_personalities = {}
end

--- Get the raw character_id → personality_id map (read-only reference).
-- Used by batch query handler for collection iteration.
-- @return table  Map of character_id to personality_id
function M.get_all_mappings()
	return character_personalities
end

return M

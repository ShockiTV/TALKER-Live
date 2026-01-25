package.path = package.path .. ";./bin/lua/?.lua;"
local log = require("framework.logger")
local unique_backstories = require("infra.STALKER.unique_backstories")
local queries = talker_game_queries or require("tests.mocks.mock_game_queries")
local mcm = talker_mcm
local M = {}
local character_backstories = {}

function M.set_queries(q)
	log.spam("Setting queries...")
	queries = q
end

local function get_random_faction_backstory(faction)
	log.spam("Fetching random backstory for faction: " .. tostring(faction))
	-- Sanitize faction name (replace spaces with underscores for XML retrieval)
	local sanitized_faction = tostring(faction):gsub(" ", "_")
	return queries.load_random_xml("stories_" .. sanitized_faction)
end

local function get_random_backstory()
	log.spam("Fetching a generic random backstory...")
	return queries.load_random_xml("stories")
end

local function set_random_backstory(character)
	-- If the character is unique, we need to assign a specific backstory
	if tostring(character.game_id) == "0" then
		-- cache empty backstory for player so callers don't re-run assignment
		character_backstories[character.game_id] = ""
		return
	end
	if queries.is_unique_character_by_id(character.game_id) then
		log.debug("Handling unique character: " .. tostring(character.game_id))
		local tech_name = queries.get_technical_name_by_id(character.game_id)
		local backstory = unique_backstories[tech_name]
		if not backstory then
			log.info("No backstory found for unique character: " .. tech_name)
			backstory = get_random_backstory()
			log.info("Assigning random backstory instead: " .. backstory)
			character_backstories[character.game_id] = backstory
			return
		end
		character_backstories[character.game_id] = unique_backstories[tech_name]
		return
	end
	-- Otherwise, we assign a random backstory based on the faction
	local backstory = get_random_faction_backstory(tostring(character.faction))

	-- normalize/check returned value (handle table / empty table)
	if type(backstory) == "table" then
		if #backstory == 1 and type(backstory[1]) == "string" then
			backstory = backstory[1]
		else
			backstory = nil
		end
	end

	if not backstory or backstory == "" then
		log.spam("Faction backstory empty, loading generic backstory.")
		backstory = get_random_backstory()
	end
	log.spam("Assigning random backstory to character: " .. tostring(character.game_id) .. " - " .. tostring(backstory))
	character_backstories[character.game_id] = backstory
end

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

function M.get_save_data()
	log.debug("Returning character backstories for save.")
	return character_backstories
end

function M.clear()
	log.debug("Clearing character backstories cache.")
	character_backstories = {}
end

function M.load_save_data(saved_character_backstories)
	if mcm.get("reset_backstory") then
		log.debug("TALKER backstory reset is enabled. Clearing all saved backstories.")
		character_backstories = {}
	else
		if saved_character_backstories ~= nil then
			log.debug("TALKER backstory reset is disabled. Loading saved backstories.")
			character_backstories = saved_character_backstories
		else
			log.info("No saved backstories provided to load_save_data; keeping current cache.")
		end
	end
end

return M

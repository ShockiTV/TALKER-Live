package.path = package.path .. ";./bin/lua/?.lua;"
local log = require("framework.logger")
local unique_characters = require("infra.STALKER.unique_characters")
local queries = talker_game_queries or require("tests.mocks.mock_game_queries")
local mcm = talker_mcm
local M = {}
local character_personalities = {}

function M.set_queries(q)
	log.spam("Setting queries...")
	queries = q
end

local function get_random_personality()
	local personality = queries.load_random_xml("traits")
	local pid = ""
	if type(personality) == "table" then
		pid = tostring(personality.id or personality.text or "<table>")
	else
		pid = tostring(personality)
	end
	log.spam("Fetching a generic random personality... " .. pid)
	return personality
end

local function get_random_personalities(amountOfPersonalities, xml_key)
	local loadedPersonalities = {}
	local maxAttempts = math.max(10, amountOfPersonalities * 10)
	local attempts = 0

	while #loadedPersonalities < amountOfPersonalities and attempts < maxAttempts do
		local candidate = queries.load_random_xml(xml_key or "traits")
		attempts = attempts + 1
		if candidate then
			local candidate_id = candidate.id or tostring(candidate)
			local duplicate = false
			for _, p in ipairs(loadedPersonalities) do
				local pid = p.id or tostring(p)
				if pid == candidate_id then
					duplicate = true
					break
				end
			end
			if not duplicate then
				table.insert(loadedPersonalities, candidate)
			end
		end
	end

	if #loadedPersonalities < amountOfPersonalities then
		log.info(
			"Requested "
				.. amountOfPersonalities
				.. " unique personalities but only obtained "
				.. #loadedPersonalities
				.. " after "
				.. attempts
				.. " attempts."
		)
	end

	-- helper to convert a personality entry to a string
	local function personality_to_string(p)
		if type(p) == "table" then
			-- prefer a human-readable text field, fallback to id, then tostring
			return (p.text or p.id or tostring(p))
		end
		return tostring(p)
	end

	-- concatenate all found personalities into a single string separated by ' and '
	local parts = {}
	for _, p in ipairs(loadedPersonalities) do
		table.insert(parts, personality_to_string(p))
	end
	local result = table.concat(parts, " and ")

	log.spam("Fetching " .. #loadedPersonalities .. " unique generic personalities.")
	return result
end

local function get_random_faction_personalities(faction)
	log.spam("Fetching random personalities for faction: " .. tostring(faction))
	local sanitized_faction = tostring(faction):gsub(" ", "_")
	local key = "traits_" .. sanitized_faction
	if not queries.load_random_xml(key) then
		return nil
	end
	return get_random_personalities(2, key)
end

local function set_random_personality(character)
	-- If the character is unique, we need to assign a specific personality
	if tostring(character.game_id) == "0" then
		return "" -- player
	end
	if queries.is_unique_character_by_id(character.game_id) then
		log.debug("Handling unique character: " .. character.game_id)
		local tech_name = queries.get_technical_name_by_id(character.game_id)
		local personality = unique_characters[tech_name]
		if not personality then
			log.info("No personality found for unique character: " .. tech_name)
			personality = get_random_personalities(2)
			log.info("Assigning random personality instead: " .. personality)
			character_personalities[character.game_id] = personality
			return
		end
		character_personalities[character.game_id] = unique_characters[tech_name]
		return
	end
	-- Otherwise, we assign a random personality
	local personality = get_random_faction_personalities(character.faction)
	if not personality or personality == "" then
		log.spam("Faction personality empty, loading generic personality.")
		personality = get_random_personalities(2)
	end
	log.spam("Assigning random personality to character: " .. character.game_id .. " - " .. personality)
	character_personalities[character.game_id] = personality
end

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

function M.get_save_data()
	log.debug("Returning character personalities for save.")
	return character_personalities
end

function M.clear()
	log.debug("Clearing character personalities cache.")
	character_personalities = {}
end

function M.load_save_data(saved_character_personalities)
	if mcm.get("reset_personality") then
		log.debug("TALKER personality reset is enabled. Clearing all saved personalities.")
		character_personalities = {}
	else
		if saved_character_personalities ~= nil then
			log.debug("TALKER personality reset is disabled. Loading saved personalities.")
			character_personalities = saved_character_personalities
		else
			log.info("No saved personalities provided to load_save_data; keeping current cache.")
		end
	end
end

return M

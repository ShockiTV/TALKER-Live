-- interface/traits.lua (Task 3.2)
-- Traits map helper: builds personality + backstory lookup for candidate NPCs
-- Used by triggers to assemble context for Python dialogue

package.path = package.path .. ";./bin/lua/?.lua;"
local log = require("framework.logger")
local personalities = require("domain.repo.personalities")
local backstories = require("domain.repo.backstories")

local M = {}

--- Build a traits map for a list of characters.
-- For each character, looks up personality_id and backstory_id.
-- Returns: { character_id → {personality_id, backstory_id} }
-- @param candidates  Array of character objects with game_id field
-- @return traits     Table mapping char_id to {personality_id, backstory_id}
function M.build_traits_map(candidates)
	log.debug("Building traits map for %d candidates", #candidates)

	local traits = {}

	if not candidates or #candidates == 0 then
		return traits
	end

	for _, char in ipairs(candidates) do
		if char and char.game_id then
			local char_id = tostring(char.game_id)

			-- Get personality ID (will auto-assign if not cached)
			local personality_id = personalities.get_personality(char) or ""

			-- Get backstory ID (will auto-assign if not cached)
			local backstory_id = backstories.get_backstory(char) or ""

			traits[char_id] = {
				personality_id = personality_id,
				backstory_id = backstory_id,
			}

			log.spam("Traits for %s: personality=%s, backstory=%s", char_id, personality_id, backstory_id)
		end
	end

	return traits
end

--- Build a traits map for a single character (convenience function)
-- @param char  Character object with game_id
-- @return      Single-entry traits map: {char_id → {personality_id, backstory_id}}
function M.build_traits_for_character(char)
	if not char or not char.game_id then
		return {}
	end
	return M.build_traits_map({ char })
end

return M

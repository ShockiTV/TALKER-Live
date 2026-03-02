-- domain/service/importance.lua
-- Pure predicate: determines whether a character is "important" enough
-- to override the chance roll in trigger scripts.
--
-- An important person always triggers dialogue (publish_event) regardless
-- of the per-trigger chance setting.
--
-- Usage:
--   local importance = require("domain.service.importance")
--   local flags = { is_player = true, is_companion = false, is_unique = false, rank = "novice" }
--   if importance.is_important_person(flags) then ... end

local unique_npcs = require("domain.data.unique_npcs")

local M = {}

-- Ranks at or above this threshold are considered "important"
local IMPORTANT_RANK_THRESHOLD = "master"

-- Rank ordering for comparison (higher index = higher rank)
local RANK_ORDER = {
    novice    = 1,
    trainee   = 2,
    rookie    = 3,
    experienced = 4,
    professional = 5,
    veteran   = 6,
    expert    = 7,
    master    = 8,
    legend    = 9,
}

--- Check if a rank string is at or above the importance threshold.
-- @param rank  string  Rank name (e.g. "master", "veteran")
-- @return boolean
local function is_high_rank(rank)
    if not rank then return false end
    local val = RANK_ORDER[string.lower(rank)]
    local threshold = RANK_ORDER[IMPORTANT_RANK_THRESHOLD]
    if not val or not threshold then return false end
    return val >= threshold
end

--- Determine if a character is important based on pure data flags.
-- Important characters always get dialogue (bypass chance roll).
-- @param flags  table  { is_player=bool, is_companion=bool, is_unique=bool, rank=string }
-- @return boolean  true if the character is considered important
function M.is_important_person(flags)
    if not flags then return false end
    if flags.is_player then return true end
    if flags.is_companion then return true end
    if flags.is_unique then return true end
    if is_high_rank(flags.rank) then return true end
    return false
end

return M

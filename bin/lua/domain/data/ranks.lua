-- domain/data/ranks.lua
-- Rank value mappings, reputation tier thresholds, and character info formatting.
-- Extracted from talker_game_queries.script: get_rank_value(), get_reputation_tier(),
-- and get_character_event_info() (renamed to format_character_info()).
-- Zero engine dependencies — pure data module.
local M = {}

local RANKS_MAP = {
    ["novice"]       = 0,
    ["trainee"]      = 1,
    ["experienced"]  = 2,
    ["professional"] = 3,
    ["veteran"]      = 4,
    ["expert"]       = 5,
    ["master"]       = 6,
    ["legend"]       = 7,
}

--- Returns the numeric value for a rank name.
-- @param rank_name  Rank string (e.g. "veteran")
-- @return           Integer 0-7, or -1 if unknown
function M.get_value(rank_name)
    return RANKS_MAP[rank_name] or -1
end

--- Returns a human-readable reputation tier for a numeric reputation value.
-- Mirrors the thresholds from the original get_reputation_tier().
-- @param reputation_value  Number, or nil
-- @return                  Tier string ("Neutral", "Brilliant", etc.)
function M.get_reputation_tier(reputation_value)
    if not reputation_value then
        return "Neutral"
    end
    if type(reputation_value) ~= "number" then
        print("[ranks] get_reputation_tier: expected number, got " .. type(reputation_value))
        return "unknown"
    end
    if reputation_value >= 2000 then
        return "Excellent"
    elseif reputation_value >= 1500 then
        return "Brilliant"
    elseif reputation_value >= 1000 then
        return "Great"
    elseif reputation_value >= 500 then
        return "Good"
    elseif reputation_value >= -499 then
        return "Neutral"
    elseif reputation_value >= -999 then
        return "Bad"
    elseif reputation_value >= -1499 then
        return "Awful"
    elseif reputation_value >= -1999 then
        return "Dreary"
    else
        return "Terrible"
    end
end

--- Formats a Character table into a short human-readable description for event logs.
-- Extracted from get_character_event_info() in talker_game_queries.script.
-- Returns a plain string (not a format-string/args pair).
-- @param char  Character table with fields: name, faction, experience, reputation, visual_faction
-- @return      Formatted string, e.g. "Wolf (veteran Loner, Good rep)"
function M.format_character_info(char)
    if not char then return "Unknown" end
    if char.faction == "Monster" or char.faction == "Zombied" then
        return string.format("%s (%s)", char.name, char.faction)
    else
        if char.visual_faction then
            return string.format("%s (%s %s, %s rep) [disguised as %s]",
                char.name, char.experience, char.faction,
                char.reputation, char.visual_faction)
        else
            return string.format("%s (%s %s, %s rep)",
                char.name, char.experience, char.faction, char.reputation)
        end
    end
end

return M

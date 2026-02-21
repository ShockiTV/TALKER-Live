-- domain/service/importance.lua
-- Pure predicate for determining whether a character is "important" enough to
-- always generate AI dialogue (bypassing the base dialogue-chance filter).
-- Extracted from the inline is_important_person() function in talker_trigger_death.script.
-- Zero engine dependencies — all flags are resolved by the caller before passing.
local M = {}

--- Returns true if the character is considered an important person.
-- The caller is responsible for resolving engine-level properties and passing
-- pre-computed boolean flags.
--
-- @param flags  table:
--   is_player    (bool) — true if the character is the player
--   is_companion (bool) — true if the character is in the player's squad
--   is_unique    (bool) — true if the character is a named/story NPC
--   rank         (string, optional) — experience rank name (e.g. "master")
-- @return  boolean
function M.is_important_person(flags)
    if not flags then return false end
    if flags.is_player    then return true end
    if flags.is_companion then return true end
    if flags.is_unique    then return true end
    if flags.rank then
        local rank = string.lower(flags.rank)
        if rank == "master" or rank == "legend" then return true end
    end
    return false
end

return M

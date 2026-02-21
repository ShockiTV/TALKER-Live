-- domain/data/mutant_names.lua
-- Pattern-to-display-name mapping for mutant identification.
-- Extracted from the `patternToNameMap` inside `describe_mutant()` in talker_game_queries.script.
-- Zero engine dependencies — pure data module.
--
-- IMPORTANT: Order matters — "pseudodog" and "psy_dog" must appear BEFORE "dog" to avoid
-- false positives (since "m_pseudodog_01" contains both "pseudodog" and "dog").
local M = {}

-- Ordered list of {pattern, display_name} pairs.
-- Lua tables keyed by string have non-deterministic iteration order (pairs()), so we use
-- an indexed array here and scan linearly.
local PATTERNS = {
    { "zombie",      "Zombie" },
    { "rat",         "Rat" },
    { "tushkano",    "Tushkano" },
    { "boar",        "Boar (bulletproof head)" },           -- AI should not keep suggesting head shots
    { "flesh",       "Flesh (mutant pig, relatively passive)" },
    { "pseudodog",   "Pseudodog" },                         -- must come before "dog"
    { "psy_dog",     "Psy Dog" },                           -- must come before "dog"
    { "cat",         "Mutant Cat" },
    { "fracture",    "Fracture" },
    { "snork",       "Snork" },
    { "lurker",      "Lurker" },
    { "bloodsucker", "Bloodsucker" },
    { "burer",       "Burer" },
    { "controller",  "Controller" },
    { "poltergeist", "Poltergeist" },
    { "psysucker",   "Psysucker" },
    { "chimera",     "Chimera (extremely dangerous!)" },
    { "gigant",      "Pseudogiant (extremely dangerous!)" },
    { "karlik",      "Karlik" },
    { "dog",         "Dog" },                               -- always last: "dog" is a substring of "pseudodog"
}

--- Returns a human-readable display name for a mutant given its technical section name.
-- @param tech_name  Technical name (e.g. "m_bloodsucker_e_01")
-- @return           Display string prefixed with "a " (e.g. "a Bloodsucker"), or
--                   "a <tech_name>" for unknown/modded mutants.
function M.describe(tech_name)
    if not tech_name then return "a Unknown" end
    for _, pair in ipairs(PATTERNS) do
        local pattern, name = pair[1], pair[2]
        if string.find(tech_name, pattern) then
            return "a " .. name
        end
    end
    return "a " .. tech_name
end

--- The raw ordered pattern list (exposed for tooling / tests).
M.patterns = PATTERNS

return M

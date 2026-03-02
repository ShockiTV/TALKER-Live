-- domain/service/chance.lua
-- Shared chance utility for trigger scripts.
-- Reads MCM value dynamically at call time (never cached).
--
-- Usage:
--   local chance = require("domain.service.chance")
--   if chance.check("triggers/death/chance_player") then ... end

local config = require("interface.config")

local M = {}

--- Check whether a chance roll passes for the given MCM key.
-- Reads the integer 0–100 value from config at call time (dynamic).
-- @param mcm_key  string  Config key that returns an integer 0–100
-- @return boolean  true if roll passes, false otherwise
function M.check(mcm_key)
    local pct = tonumber(config.get(mcm_key)) or 0
    if pct >= 100 then return true end
    if pct <= 0 then return false end
    return math.random(1, 100) <= pct
end

return M

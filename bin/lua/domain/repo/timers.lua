-- timers.lua — Domain repository for persisting timer values across saves
-- Holds the cumulative game time accumulator and the idle conversation check timer.
package.path = package.path .. ";./bin/lua/?.lua;"
local logger = require("framework.logger")

-- Version for timers store save data format
-- 1 is first versioned format (legacy unversioned saves are treated as version 0)
local TIMERS_VERSION = 1

local timers = {}

-- Internal state
local data = {
    game_time_accumulator = 0,   -- number: cumulative game time in ms across save/load cycles
    idle_last_check_time = 0,    -- number: last time the idle conversation check ran (ms)
}

--------------------------------------------------------------------------------
-- PUBLIC API
--------------------------------------------------------------------------------

--- Get the game time accumulator (cumulative ms across all save/load cycles).
-- This value is set once on load and is read-only during gameplay.
-- @return number
function timers.get_game_time_accumulator()
    return data.game_time_accumulator
end

--- Get the idle conversation last check time (ms).
-- @return number
function timers.get_idle_last_check_time()
    return data.idle_last_check_time
end

--- Set the idle conversation last check time (ms).
-- @param value number
function timers.set_idle_last_check_time(value)
    data.idle_last_check_time = value or 0
end

--- Clear all stored data to fresh state.
function timers.clear()
    data.game_time_accumulator = 0
    data.idle_last_check_time = 0
end

--------------------------------------------------------------------------------
-- PERSISTENCE — Envelope pattern
--------------------------------------------------------------------------------

--- Get save data with envelope pattern.
-- The caller passes the current computed game time so the store never
-- depends on time_global() or any game engine API.
-- @param current_game_time_ms number  The cumulative game time at save time
-- @return table  { timers_version = 1, timers = { ... } }
function timers.get_save_data(current_game_time_ms)
    return {
        timers_version = TIMERS_VERSION,
        timers = {
            game_time_accumulator = current_game_time_ms or 0,
            idle_last_check_time = data.idle_last_check_time,
        },
    }
end

--- Load save data. Handles versioned format and legacy migration.
-- @param saved_data table|nil  The raw saved data envelope
function timers.load_save_data(saved_data)
    logger.info("Loading timers store...")

    -- Handle nil data → start fresh
    if not saved_data then
        logger.info("No saved timers data, starting fresh")
        timers.clear()
        return
    end

    -- Check for versioned format
    if saved_data.timers_version then
        if saved_data.timers_version == TIMERS_VERSION then
            -- Current version: load normally
            logger.info("Loading versioned timers store (v" .. tostring(saved_data.timers_version) .. ")")
            local inner = saved_data.timers or {}
            data.game_time_accumulator = inner.game_time_accumulator or 0
            data.idle_last_check_time = inner.idle_last_check_time or 0
        else
            -- Unknown version: start fresh with warning
            logger.warn("Unknown timers store version: " .. tostring(saved_data.timers_version)
                .. ". Expected: " .. tostring(TIMERS_VERSION) .. ". Starting fresh.")
            timers.clear()
        end
    else
        -- Legacy format (no version field): migrate from old inline keys
        logger.info("Legacy timers format detected, migrating...")
        data.game_time_accumulator = saved_data.game_time_since_last_load or 0
        data.idle_last_check_time = saved_data.talker_idle_last_check_time_ms or 0
        logger.info("Legacy migration complete: game_time_accumulator="
            .. tostring(data.game_time_accumulator)
            .. ", idle_last_check_time=" .. tostring(data.idle_last_check_time))
    end
end

return timers

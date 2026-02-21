-- levels.lua — Domain repository for level visit history
-- Tracks visit counts, detailed visit logs, and transition detection state (from_level)
package.path = package.path .. ";./bin/lua/?.lua;"
local logger = require("framework.logger")

-- Version for levels store save data format
-- 1 is first versioned format (legacy unversioned saves are treated as version 0)
local LEVELS_VERSION = 1

local levels = {}

-- Internal state
local data = {
    from_level = nil,  -- string: level the player was on before the current one
    visits = {},       -- map<level_id, { count = N, log = { ... } }>
}

--------------------------------------------------------------------------------
-- PUBLIC API
--------------------------------------------------------------------------------

--- Record a visit to a level.
-- @param level_id string   The level being visited (e.g. "l01_escape")
-- @param game_time_ms number  Game time in milliseconds
-- @param from_level string|nil  The level transitioned from
-- @param companions table  List of companion IDs (may be empty)
function levels.record_visit(level_id, game_time_ms, from_level, companions)
    if not level_id then
        logger.warn("levels.record_visit: level_id is nil, ignoring")
        return
    end

    if not data.visits[level_id] then
        data.visits[level_id] = { count = 0, log = {} }
    end

    local entry = data.visits[level_id]
    entry.count = entry.count + 1

    local log_entry = {
        game_time_ms = game_time_ms or 0,
        from_level = from_level,
        companions = companions or {},
    }
    entry.log[#entry.log + 1] = log_entry
end

--- Get the authoritative visit count for a level.
-- @param level_id string
-- @return number  Visit count (0 if never visited)
function levels.get_visit_count(level_id)
    local entry = data.visits[level_id]
    if entry then
        return entry.count
    end
    return 0
end

--- Get the visit log for a level (chronological, oldest first).
-- @param level_id string
-- @return table  Array of log entries (empty table if never visited)
function levels.get_log(level_id)
    local entry = data.visits[level_id]
    if entry then
        return entry.log
    end
    return {}
end

--- Get the from_level (the level the player was on before the current one).
-- @return string|nil
function levels.get_from_level()
    return data.from_level
end

--- Set the from_level.
-- @param level_id string|nil
function levels.set_from_level(level_id)
    data.from_level = level_id
end

--- Clear all stored data.
function levels.clear()
    data.from_level = nil
    data.visits = {}
end

--------------------------------------------------------------------------------
-- PERSISTENCE — Envelope pattern
--------------------------------------------------------------------------------

--- Get save data with envelope pattern and optional pruning.
-- Reads pruning config from interface.config at save time.
-- @return table  { levels_version = 1, levels = { from_level = ..., visits = { ... } } }
function levels.get_save_data()
    -- Read pruning config (lazy require to avoid circular deps at load time)
    local max_entries = 0
    local ok, config = pcall(require, "interface.config")
    if ok and config and config.max_log_entries_per_level then
        max_entries = config.max_log_entries_per_level() or 0
    end

    -- Fast path: no pruning, return data as-is
    if max_entries <= 0 then
        return {
            levels_version = LEVELS_VERSION,
            levels = {
                from_level = data.from_level,
                visits = data.visits,
            },
        }
    end

    -- Build visits with pruning
    local pruned_visits = {}
    for level_id, entry in pairs(data.visits) do
        local log = entry.log
        if #log > max_entries then
            local pruned_log = {}
            local start_idx = #log - max_entries + 1
            for i = start_idx, #log do
                pruned_log[#pruned_log + 1] = log[i]
            end
            log = pruned_log
        end
        pruned_visits[level_id] = {
            count = entry.count,  -- authoritative, never reduced by pruning
            log = log,
        }
    end

    return {
        levels_version = LEVELS_VERSION,
        levels = {
            from_level = data.from_level,
            visits = pruned_visits,
        },
    }
end

--- Load save data. Handles versioned format and legacy migration.
-- @param saved_data table|nil  The raw saved data envelope
function levels.load_save_data(saved_data)
    logger.info("Loading levels store...")

    -- Handle nil data → start fresh
    if not saved_data then
        logger.info("No saved levels data, starting fresh")
        levels.clear()
        return
    end

    -- Check for versioned format
    if saved_data.levels_version then
        if saved_data.levels_version == LEVELS_VERSION then
            -- Current version: load normally
            logger.info("Loading versioned levels store (v" .. tostring(saved_data.levels_version) .. ")")
            local inner = saved_data.levels or {}
            data.from_level = inner.from_level
            data.visits = inner.visits or {}
        else
            -- Unknown version: start fresh with warning
            logger.warn("Unknown levels store version: " .. tostring(saved_data.levels_version)
                .. ". Expected: " .. tostring(LEVELS_VERSION) .. ". Starting fresh.")
            levels.clear()
        end
    else
        -- Legacy format (no version field): migrate
        -- Expected legacy keys: level_visit_count (table<level, int>), from_level (string)
        logger.info("Legacy levels format detected, migrating...")
        levels.clear()

        local legacy_counts = saved_data.level_visit_count
        if legacy_counts and type(legacy_counts) == "table" then
            for level_id, count in pairs(legacy_counts) do
                if type(count) == "number" then
                    data.visits[level_id] = {
                        count = count,
                        log = {},  -- no log data in legacy format
                    }
                end
            end
        end

        if saved_data.from_level then
            data.from_level = saved_data.from_level
        end

        logger.info("Legacy migration complete: migrated "
            .. tostring(levels._count_levels()) .. " levels")
    end
end

--- (Internal) Count the number of levels with visits (used for logging).
function levels._count_levels()
    local count = 0
    for _ in pairs(data.visits) do
        count = count + 1
    end
    return count
end

--- Get the raw visits map (read-only reference).
-- Used by batch query handler for collection iteration.
-- @return table  Map of level_id to {count, log}
function levels.get_all_visits()
    return data.visits
end

return levels

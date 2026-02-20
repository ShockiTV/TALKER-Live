-- Test suite for levels domain repository
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'

local luaunit = require('tests.utils.luaunit')

-- Pre-populate a mock interface.config so levels.lua can require it without talker_mcm
local mock_config = { max_log_entries_per_level = function() return 0 end }
package.loaded["interface.config"] = mock_config

local levels = require('domain.repo.levels')

-- ============================================================================
-- 5.1: Record, query count, query log, from_level, clear
-- ============================================================================

function testRecordFirstVisit()
    levels.clear()
    levels.record_visit("l01_escape", 1000, nil, {})

    luaunit.assertEquals(levels.get_visit_count("l01_escape"), 1)

    local log = levels.get_log("l01_escape")
    luaunit.assertEquals(#log, 1)
    luaunit.assertEquals(log[1].game_time_ms, 1000)
    luaunit.assertNil(log[1].from_level)
    luaunit.assertEquals(#log[1].companions, 0)
end

function testRecordSubsequentVisit()
    levels.clear()
    levels.record_visit("l01_escape", 1000, nil, {})
    levels.record_visit("l01_escape", 2000, "l02_garbage", {101, 102})

    luaunit.assertEquals(levels.get_visit_count("l01_escape"), 2)

    local log = levels.get_log("l01_escape")
    luaunit.assertEquals(#log, 2)
    luaunit.assertEquals(log[2].game_time_ms, 2000)
    luaunit.assertEquals(log[2].from_level, "l02_garbage")
    luaunit.assertEquals(#log[2].companions, 2)
end

function testVisitWithNoCompanions()
    levels.clear()
    levels.record_visit("l03_agroprom", 5000, "l01_escape", {})

    local log = levels.get_log("l03_agroprom")
    luaunit.assertEquals(#log[1].companions, 0)
end

function testQueryUnvisitedLevel()
    levels.clear()
    luaunit.assertEquals(levels.get_visit_count("never_been"), 0)
end

function testGetLogUnvisitedLevel()
    levels.clear()
    local log = levels.get_log("never_been")
    luaunit.assertNotNil(log)
    luaunit.assertEquals(#log, 0)
end

function testFromLevelSetAndGet()
    levels.clear()
    luaunit.assertNil(levels.get_from_level())

    levels.set_from_level("l01_escape")
    luaunit.assertEquals(levels.get_from_level(), "l01_escape")

    levels.set_from_level("l02_garbage")
    luaunit.assertEquals(levels.get_from_level(), "l02_garbage")
end

function testFromLevelNilOnFreshGame()
    levels.clear()
    luaunit.assertNil(levels.get_from_level())
end

function testClearRemovesAllData()
    levels.clear()
    levels.record_visit("l01_escape", 1000, nil, {})
    levels.set_from_level("l01_escape")

    levels.clear()

    luaunit.assertEquals(levels.get_visit_count("l01_escape"), 0)
    luaunit.assertEquals(#levels.get_log("l01_escape"), 0)
    luaunit.assertNil(levels.get_from_level())
end

function testRecordVisitNilLevelIdIgnored()
    levels.clear()
    levels.record_visit(nil, 1000, nil, {})
    -- Should not error and store nothing
    luaunit.assertEquals(levels.get_visit_count(nil), 0)
end

-- ============================================================================
-- 5.2: Versioned save/load round-trip
-- ============================================================================

function testSaveDataReturnsVersionedEnvelope()
    levels.clear()
    levels.record_visit("l01_escape", 1000, nil, {})
    levels.set_from_level("l01_escape")

    local save_data = levels.get_save_data()

    luaunit.assertNotNil(save_data.levels_version)
    luaunit.assertEquals(save_data.levels_version, 1)
    luaunit.assertNotNil(save_data.levels)
    luaunit.assertEquals(save_data.levels.from_level, "l01_escape")
    luaunit.assertNotNil(save_data.levels.visits)
    luaunit.assertNotNil(save_data.levels.visits["l01_escape"])
end

function testSaveLoadRoundTrip()
    levels.clear()
    levels.record_visit("l01_escape", 1000, nil, {})
    levels.record_visit("l02_garbage", 2000, "l01_escape", {101})
    levels.set_from_level("l02_garbage")

    local save_data = levels.get_save_data()

    -- Clear and reload
    levels.clear()
    levels.load_save_data(save_data)

    luaunit.assertEquals(levels.get_visit_count("l01_escape"), 1)
    luaunit.assertEquals(levels.get_visit_count("l02_garbage"), 1)
    luaunit.assertEquals(levels.get_from_level(), "l02_garbage")

    local log = levels.get_log("l02_garbage")
    luaunit.assertEquals(#log, 1)
    luaunit.assertEquals(log[1].game_time_ms, 2000)
    luaunit.assertEquals(log[1].from_level, "l01_escape")
    luaunit.assertEquals(log[1].companions[1], 101)
end

function testLoadNilDataStartsFresh()
    levels.clear()
    levels.record_visit("l01_escape", 1000, nil, {})

    levels.load_save_data(nil)

    luaunit.assertEquals(levels.get_visit_count("l01_escape"), 0)
    luaunit.assertNil(levels.get_from_level())
end

function testLoadUnknownVersionStartsFresh()
    levels.clear()
    levels.record_visit("l01_escape", 1000, nil, {})

    levels.load_save_data({ levels_version = 999, levels = { from_level = "x", visits = {} } })

    luaunit.assertEquals(levels.get_visit_count("l01_escape"), 0)
    luaunit.assertNil(levels.get_from_level())
end

-- ============================================================================
-- 5.3: Legacy migration (flat visit count + from_level → new format)
-- ============================================================================

function testLegacyMigrationWithVisitCountsAndFromLevel()
    levels.clear()

    local legacy_data = {
        level_visit_count = {
            ["l01_escape"] = 5,
            ["l02_garbage"] = 3,
        },
        from_level = "l02_garbage",
    }

    levels.load_save_data(legacy_data)

    luaunit.assertEquals(levels.get_visit_count("l01_escape"), 5)
    luaunit.assertEquals(levels.get_visit_count("l02_garbage"), 3)
    luaunit.assertEquals(levels.get_from_level(), "l02_garbage")
    -- Legacy migration has no log entries
    luaunit.assertEquals(#levels.get_log("l01_escape"), 0)
    luaunit.assertEquals(#levels.get_log("l02_garbage"), 0)
end

function testLegacyMigrationWithOnlyVisitCounts()
    levels.clear()

    local legacy_data = {
        level_visit_count = {
            ["l01_escape"] = 2,
        },
    }

    levels.load_save_data(legacy_data)

    luaunit.assertEquals(levels.get_visit_count("l01_escape"), 2)
    luaunit.assertNil(levels.get_from_level())
end

function testLegacyMigrationWithEmptyData()
    levels.clear()
    levels.record_visit("l01_escape", 1000, nil, {})

    -- Legacy format but empty tables
    levels.load_save_data({ level_visit_count = {} })

    luaunit.assertEquals(levels.get_visit_count("l01_escape"), 0)
    luaunit.assertNil(levels.get_from_level())
end

-- ============================================================================
-- 5.4: Pruning on save (0 = no pruning, N = keep last N)
-- ============================================================================

-- Override config for pruning tests
local original_config_getter = nil

local function set_pruning_config(value)
    if not original_config_getter then
        original_config_getter = mock_config.max_log_entries_per_level
    end
    mock_config.max_log_entries_per_level = function() return value end
end

local function restore_pruning_config()
    if original_config_getter then
        mock_config.max_log_entries_per_level = original_config_getter
        original_config_getter = nil
    end
end

function testPruningDisabledKeepsAllEntries()
    levels.clear()
    set_pruning_config(0)

    for i = 1, 20 do
        levels.record_visit("l01_escape", i * 1000, "l02_garbage", {})
    end

    local save_data = levels.get_save_data()
    local saved_log = save_data.levels.visits["l01_escape"].log

    luaunit.assertEquals(#saved_log, 20)
    luaunit.assertEquals(save_data.levels.visits["l01_escape"].count, 20)

    restore_pruning_config()
end

function testPruningEnabledKeepsLastN()
    levels.clear()
    set_pruning_config(5)

    for i = 1, 20 do
        levels.record_visit("l01_escape", i * 1000, "l02_garbage", {})
    end

    local save_data = levels.get_save_data()
    local saved_log = save_data.levels.visits["l01_escape"].log

    -- Should keep only the last 5 entries
    luaunit.assertEquals(#saved_log, 5)
    -- Count is authoritative, not affected by pruning
    luaunit.assertEquals(save_data.levels.visits["l01_escape"].count, 20)
    -- Verify the kept entries are the most recent (last 5)
    luaunit.assertEquals(saved_log[1].game_time_ms, 16000)
    luaunit.assertEquals(saved_log[5].game_time_ms, 20000)

    restore_pruning_config()
end

function testPruningDoesNotAffectSmallLogs()
    levels.clear()
    set_pruning_config(10)

    for i = 1, 3 do
        levels.record_visit("l01_escape", i * 1000, nil, {})
    end

    local save_data = levels.get_save_data()
    local saved_log = save_data.levels.visits["l01_escape"].log

    -- Only 3 entries, pruning limit is 10, so all kept
    luaunit.assertEquals(#saved_log, 3)
    luaunit.assertEquals(save_data.levels.visits["l01_escape"].count, 3)

    restore_pruning_config()
end

function testPruningPerLevel()
    levels.clear()
    set_pruning_config(2)

    for i = 1, 5 do
        levels.record_visit("l01_escape", i * 1000, nil, {})
    end
    for i = 1, 3 do
        levels.record_visit("l02_garbage", (i + 10) * 1000, nil, {})
    end

    local save_data = levels.get_save_data()

    luaunit.assertEquals(#save_data.levels.visits["l01_escape"].log, 2)
    luaunit.assertEquals(save_data.levels.visits["l01_escape"].count, 5)
    luaunit.assertEquals(#save_data.levels.visits["l02_garbage"].log, 2)
    luaunit.assertEquals(save_data.levels.visits["l02_garbage"].count, 3)

    restore_pruning_config()
end

-- Run the tests
os.exit(luaunit.LuaUnit.run())

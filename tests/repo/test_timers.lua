-- Test suite for timers domain repository
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require('tests.utils.luaunit')

local timers = require('domain.repo.timers')

-- ============================================================================
-- Fresh state
-- ============================================================================

function testFreshStateReturnsZeros()
    timers.clear()
    luaunit.assertEquals(timers.get_game_time_accumulator(), 0)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 0)
end

-- ============================================================================
-- Idle check time getter/setter
-- ============================================================================

function testSetAndGetIdleLastCheckTime()
    timers.clear()
    timers.set_idle_last_check_time(42000)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 42000)
end

function testSetIdleLastCheckTimeWithNilDefaultsToZero()
    timers.clear()
    timers.set_idle_last_check_time(12345)
    timers.set_idle_last_check_time(nil)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 0)
end

-- ============================================================================
-- get_save_data envelope structure
-- ============================================================================

function testGetSaveDataEnvelopeStructure()
    timers.clear()
    timers.set_idle_last_check_time(123000)
    local save = timers.get_save_data(500000)

    luaunit.assertEquals(save.timers_version, 1)
    luaunit.assertNotNil(save.timers)
    luaunit.assertEquals(save.timers.game_time_accumulator, 500000)
    luaunit.assertEquals(save.timers.idle_last_check_time, 123000)
end

function testGetSaveDataUsesPassedInTime()
    timers.clear()
    -- The stored accumulator is 0 after clear, but get_save_data uses the passed-in value
    local save = timers.get_save_data(999999)
    luaunit.assertEquals(save.timers.game_time_accumulator, 999999)
end

function testGetSaveDataWithNilTimeDefaultsToZero()
    timers.clear()
    local save = timers.get_save_data(nil)
    luaunit.assertEquals(save.timers.game_time_accumulator, 0)
end

-- ============================================================================
-- load_save_data with versioned data
-- ============================================================================

function testLoadVersionedData()
    timers.clear()
    timers.load_save_data({
        timers_version = 1,
        timers = {
            game_time_accumulator = 500000,
            idle_last_check_time = 123000,
        },
    })
    luaunit.assertEquals(timers.get_game_time_accumulator(), 500000)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 123000)
end

function testLoadVersionedDataWithMissingFields()
    timers.clear()
    timers.set_idle_last_check_time(99999) -- set something first
    timers.load_save_data({
        timers_version = 1,
        timers = {},
    })
    luaunit.assertEquals(timers.get_game_time_accumulator(), 0)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 0)
end

function testLoadVersionedDataWithMissingTimersTable()
    timers.clear()
    timers.load_save_data({
        timers_version = 1,
        -- no timers table
    })
    luaunit.assertEquals(timers.get_game_time_accumulator(), 0)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 0)
end

-- ============================================================================
-- load_save_data with nil
-- ============================================================================

function testLoadNilDataStartsFresh()
    timers.clear()
    timers.set_idle_last_check_time(42000)
    timers.load_save_data(nil)
    luaunit.assertEquals(timers.get_game_time_accumulator(), 0)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 0)
end

-- ============================================================================
-- load_save_data with unknown version
-- ============================================================================

function testLoadUnknownVersionClearsState()
    timers.clear()
    timers.load_save_data({
        timers_version = 99,
        timers = {
            game_time_accumulator = 500000,
            idle_last_check_time = 123000,
        },
    })
    luaunit.assertEquals(timers.get_game_time_accumulator(), 0)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 0)
end

-- ============================================================================
-- Legacy migration
-- ============================================================================

function testLegacyMigrationBothKeys()
    timers.clear()
    timers.load_save_data({
        game_time_since_last_load = 500000,
        talker_idle_last_check_time_ms = 123000,
    })
    luaunit.assertEquals(timers.get_game_time_accumulator(), 500000)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 123000)
end

function testLegacyMigrationGameTimeOnly()
    timers.clear()
    timers.load_save_data({
        game_time_since_last_load = 500000,
    })
    luaunit.assertEquals(timers.get_game_time_accumulator(), 500000)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 0)
end

function testLegacyMigrationIdleTimerOnly()
    timers.clear()
    timers.load_save_data({
        talker_idle_last_check_time_ms = 123000,
    })
    luaunit.assertEquals(timers.get_game_time_accumulator(), 0)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 123000)
end

function testLegacyMigrationEmptyTable()
    -- Empty table with no timers_version triggers legacy path, both default to 0
    timers.clear()
    timers.set_idle_last_check_time(99999)
    timers.load_save_data({})
    luaunit.assertEquals(timers.get_game_time_accumulator(), 0)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 0)
end

-- ============================================================================
-- clear()
-- ============================================================================

function testClearResetsAllValues()
    timers.load_save_data({
        timers_version = 1,
        timers = {
            game_time_accumulator = 500000,
            idle_last_check_time = 123000,
        },
    })
    timers.clear()
    luaunit.assertEquals(timers.get_game_time_accumulator(), 0)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 0)
end

-- ============================================================================
-- Round-trip: save → load
-- ============================================================================

function testRoundTrip()
    timers.clear()
    timers.set_idle_last_check_time(42000)
    local save = timers.get_save_data(750000)

    timers.clear()
    timers.load_save_data(save)

    luaunit.assertEquals(timers.get_game_time_accumulator(), 750000)
    luaunit.assertEquals(timers.get_idle_last_check_time(), 42000)
end

os.exit(luaunit.LuaUnit.run())

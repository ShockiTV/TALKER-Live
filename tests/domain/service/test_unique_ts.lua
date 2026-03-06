-- tests/domain/service/test_unique_ts.lua
-- Tests for the global unique timestamp generator
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local mock_engine = require("tests.mocks.mock_engine")
local unique_ts = require("domain.service.unique_ts")

local function setup()
	unique_ts.reset()
	mock_engine._reset()
end

------------------------------------------------------------
-- Requirement: unique_ts returns monotonically increasing values
------------------------------------------------------------

function testSameTickCollision()
	setup()
	mock_engine._set("get_game_time_ms", 1000)

	local ts1 = unique_ts.unique_ts()
	local ts2 = unique_ts.unique_ts()
	local ts3 = unique_ts.unique_ts()

	luaunit.assertEquals(ts1, 1000)
	luaunit.assertEquals(ts2, 1001)
	luaunit.assertEquals(ts3, 1002)

	-- All unique
	luaunit.assertNotEquals(ts1, ts2)
	luaunit.assertNotEquals(ts2, ts3)
end

function testCrossTickNormal()
	setup()
	mock_engine._set("get_game_time_ms", 1000)
	local ts1 = unique_ts.unique_ts()
	luaunit.assertEquals(ts1, 1000)

	-- Move to a later tick
	mock_engine._set("get_game_time_ms", 2000)
	local ts2 = unique_ts.unique_ts()
	luaunit.assertEquals(ts2, 2000) -- raw game_time_ms, no bump needed
end

function testResetBehavior()
	setup()
	mock_engine._set("get_game_time_ms", 5000)
	local ts1 = unique_ts.unique_ts()
	luaunit.assertEquals(ts1, 5000)

	-- Reset state
	unique_ts.reset()
	luaunit.assertEquals(unique_ts.get_last_ts(), 0)

	-- Now same time should work from scratch
	local ts2 = unique_ts.unique_ts()
	luaunit.assertEquals(ts2, 5000)
end

function testBumpDoesNotExceedOnePerCall()
	setup()
	mock_engine._set("get_game_time_ms", 100)

	local results = {}
	for i = 1, 10 do
		results[i] = unique_ts.unique_ts()
	end

	-- Should be 100, 101, 102, ..., 109
	for i = 1, 10 do
		luaunit.assertEquals(results[i], 99 + i)
	end
end

function testThatTimeJumpBackwardStillBumps()
	setup()
	mock_engine._set("get_game_time_ms", 1000)
	local ts1 = unique_ts.unique_ts()
	luaunit.assertEquals(ts1, 1000)

	-- Time goes backward (shouldn't happen, but defensive)
	mock_engine._set("get_game_time_ms", 500)
	local ts2 = unique_ts.unique_ts()
	luaunit.assertEquals(ts2, 1001) -- bumps from last, not from current time
end

function testGetLastTs()
	setup()
	luaunit.assertEquals(unique_ts.get_last_ts(), 0)

	mock_engine._set("get_game_time_ms", 42)
	unique_ts.unique_ts()
	luaunit.assertEquals(unique_ts.get_last_ts(), 42)
end

os.exit(luaunit.LuaUnit.run())

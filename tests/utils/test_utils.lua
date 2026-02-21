package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require('tests.utils.luaunit')
local utils   = require('framework.utils')

-- ──────────────────────────────────────────────────────────────────────────────
-- must_exist
-- ──────────────────────────────────────────────────────────────────────────────

function testMustExist_nonNilPasses()
    -- Should not throw
    local ok = pcall(utils.must_exist, {}, "test_func")
    luaunit.assertTrue(ok)
end

function testMustExist_nilRaisesError()
    local ok, err = pcall(utils.must_exist, nil, "my_func")
    luaunit.assertFalse(ok)
    luaunit.assertStrContains(err, "my_func")
    luaunit.assertStrContains(err, "nil")
end

-- ──────────────────────────────────────────────────────────────────────────────
-- try
-- ──────────────────────────────────────────────────────────────────────────────

function testTry_successReturnsResult()
    local result = utils.try(function() return 42 end)
    luaunit.assertEquals(result, 42)
end

function testTry_errorReturnsNil()
    local result = utils.try(function() error("boom") end)
    luaunit.assertNil(result)
end

function testTry_forwardsArgs()
    local result = utils.try(function(a, b) return a + b end, 3, 4)
    luaunit.assertEquals(result, 7)
end

-- ──────────────────────────────────────────────────────────────────────────────
-- join_tables
-- ──────────────────────────────────────────────────────────────────────────────

function testJoinTables_twoArrays()
    local result = utils.join_tables({1, 2}, {3, 4})
    luaunit.assertEquals(result, {1, 2, 3, 4})
end

function testJoinTables_firstNil()
    local result = utils.join_tables(nil, {3, 4})
    luaunit.assertEquals(result, {3, 4})
end

function testJoinTables_secondNil()
    local result = utils.join_tables({1, 2}, nil)
    luaunit.assertEquals(result, {1, 2})
end

function testJoinTables_bothNil()
    local result = utils.join_tables(nil, nil)
    luaunit.assertEquals(result, {})
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Set
-- ──────────────────────────────────────────────────────────────────────────────

function testSet_conversion()
    local s = utils.Set({"a", "b", "c"})
    luaunit.assertEquals(s, {a = true, b = true, c = true})
end

function testSet_membershipTrue()
    local s = utils.Set({"alpha", "beta"})
    luaunit.assertTrue(s["alpha"])
end

function testSet_membershipMissing()
    local s = utils.Set({"alpha", "beta"})
    luaunit.assertNil(s["gamma"])
end

-- ──────────────────────────────────────────────────────────────────────────────
-- shuffle
-- ──────────────────────────────────────────────────────────────────────────────

function testShuffle_preservesElements()
    local input = {1, 2, 3, 4, 5}
    local copy  = {1, 2, 3, 4, 5}
    utils.shuffle(input)
    -- Same elements regardless of order
    table.sort(input)
    luaunit.assertEquals(input, copy)
end

function testShuffle_modifiesInPlace()
    local t = {1, 2, 3}
    local returned = utils.shuffle(t)
    luaunit.assertTrue(returned == t)  -- same table reference
end

-- ──────────────────────────────────────────────────────────────────────────────
-- safely
-- ──────────────────────────────────────────────────────────────────────────────

function testSafely_successReturnsValue()
    local safe_fn = utils.safely(function() return 42 end, "test")
    luaunit.assertEquals(safe_fn(), 42)
end

function testSafely_errorDoesNotPropagate()
    local safe_fn = utils.safely(function() error("boom") end, "test")
    local ok = pcall(safe_fn)   -- should not throw
    luaunit.assertTrue(ok)
end

function testSafely_forwardsArgs()
    local safe_fn = utils.safely(function(a, b) return a + b end, "add")
    luaunit.assertEquals(safe_fn(10, 20), 30)
end

-- ──────────────────────────────────────────────────────────────────────────────
-- array_iter
-- ──────────────────────────────────────────────────────────────────────────────

function testArrayIter_returnsElementsInOrder()
    local iter = utils.array_iter({10, 20, 30})
    luaunit.assertEquals(iter(), 10)
    luaunit.assertEquals(iter(), 20)
    luaunit.assertEquals(iter(), 30)
end

function testArrayIter_exhaustedReturnsNil()
    local iter = utils.array_iter({10})
    iter()  -- consume the only element
    luaunit.assertNil(iter())
end

function testArrayIter_emptyArray()
    local iter = utils.array_iter({})
    luaunit.assertNil(iter())
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Run
-- ──────────────────────────────────────────────────────────────────────────────
os.exit(luaunit.LuaUnit.run())

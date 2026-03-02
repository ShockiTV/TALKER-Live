package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit     = require('tests.utils.luaunit')
local mock_engine = require('tests.mocks.mock_engine')
local chance      = require('domain.service.chance')

-- ──────────────────────────────────────────────────────────────────────────────
-- Setup / Teardown
-- ──────────────────────────────────────────────────────────────────────────────

function setUp()
    mock_engine._reset()
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Module structure
-- ──────────────────────────────────────────────────────────────────────────────

function testModuleLoads()
    luaunit.assertNotNil(chance)
    luaunit.assertEquals(type(chance.check), "function")
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Boundary: 100 always passes
-- ──────────────────────────────────────────────────────────────────────────────

function testChance100_alwaysTrue()
    mock_engine._set("triggers/death/chance_player", 100)
    for _ = 1, 50 do
        luaunit.assertTrue(chance.check("triggers/death/chance_player"))
    end
end

function testChanceAbove100_alwaysTrue()
    mock_engine._set("triggers/death/chance_player", 150)
    for _ = 1, 50 do
        luaunit.assertTrue(chance.check("triggers/death/chance_player"))
    end
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Boundary: 0 always fails
-- ──────────────────────────────────────────────────────────────────────────────

function testChance0_alwaysFalse()
    mock_engine._set("triggers/death/chance_player", 0)
    for _ = 1, 50 do
        luaunit.assertFalse(chance.check("triggers/death/chance_player"))
    end
end

function testChanceNegative_alwaysFalse()
    mock_engine._set("triggers/death/chance_player", -10)
    for _ = 1, 50 do
        luaunit.assertFalse(chance.check("triggers/death/chance_player"))
    end
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Nil / missing key defaults to 0 (no dialogue)
-- ──────────────────────────────────────────────────────────────────────────────

function testChanceNil_alwaysFalse()
    -- Key not set → config returns nil → tonumber(nil) → 0
    mock_engine._set("triggers/missing/chance", nil)
    for _ = 1, 50 do
        luaunit.assertFalse(chance.check("triggers/missing/chance"))
    end
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Dynamic MCM reads (value changes between calls)
-- ──────────────────────────────────────────────────────────────────────────────

function testChanceDynamicRead()
    -- Start at 0 → must fail
    mock_engine._set("triggers/death/chance_player", 0)
    luaunit.assertFalse(chance.check("triggers/death/chance_player"))
    -- Change to 100 → must pass
    mock_engine._set("triggers/death/chance_player", 100)
    luaunit.assertTrue(chance.check("triggers/death/chance_player"))
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Probabilistic: 50% produces both true and false in a large enough sample
-- ──────────────────────────────────────────────────────────────────────────────

function testChance50_producesBothResults()
    mock_engine._set("triggers/idle/chance", 50)
    local seen_true, seen_false = false, false
    for _ = 1, 200 do
        local result = chance.check("triggers/idle/chance")
        if result then seen_true = true else seen_false = true end
        if seen_true and seen_false then break end
    end
    luaunit.assertTrue(seen_true,  "Expected at least one true in 200 rolls at 50%")
    luaunit.assertTrue(seen_false, "Expected at least one false in 200 rolls at 50%")
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Falls back to config_defaults when no override set
-- ──────────────────────────────────────────────────────────────────────────────

function testUsesConfigDefault()
    -- config_defaults has triggers/death/chance_player = 25
    -- With seed 42 from test_bootstrap, we should get a mix
    mock_engine._reset()
    -- Just verify no error is thrown and a boolean comes back
    local result = chance.check("triggers/death/chance_player")
    luaunit.assertEquals(type(result), "boolean")
end

os.exit(luaunit.LuaUnit.run())

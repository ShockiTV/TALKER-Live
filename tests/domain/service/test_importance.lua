package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit    = require('tests.utils.luaunit')
local importance = require('domain.service.importance')

function testNilFlags_returnsFalse()
    luaunit.assertFalse(importance.is_important_person(nil))
end

function testPlayer_returnsTrue()
    luaunit.assertTrue(importance.is_important_person({ is_player = true }))
end

function testCompanion_returnsTrue()
    luaunit.assertTrue(importance.is_important_person({ is_companion = true }))
end

function testUniqueNpc_returnsTrue()
    luaunit.assertTrue(importance.is_important_person({ is_unique = true }))
end

function testMasterRank_returnsTrue()
    luaunit.assertTrue(importance.is_important_person({ rank = "master" }))
end

function testLegendRank_returnsTrue()
    luaunit.assertTrue(importance.is_important_person({ rank = "legend" }))
end

function testMasterRankUpperCase_returnsTrue()
    luaunit.assertTrue(importance.is_important_person({ rank = "Master" }))
end

function testVeteranRank_returnsFalse()
    luaunit.assertFalse(importance.is_important_person({ rank = "veteran" }))
end

function testLowRankNoFlags_returnsFalse()
    luaunit.assertFalse(importance.is_important_person({
        is_player    = false,
        is_companion = false,
        is_unique    = false,
        rank         = "novice",
    }))
end

function testAllFalseFlags_returnsFalse()
    luaunit.assertFalse(importance.is_important_person({
        is_player    = false,
        is_companion = false,
        is_unique    = false,
    }))
end

function testNilRank_doesNotCrash()
    local ok = pcall(importance.is_important_person, { rank = nil })
    luaunit.assertTrue(ok)
end

os.exit(luaunit.LuaUnit.run())

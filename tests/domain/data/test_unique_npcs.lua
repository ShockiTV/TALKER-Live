package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit     = require('tests.utils.luaunit')
local unique_npcs = require('domain.data.unique_npcs')

function testKnownUniqueNpcReturnsTrue()
    luaunit.assertTrue(unique_npcs.is_unique("esc_m_trader"))        -- Sidorovich
    luaunit.assertTrue(unique_npcs.is_unique("bar_dolg_leader"))     -- General Voronin
    luaunit.assertTrue(unique_npcs.is_unique("jup_b220_trapper"))    -- Trapper
    luaunit.assertTrue(unique_npcs.is_unique("actor"))               -- player
end

function testUnknownNpcReturnsFalse()
    luaunit.assertFalse(unique_npcs.is_unique("random_stalker_123"))
    luaunit.assertFalse(unique_npcs.is_unique("generic_bandit_01"))
    luaunit.assertFalse(unique_npcs.is_unique(""))
end

function testNilReturnsFalse()
    luaunit.assertFalse(unique_npcs.is_unique(nil))
end

function testSetDirectAccess()
    -- ids set should also work for direct membership checks
    luaunit.assertTrue(unique_npcs.ids["esc_m_trader"] == true)
    luaunit.assertNil(unique_npcs.ids["not_a_npc"])
end

function testStrelokVariantsPresent()
    luaunit.assertTrue(unique_npcs.is_unique("lost_stalker_strelok"))
    luaunit.assertTrue(unique_npcs.is_unique("stalker_strelok_hb"))
    luaunit.assertTrue(unique_npcs.is_unique("stalker_strelok_oa"))
end

os.exit(luaunit.LuaUnit.run())

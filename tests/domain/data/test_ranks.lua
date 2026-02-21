package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require('tests.utils.luaunit')
local ranks   = require('domain.data.ranks')

-- ──────────────────────────────────────────────────────────────────────────────
-- get_value
-- ──────────────────────────────────────────────────────────────────────────────

function testGetValue_knownRanks()
    luaunit.assertEquals(ranks.get_value("novice"),       0)
    luaunit.assertEquals(ranks.get_value("trainee"),      1)
    luaunit.assertEquals(ranks.get_value("experienced"),  2)
    luaunit.assertEquals(ranks.get_value("professional"), 3)
    luaunit.assertEquals(ranks.get_value("veteran"),      4)
    luaunit.assertEquals(ranks.get_value("expert"),       5)
    luaunit.assertEquals(ranks.get_value("master"),       6)
    luaunit.assertEquals(ranks.get_value("legend"),       7)
end

function testGetValue_unknownRankReturnsMinusOne()
    luaunit.assertEquals(ranks.get_value("unknown_rank"), -1)
    luaunit.assertEquals(ranks.get_value(""),             -1)
    luaunit.assertEquals(ranks.get_value(nil),            -1)
end

-- ──────────────────────────────────────────────────────────────────────────────
-- get_reputation_tier
-- ──────────────────────────────────────────────────────────────────────────────

function testRepTier_nil()
    luaunit.assertEquals(ranks.get_reputation_tier(nil), "Neutral")
end

function testRepTier_nonNumber()
    local result = ranks.get_reputation_tier("not_a_number")
    luaunit.assertEquals(result, "unknown")
end

function testRepTier_positive()
    luaunit.assertEquals(ranks.get_reputation_tier(1500), "Brilliant")
    luaunit.assertEquals(ranks.get_reputation_tier(2000), "Excellent")
    luaunit.assertEquals(ranks.get_reputation_tier(1000), "Great")
    luaunit.assertEquals(ranks.get_reputation_tier(500),  "Good")
end

function testRepTier_neutral()
    luaunit.assertEquals(ranks.get_reputation_tier(0),    "Neutral")
    luaunit.assertEquals(ranks.get_reputation_tier(-499), "Neutral")
end

function testRepTier_negative()
    luaunit.assertEquals(ranks.get_reputation_tier(-1200), "Awful")
    luaunit.assertEquals(ranks.get_reputation_tier(-999),  "Bad")
    luaunit.assertEquals(ranks.get_reputation_tier(-1999), "Dreary")
    luaunit.assertEquals(ranks.get_reputation_tier(-2000), "Terrible")
end

-- ──────────────────────────────────────────────────────────────────────────────
-- format_character_info
-- ──────────────────────────────────────────────────────────────────────────────

function testFormatCharInfo_nil()
    luaunit.assertEquals(ranks.format_character_info(nil), "Unknown")
end

function testFormatCharInfo_monster()
    local char = { name = "Bloodsucker", faction = "Monster" }
    luaunit.assertEquals(ranks.format_character_info(char), "Bloodsucker (Monster)")
end

function testFormatCharInfo_zombied()
    local char = { name = "Zombie", faction = "Zombied" }
    luaunit.assertEquals(ranks.format_character_info(char), "Zombie (Zombied)")
end

function testFormatCharInfo_humanNoDisguise()
    local char = { name = "Wolf", experience = "veteran", faction = "Loner", reputation = "Good" }
    luaunit.assertEquals(ranks.format_character_info(char), "Wolf (veteran Loner, Good rep)")
end

function testFormatCharInfo_humanWithDisguise()
    local char = {
        name = "Spy", experience = "expert", faction = "Freedom",
        reputation = "Neutral", visual_faction = "Duty"
    }
    local result = ranks.format_character_info(char)
    luaunit.assertStrContains(result, "[disguised as Duty]")
    luaunit.assertStrContains(result, "Spy")
    luaunit.assertStrContains(result, "Freedom")
end

os.exit(luaunit.LuaUnit.run())

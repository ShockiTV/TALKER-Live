-- Test faction data builders: build_faction_matrix() and build_player_goodwill()
-- These live in talker_game_queries.script as globals.
-- We simulate them here since .script files can't be required directly.

package.path = package.path .. ";./bin/lua/?.lua"
require("tests.test_bootstrap")
local luaunit = require("tests.utils.luaunit")

-- ============================================================================
-- Replicate the production code inline so we can test it outside the engine.
-- The real code lives in talker_game_queries.script; these are identical copies.
-- ============================================================================

local GAMEPLAY_FACTIONS = {
    "stalker", "dolg", "freedom", "csky", "ecolog", "killer",
    "army", "bandit", "monolith", "renegade", "greh", "isg",
}

local function build_faction_matrix(relation_registry_arg)
    if not relation_registry_arg then return {} end

    local matrix = {}
    for i = 1, #GAMEPLAY_FACTIONS do
        for j = i + 1, #GAMEPLAY_FACTIONS do
            local a, b = GAMEPLAY_FACTIONS[i], GAMEPLAY_FACTIONS[j]
            if a > b then a, b = b, a end
            local key = a .. "_" .. b
            local ok, val = pcall(relation_registry_arg.community_relation, a, b)
            matrix[key] = ok and val or 0
        end
    end
    return matrix
end

local function build_player_goodwill(actor)
    if not actor then return {} end

    local goodwill = {}
    for _, faction in ipairs(GAMEPLAY_FACTIONS) do
        local ok, val = pcall(actor.community_goodwill, actor, faction)
        goodwill[faction] = ok and val or 0
    end
    return goodwill
end

-- ============================================================================
-- Tests: build_faction_matrix
-- ============================================================================

function testMatrix_AllUniquePairs()
    -- Mock relation_registry that returns deterministic values
    local mock_rr = {
        community_relation = function(a, b)
            if a == "dolg" and b == "freedom" or a == "freedom" and b == "dolg" then
                return -1500
            end
            return 0
        end,
    }
    local matrix = build_faction_matrix(mock_rr)

    -- 12 factions → C(12,2) = 66 unique pairs
    local count = 0
    for _ in pairs(matrix) do count = count + 1 end
    luaunit.assertEquals(count, 66)
end

function testMatrix_KeyFormat()
    local mock_rr = {
        community_relation = function() return 100 end,
    }
    local matrix = build_faction_matrix(mock_rr)

    -- Every key should have exactly one underscore
    for key, _ in pairs(matrix) do
        local a, b = key:match("^([^_]+)_(.+)$")
        luaunit.assertNotNil(a, "key should match pattern: " .. key)
        luaunit.assertNotNil(b, "key should match pattern: " .. key)
    end
end

function testMatrix_AlphabeticallySorted()
    local mock_rr = {
        community_relation = function() return 0 end,
    }
    local matrix = build_faction_matrix(mock_rr)

    for key, _ in pairs(matrix) do
        local a, b = key:match("^([^_]+)_(.+)$")
        luaunit.assertTrue(a <= b, "Key not sorted: " .. key)
    end
end

function testMatrix_NoSelfPairs()
    local mock_rr = {
        community_relation = function() return 0 end,
    }
    local matrix = build_faction_matrix(mock_rr)

    for key, _ in pairs(matrix) do
        local a, b = key:match("^([^_]+)_(.+)$")
        luaunit.assertNotEquals(a, b, "Self-pair found: " .. key)
    end
end

function testMatrix_NilRelationRegistry_ReturnsEmpty()
    local matrix = build_faction_matrix(nil)
    local count = 0
    for _ in pairs(matrix) do count = count + 1 end
    luaunit.assertEquals(count, 0)
end

function testMatrix_SpecificPairValue()
    local mock_rr = {
        community_relation = function(a, b)
            if (a == "dolg" and b == "freedom") or (a == "freedom" and b == "dolg") then
                return -1500
            end
            return 0
        end,
    }
    local matrix = build_faction_matrix(mock_rr)
    luaunit.assertEquals(matrix["dolg_freedom"], -1500)
end

-- ============================================================================
-- Tests: build_player_goodwill
-- ============================================================================

function testGoodwill_AllFactionsPresent()
    local mock_actor = {
        community_goodwill = function(self, faction)
            return 100
        end,
    }
    local goodwill = build_player_goodwill(mock_actor)

    for _, faction in ipairs(GAMEPLAY_FACTIONS) do
        luaunit.assertNotNil(goodwill[faction], "Missing faction: " .. faction)
    end
end

function testGoodwill_ReturnsCorrectValues()
    local mock_actor = {
        community_goodwill = function(self, faction)
            if faction == "dolg" then return 1200 end
            if faction == "bandit" then return -800 end
            return 0
        end,
    }
    local goodwill = build_player_goodwill(mock_actor)

    luaunit.assertEquals(goodwill["dolg"], 1200)
    luaunit.assertEquals(goodwill["bandit"], -800)
    luaunit.assertEquals(goodwill["stalker"], 0)
end

function testGoodwill_NilActor_ReturnsEmpty()
    local goodwill = build_player_goodwill(nil)
    local count = 0
    for _ in pairs(goodwill) do count = count + 1 end
    luaunit.assertEquals(count, 0)
end

function testGoodwill_ErrorInCommunityGoodwill_FallsBackToZero()
    local mock_actor = {
        community_goodwill = function(self, faction)
            if faction == "dolg" then error("engine error") end
            return 500
        end,
    }
    local goodwill = build_player_goodwill(mock_actor)
    luaunit.assertEquals(goodwill["dolg"], 0)
    luaunit.assertEquals(goodwill["stalker"], 500)
end

os.exit(luaunit.LuaUnit.run())

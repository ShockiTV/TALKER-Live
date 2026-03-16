package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local checksum = require("framework.checksum")

local function make_event(overrides)
    local base = {
        type = 42,
        game_time_ms = 123456,
        ts = 999,
        context = {
            actor = { game_id = "1", name = "Wolf" },
            victim = { game_id = "2", name = "Bandit" },
            detail = "near campfire",
        },
        witnesses = {
            { game_id = "3", name = "Fanatic" },
        },
    }
    if overrides then
        for k, v in pairs(overrides) do
            base[k] = v
        end
    end
    return base
end

local function xor32(a, b)
    local x = a % 4294967296
    local y = b % 4294967296
    local result = 0
    local place = 1
    for _ = 1, 32 do
        local xb = x % 2
        local yb = y % 2
        if xb ~= yb then
            result = result + place
        end
        x = (x - xb) / 2
        y = (y - yb) / 2
        place = place * 2
    end
    return result
end

function testEventChecksumDeterministic()
    local event = make_event()
    local first = checksum.event_checksum(event)
    local second = checksum.event_checksum(event)

    luaunit.assertEquals(first, second)
    luaunit.assertEquals(#first, 8)
end

function testEventChecksumExcludesTsAndWitnesses()
    local one = make_event({ ts = 1, witnesses = { { game_id = "7" } } })
    local two = make_event({ ts = 2, witnesses = { { game_id = "9" }, { game_id = "10" } } })

    luaunit.assertEquals(checksum.event_checksum(one), checksum.event_checksum(two))
end

function testEventChecksumDetectsContextMutation()
    local one = make_event()
    local two = make_event()
    two.context.detail = "inside bunker"

    luaunit.assertNotEquals(checksum.event_checksum(one), checksum.event_checksum(two))
end

function testBackgroundChecksumChangesWithMutation()
    local bg_a = {
        backstory = "Veteran",
        traits = { "gruff", "loyal" },
        connections = { { character_id = "2", relation = "friend" } },
    }
    local bg_b = {
        backstory = "Veteran",
        traits = { "gruff", "kind" },
        connections = { { character_id = "2", relation = "friend" } },
    }

    local cs_a = checksum.background_checksum(bg_a)
    local cs_b = checksum.background_checksum(bg_b)

    luaunit.assertEquals(#cs_a, 8)
    luaunit.assertEquals(#cs_b, 8)
    luaunit.assertNotEquals(cs_a, cs_b)
end

function testFallbackConsistencyWithBitPath()
    local event = make_event()

    checksum._set_bit_override(nil)
    local fallback_result = checksum.event_checksum(event)

    local mock_bit = {
        bxor = function(a, b)
            return xor32(a, b)
        end,
    }

    checksum._set_bit_override(mock_bit)
    local bit_path_result = checksum.event_checksum(event)
    checksum._set_bit_override(nil)

    luaunit.assertEquals(fallback_result, bit_path_result)
end

os.exit(luaunit.LuaUnit.run())

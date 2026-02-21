package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit           = require('tests.utils.luaunit')
local world_description = require('interface.world_description')

-- ──────────────────────────────────────────────────────────────────────────────
-- time_of_day
-- ──────────────────────────────────────────────────────────────────────────────

function testTimeOfDay_night_early()
    luaunit.assertEquals(world_description.time_of_day(0),  "night")
    luaunit.assertEquals(world_description.time_of_day(3),  "night")
    luaunit.assertEquals(world_description.time_of_day(5),  "night")
end

function testTimeOfDay_morning()
    luaunit.assertEquals(world_description.time_of_day(6),  "morning")
    luaunit.assertEquals(world_description.time_of_day(8),  "morning")
    luaunit.assertEquals(world_description.time_of_day(9),  "morning")
end

function testTimeOfDay_noon()
    luaunit.assertEquals(world_description.time_of_day(10), "noon")
    luaunit.assertEquals(world_description.time_of_day(12), "noon")
    luaunit.assertEquals(world_description.time_of_day(14), "noon")
end

function testTimeOfDay_evening()
    luaunit.assertEquals(world_description.time_of_day(15), "evening")
    luaunit.assertEquals(world_description.time_of_day(17), "evening")
    luaunit.assertEquals(world_description.time_of_day(19), "evening")
end

function testTimeOfDay_night_late()
    luaunit.assertEquals(world_description.time_of_day(20), "night")
    luaunit.assertEquals(world_description.time_of_day(22), "night")
    luaunit.assertEquals(world_description.time_of_day(23), "night")
end

-- ──────────────────────────────────────────────────────────────────────────────
-- describe_emission
-- ──────────────────────────────────────────────────────────────────────────────

function testDescribeEmission_psyStorm()
    luaunit.assertEquals(world_description.describe_emission(true, false), "ongoing psy storm")
end

function testDescribeEmission_surge()
    luaunit.assertEquals(world_description.describe_emission(false, true), "ongoing emission")
end

function testDescribeEmission_none()
    luaunit.assertEquals(world_description.describe_emission(false, false), "")
end

function testDescribeEmission_bothTrue_psyPriority()
    -- psy_storm check comes first
    luaunit.assertEquals(world_description.describe_emission(true, true), "ongoing psy storm")
end

-- ──────────────────────────────────────────────────────────────────────────────
-- describe_weather
-- ──────────────────────────────────────────────────────────────────────────────

function testDescribeWeather_normalClear()
    luaunit.assertEquals(world_description.describe_weather("clear", ""), "clear")
end

function testDescribeWeather_partly()
    luaunit.assertEquals(world_description.describe_weather("partly", ""), "partially cloudy")
end

function testDescribeWeather_overriddenByEmission()
    luaunit.assertEquals(world_description.describe_weather("clear", "ongoing emission"), "an ongoing emission")
end

function testDescribeWeather_nilEmission()
    luaunit.assertEquals(world_description.describe_weather("rain", nil), "rain")
end

-- ──────────────────────────────────────────────────────────────────────────────
-- describe_shelter
-- ──────────────────────────────────────────────────────────────────────────────

function testDescribeShelter_sheltered()
    luaunit.assertEquals(world_description.describe_shelter(0.5, 0.05), "and sheltering inside")
end

function testDescribeShelter_notSheltered()
    luaunit.assertEquals(world_description.describe_shelter(0.1, 0.5), "")
end

function testDescribeShelter_noRain()
    luaunit.assertEquals(world_description.describe_shelter(0.0, 0.0), "")
end

function testDescribeShelter_lowRainFactor()
    luaunit.assertEquals(world_description.describe_shelter(0.2, 0.05), "")  -- border: > 0.2 required
end

function testDescribeShelter_nilValues()
    luaunit.assertEquals(world_description.describe_shelter(nil, nil), "")
end

-- ──────────────────────────────────────────────────────────────────────────────
-- build_description
-- ──────────────────────────────────────────────────────────────────────────────

function testBuildDescription_full_withLitCampfire()
    local result = world_description.build_description({
        location    = "Rostok",
        time_of_day = "morning",
        weather     = "partially cloudy",
        shelter     = "",
        campfire    = "lit",
    })
    luaunit.assertEquals(result,
        "In Rostok at morning during partially cloudy weather, next to a lit campfire.")
end

function testBuildDescription_noCampfire()
    local result = world_description.build_description({
        location    = "Cordon",
        time_of_day = "night",
        weather     = "rain",
        shelter     = "",
        campfire    = nil,
    })
    luaunit.assertEquals(result, "In Cordon at night during rain weather.")
end

function testBuildDescription_withShelter()
    local result = world_description.build_description({
        location    = "Army Warehouses",
        time_of_day = "evening",
        weather     = "rain",
        shelter     = "and sheltering inside",
        campfire    = nil,
    })
    luaunit.assertEquals(result, "In Army Warehouses at evening and sheltering inside during rain weather.")
end

function testBuildDescription_unlitCampfire()
    local result = world_description.build_description({
        location    = "Yantar",
        time_of_day = "noon",
        weather     = "clear",
        shelter     = "",
        campfire    = "unlit",
    })
    luaunit.assertEquals(result, "In Yantar at noon during clear weather, next to an unlit campfire.")
end

function testBuildDescription_locationDotsReplacedWithCommas()
    local result = world_description.build_description({
        location    = "Rostok. 100 Rads Bar",
        time_of_day = "evening",
        weather     = "clear",
        shelter     = "",
        campfire    = nil,
    })
    luaunit.assertStrContains(result, "Rostok, 100 Rads Bar")
    luaunit.assertFalse(string.find(result, "Rostok%.") ~= nil)
end

os.exit(luaunit.LuaUnit.run())

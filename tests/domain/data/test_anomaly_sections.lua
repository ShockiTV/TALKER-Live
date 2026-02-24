package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit         = require('tests.utils.luaunit')
local anomaly_sections = require('domain.data.anomaly_sections')

-- is_anomaly: known sections

function testKnownAnomalySectionReturnsTrue()
    luaunit.assertTrue(anomaly_sections.is_anomaly("zone_buzz_weak"))
    luaunit.assertTrue(anomaly_sections.is_anomaly("zone_vortex"))
    luaunit.assertTrue(anomaly_sections.is_anomaly("zone_mine_electric_strong"))
    luaunit.assertTrue(anomaly_sections.is_anomaly("zone_field_radioactive_average"))
    luaunit.assertTrue(anomaly_sections.is_anomaly("zone_mosquito_bald_average"))
end

function testAllSectionsRecognised()
    -- Every entry in the raw table must round-trip through is_anomaly
    for section, _ in pairs(anomaly_sections.sections) do
        luaunit.assertTrue(
            anomaly_sections.is_anomaly(section),
            "Expected is_anomaly to return true for: " .. section
        )
    end
end

-- is_anomaly: unknown / invalid inputs

function testUnknownSectionReturnsFalse()
    luaunit.assertFalse(anomaly_sections.is_anomaly("stalker_bandit_01"))
    luaunit.assertFalse(anomaly_sections.is_anomaly("m_bloodsucker"))
    luaunit.assertFalse(anomaly_sections.is_anomaly(""))
end

function testNilReturnsFalse()
    luaunit.assertFalse(anomaly_sections.is_anomaly(nil))
end

-- describe: known sections

function testDescribeKnownSection()
    local name = anomaly_sections.describe("zone_vortex")
    luaunit.assertNotNil(name)
    luaunit.assertIsString(name)
    -- Should mention "Vortex"
    luaunit.assertStrContains(name, "Vortex")
end

function testDescribeAnomolySectionFieldRadioactive()
    local name = anomaly_sections.describe("zone_field_radioactive_average")
    luaunit.assertNotNil(name)
    luaunit.assertStrContains(name, "radioactive")
end

function testDescribeMosquitoBaldAverage()
    local name = anomaly_sections.describe("zone_mosquito_bald_average")
    luaunit.assertNotNil(name)
    luaunit.assertStrContains(name, "Space")
end

-- describe: unknown / nil

function testDescribeUnknownSectionReturnsNil()
    luaunit.assertNil(anomaly_sections.describe("not_a_zone"))
    luaunit.assertNil(anomaly_sections.describe("stalker_bandit_01"))
end

function testDescribeNilReturnsNil()
    luaunit.assertNil(anomaly_sections.describe(nil))
end

-- ids Set direct access

function testIdsSetDirectAccess()
    luaunit.assertTrue(anomaly_sections.ids["zone_buzz_strong"] == true)
    luaunit.assertNil(anomaly_sections.ids["not_a_zone"])
end

-- Consistency: every key in sections has an entry in ids

function testSectionsAndIdsConsistent()
    for section, _ in pairs(anomaly_sections.sections) do
        luaunit.assertTrue(
            anomaly_sections.ids[section] == true,
            "ids Set missing entry for: " .. section
        )
    end
end

os.exit(luaunit.LuaUnit.run())

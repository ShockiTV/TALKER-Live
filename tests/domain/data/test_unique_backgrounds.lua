-- tests/domain/data/test_unique_backgrounds.lua
-- Tests for unique_backgrounds.lua static data file
-- Tasks 3.1 (structure) and 3.2 (connection validation)
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit            = require('tests.utils.luaunit')
local unique_backgrounds = require('domain.data.unique_backgrounds')
local unique_npcs        = require('domain.data.unique_npcs')

------------------------------------------------------------
-- 3.1 Structure validation
------------------------------------------------------------

function testDataTableExists()
    luaunit.assertNotNil(unique_backgrounds.data)
    luaunit.assertEquals(type(unique_backgrounds.data), "table")
end

function testDataTableNotEmpty()
    local count = 0
    for _ in pairs(unique_backgrounds.data) do
        count = count + 1
    end
    luaunit.assertTrue(count > 100, "Expected at least 100 entries, got " .. count)
end

function testEveryEntryHasBackstoryString()
    for tech_name, entry in pairs(unique_backgrounds.data) do
        luaunit.assertNotNil(entry.backstory, tech_name .. " missing backstory")
        luaunit.assertEquals(type(entry.backstory), "string", tech_name .. " backstory not a string")
        luaunit.assertTrue(#entry.backstory > 50, tech_name .. " backstory too short: " .. #entry.backstory)
    end
end

function testEveryEntryHasTraitsTable()
    for tech_name, entry in pairs(unique_backgrounds.data) do
        luaunit.assertNotNil(entry.traits, tech_name .. " missing traits")
        luaunit.assertEquals(type(entry.traits), "table", tech_name .. " traits not a table")
        luaunit.assertTrue(#entry.traits >= 3, tech_name .. " has fewer than 3 traits: " .. #entry.traits)
        luaunit.assertTrue(#entry.traits <= 6, tech_name .. " has more than 6 traits: " .. #entry.traits)
    end
end

function testTraitsAreStrings()
    for tech_name, entry in pairs(unique_backgrounds.data) do
        for i, trait in ipairs(entry.traits) do
            luaunit.assertEquals(type(trait), "string",
                tech_name .. " trait #" .. i .. " is not a string")
        end
    end
end

function testEveryEntryHasConnectionsTable()
    for tech_name, entry in pairs(unique_backgrounds.data) do
        luaunit.assertNotNil(entry.connections, tech_name .. " missing connections")
        luaunit.assertEquals(type(entry.connections), "table", tech_name .. " connections not a table")
    end
end

function testConnectionsStructure()
    for tech_name, entry in pairs(unique_backgrounds.data) do
        for i, conn in ipairs(entry.connections) do
            local prefix = tech_name .. " connection #" .. i
            luaunit.assertNotNil(conn.name, prefix .. " missing name")
            luaunit.assertEquals(type(conn.name), "string", prefix .. " name not a string")
            luaunit.assertNotNil(conn.id, prefix .. " missing id")
            luaunit.assertEquals(type(conn.id), "string", prefix .. " id not a string")
            luaunit.assertNotNil(conn.relationship, prefix .. " missing relationship")
            luaunit.assertEquals(type(conn.relationship), "string", prefix .. " relationship not a string")
        end
    end
end

function testActorNotInData()
    luaunit.assertNil(unique_backgrounds.data["actor"], "actor should not be in unique_backgrounds.data")
end

------------------------------------------------------------
-- 3.2 Connection id cross-references valid tech_names
------------------------------------------------------------

function testAllConnectionIdsAreValidTechNames()
    local invalid = {}
    for tech_name, entry in pairs(unique_backgrounds.data) do
        for _, conn in ipairs(entry.connections) do
            if not unique_npcs.is_unique(conn.id) then
                table.insert(invalid, tech_name .. " -> " .. conn.id .. " (" .. conn.name .. ")")
            end
        end
    end
    if #invalid > 0 then
        luaunit.fail("Connection ids not found in unique_npcs:\n  " .. table.concat(invalid, "\n  "))
    end
end

function testSharedVariantsHaveSameBackstory()
    -- Sidorovich, Strelok, Rogue, etc. share entries across tech_name variants
    local data = unique_backgrounds.data
    local variants = {
        {"esc_m_trader", "esc_m_trader_hb", "esc_m_trader_oa"},
        {"lost_stalker_strelok", "stalker_strelok_hb", "stalker_strelok_oa"},
    }
    for _, group in ipairs(variants) do
        local base = data[group[1]]
        if base then
            for i = 2, #group do
                local alt = data[group[i]]
                if alt then
                    luaunit.assertEquals(base.backstory, alt.backstory,
                        group[1] .. " and " .. group[i] .. " should share the same backstory")
                end
            end
        end
    end
end

os.exit(luaunit.LuaUnit.run())

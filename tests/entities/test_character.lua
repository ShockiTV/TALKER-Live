-- Requires
package.path = package.path .. ';./bin/lua/?.lua'
require("tests.test_bootstrap")

local luaunit = require('tests.utils.luaunit')
local assert_or_record = require("tests.utils.assert_or_record")

local Character = require('domain.model.character')

-- Test Character creation
function testCharacterCreation()
    local char = Character.new("1", "John Doe", "Veteran", "Warrior")
    luaunit.assertEquals(char.game_id, "1")
    luaunit.assertEquals(char.name, "John Doe")
    luaunit.assertEquals(char.experience, "Veteran")
    luaunit.assertEquals(char.faction, "Warrior")
end

-- Test Character description method with dynamic personality incorporation
function testCharacterDescription()
    local char = Character.new(1, "John Doe", "Veteran", "Warrior")

    -- Get the description from the character object
    local description = Character.describe(char)

    -- Description format: "John Doe, a Veteran rank member of the Warrior faction who is <personality>"
    luaunit.assertStrContains(description, "John Doe")
    luaunit.assertStrContains(description, "Veteran")
    luaunit.assertStrContains(description, "Warrior")
end

-- Run tests
os.exit(luaunit.LuaUnit.run())

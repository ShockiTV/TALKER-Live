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

-- Run tests
os.exit(luaunit.LuaUnit.run())

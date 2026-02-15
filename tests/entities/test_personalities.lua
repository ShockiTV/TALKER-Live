-- Import required modules
local luaunit = require('tests.utils.luaunit')

-- Mock STALKER's ini_file function before loading personalities module
-- This simulates reading from personalities.ltx
local mock_ini_data = {
    generic = { ids = "1,2,3,4,5" },
    bandit = { ids = "1,2,3" },
    ecolog = { ids = "1,2" },
}

local function create_mock_ini()
    return {
        section_exist = function(self, section)
            return mock_ini_data[section] ~= nil
        end,
        r_string_ex = function(self, section, key)
            local sect = mock_ini_data[section]
            if sect then return sect[key] end
            return nil
        end,
    }
end

-- Set global ini_file before personalities module loads
ini_file = function(path)
    return create_mock_ini()
end

-- Now import the personality module (after global is set)
local M = require('domain.repo.personalities')

local mock_characters = require('tests.mocks.mock_characters')

-- Test cases
function testGetPersonality()
    -- Setup: Assume a character with a pre-assigned personality
    local character = mock_characters[001]
    -- Test: Retrieve the personality
    local result = M.get_personality(character)
    local result2 = M.get_personality(character)
    luaunit.assertEquals(result, result2)
end

function testGetPersonalityReturnsIdFormat()
    -- Clear cache first
    M.clear()
    -- Get personality for a new character
    local character = mock_characters[002]
    local result = M.get_personality(character)
    -- Should be in faction.number format
    luaunit.assertStrContains(result, ".")
end

-- Run tests
os.exit(luaunit.run())
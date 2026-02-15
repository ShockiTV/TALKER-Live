-- Import required modules
local luaunit = require('tests.utils.luaunit')

-- Mock STALKER's ini_file function before loading backstories module
-- This simulates reading from backstories.ltx
local mock_ini_data = {
    unique = { ids = "esc_m_trader,esc_2_12_stalker_wolf,devushka" },
    generic = { ids = "1,2,3,4,5" },
    bandit = { ids = "1,2,3" },
    duty = { ids = "1,2" },
    freedom = { ids = "1,2,3" },
    army = { ids = "1,2" },
    mercenary = { ids = "1,2" },
    clearsky = { ids = "1,2" },
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

-- Set global ini_file before backstories module loads
ini_file = function(path)
    return create_mock_ini()
end

-- Now import the backstories module (after global is set)
local M = require('domain.repo.backstories')

local mock_characters = require('tests.mocks.mock_characters')

-- Test cases
function testGetBackstory()
    -- Setup: Clear cache first
    M.clear()
    -- Get backstory for a character
    local character = mock_characters[001]
    local result = M.get_backstory(character)
    -- Getting again should return same value (cached)
    local result2 = M.get_backstory(character)
    luaunit.assertEquals(result, result2)
end

function testGetBackstoryReturnsIdFormat()
    -- Clear cache first
    M.clear()
    -- Get backstory for a new character
    local character = mock_characters[002]
    local result = M.get_backstory(character)
    -- Should be in faction.number format
    luaunit.assertStrContains(result, ".")
end

function testGetBackstoryPlayerReturnsEmpty()
    -- Clear cache first
    M.clear()
    -- Create player character (game_id = 0)
    local player = { game_id = 0, faction = "stalker" }
    local result = M.get_backstory(player)
    luaunit.assertEquals(result, "")
end

function testClearResetsCache()
    -- Get backstory to populate cache
    local character = mock_characters[001]
    M.get_backstory(character)
    -- Clear cache
    M.clear()
    -- Check save_data is empty
    local save_data = M.get_save_data()
    local count = 0
    for _ in pairs(save_data) do count = count + 1 end
    luaunit.assertEquals(count, 0)
end

function testGetSaveData()
    -- Clear and populate
    M.clear()
    local character = mock_characters[001]
    M.get_backstory(character)
    -- Get save data
    local save_data = M.get_save_data()
    luaunit.assertNotNil(save_data[character.game_id])
end

function testLoadSaveDataMigration()
    -- Clear first
    M.clear()
    -- Create old-format save data (full text, > 50 chars)
    local old_save_data = {
        [123] = "A long backstory text that is definitely more than fifty characters to trigger migration."
    }
    -- Load should detect migration and clear
    M.load_save_data(old_save_data)
    local result = M.get_save_data()
    -- Old data should be cleared due to migration
    luaunit.assertNil(result[123])
end

function testLoadSaveDataNewFormat()
    -- Clear first
    M.clear()
    -- Create new-format save data (short IDs)
    local new_save_data = {
        [123] = "generic.5",
        [456] = "bandit.2"
    }
    -- Load should preserve new format
    M.load_save_data(new_save_data)
    local result = M.get_save_data()
    luaunit.assertEquals(result[123], "generic.5")
    luaunit.assertEquals(result[456], "bandit.2")
end

-- Run tests
os.exit(luaunit.run())

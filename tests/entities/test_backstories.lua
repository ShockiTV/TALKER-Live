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
    -- Check save_data.backstories is empty
    local save_data = M.get_save_data()
    local count = 0
    for _ in pairs(save_data.backstories) do count = count + 1 end
    luaunit.assertEquals(count, 0)
end

function testGetSaveData()
    -- Clear and populate
    M.clear()
    local character = mock_characters[001]
    M.get_backstory(character)
    -- Get save data
    local save_data = M.get_save_data()
    luaunit.assertNotNil(save_data.backstories_version)
    luaunit.assertEquals(save_data.backstories_version, "2")
    luaunit.assertNotNil(save_data.backstories[character.game_id])
end

-- ============================================================================
-- Backstories Store Versioning Tests
-- ============================================================================

-- Test get_save_data() returns versioned structure
function testGetSaveDataReturnsVersionedStructure()
    M.clear()
    local character = mock_characters[001]
    M.get_backstory(character)
    
    local save_data = M.get_save_data()
    
    luaunit.assertNotNil(save_data.backstories_version)
    luaunit.assertEquals(save_data.backstories_version, "2")
    luaunit.assertNotNil(save_data.backstories)
    luaunit.assertNotNil(save_data.backstories[character.game_id])
end

-- Test load_save_data() with versioned data
function testLoadSaveDataWithVersionedData()
    M.clear()
    
    local save_data = {
        backstories_version = "2",
        backstories = {
            [123] = "generic.5",
            [456] = "bandit.2",
        }
    }
    
    M.load_save_data(save_data)
    
    local result = M.get_save_data()
    luaunit.assertEquals(result.backstories[123], "generic.5")
    luaunit.assertEquals(result.backstories[456], "bandit.2")
end

-- Test load_save_data() with legacy data (no version) clears store
function testLoadSaveDataWithLegacyDataClearsStore()
    M.clear()
    
    -- Legacy format: just the backstories map, no version field
    local legacy_data = {
        [123] = "generic.5",
        [456] = "bandit.2",
    }
    
    M.load_save_data(legacy_data)
    
    local result = M.get_save_data()
    -- Legacy data should result in empty store (cleared)
    luaunit.assertNil(result.backstories[123])
    luaunit.assertNil(result.backstories[456])
end

-- Test load_save_data() with nil data
function testLoadSaveDataWithNilData()
    M.clear()
    -- Pre-populate
    local character = mock_characters[001]
    M.get_backstory(character)
    
    M.load_save_data(nil)
    
    local result = M.get_save_data()
    luaunit.assertNil(result.backstories[character.game_id], "Nil data should result in empty store")
end

-- Test load_save_data() with unknown version clears store
function testLoadSaveDataWithUnknownVersionClearsStore()
    M.clear()
    
    local unknown_version_data = {
        backstories_version = "999",
        backstories = {
            [123] = "generic.5",
        }
    }
    
    M.load_save_data(unknown_version_data)
    
    local result = M.get_save_data()
    luaunit.assertNil(result.backstories[123], "Unknown version should result in empty store")
end

-- Run tests
os.exit(luaunit.run())

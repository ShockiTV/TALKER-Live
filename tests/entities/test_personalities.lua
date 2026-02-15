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

-- ============================================================================
-- Personalities Store Versioning Tests
-- ============================================================================

-- Test get_save_data() returns versioned structure
function testGetSaveDataReturnsVersionedStructure()
    M.clear()
    local character = mock_characters[001]
    M.get_personality(character)
    
    local save_data = M.get_save_data()
    
    luaunit.assertNotNil(save_data.personalities_version)
    luaunit.assertEquals(save_data.personalities_version, "2")
    luaunit.assertNotNil(save_data.personalities)
    luaunit.assertNotNil(save_data.personalities[character.game_id])
end

-- Test load_save_data() with versioned data
function testLoadSaveDataWithVersionedData()
    M.clear()
    
    local save_data = {
        personalities_version = "2",
        personalities = {
            [123] = "generic.5",
            [456] = "bandit.2",
        }
    }
    
    M.load_save_data(save_data)
    
    local result = M.get_save_data()
    luaunit.assertEquals(result.personalities[123], "generic.5")
    luaunit.assertEquals(result.personalities[456], "bandit.2")
end

-- Test load_save_data() with legacy data (no version) clears store
function testLoadSaveDataWithLegacyDataClearsStore()
    M.clear()
    
    -- Legacy format: just the personalities map, no version field
    local legacy_data = {
        [123] = "generic.5",
        [456] = "bandit.2",
    }
    
    M.load_save_data(legacy_data)
    
    local result = M.get_save_data()
    -- Legacy data should result in empty store (cleared)
    luaunit.assertNil(result.personalities[123])
    luaunit.assertNil(result.personalities[456])
end

-- Test load_save_data() with nil data
function testLoadSaveDataWithNilData()
    M.clear()
    -- Pre-populate
    local character = mock_characters[001]
    M.get_personality(character)
    
    M.load_save_data(nil)
    
    local result = M.get_save_data()
    luaunit.assertNil(result.personalities[character.game_id], "Nil data should result in empty store")
end

-- Test load_save_data() with unknown version clears store
function testLoadSaveDataWithUnknownVersionClearsStore()
    M.clear()
    
    local unknown_version_data = {
        personalities_version = "999",
        personalities = {
            [123] = "generic.5",
        }
    }
    
    M.load_save_data(unknown_version_data)
    
    local result = M.get_save_data()
    luaunit.assertNil(result.personalities[123], "Unknown version should result in empty store")
end

-- Run tests
os.exit(luaunit.run())
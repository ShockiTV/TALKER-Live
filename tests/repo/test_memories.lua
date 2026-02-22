-- Adjust the package path
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

-- Require LuaUnit, memories module, and event_store module
local luaunit = require('tests.utils.luaunit')
local event_store = require('domain.repo.event_store')
local memory_store = require('domain.repo.memory_store')

-- Helper function to create mock events with a 'was_witnessed_by' method
local function create_mock_event(game_time_ms, witnesses)
    return {
        description = "Mock Event",
        objects = {},
        game_time_ms = game_time_ms,
        world_context = "Somewhere",
        witnesses = witnesses or {},
        source_event = nil
    }
end

-- Setup function to reset the state before each test
function setup()
    event_store:clear()
    memory_store:clear()
end

-- Test adding/updating a narrative for a character and retrieving it
function testAddMemoryForCharacter()
    memory_store:clear()
    local character_id = 'char_1'
    local content = 'This is a memory content'

    memory_store:update_narrative(character_id, content, 0)

    local narrative = memory_store:get_narrative(character_id)

    luaunit.assertNotNil(narrative)
    luaunit.assertEquals(narrative.narrative, content)
    luaunit.assertEquals(narrative.last_update_time_ms, 0)
end

-- Test updating a narrative multiple times (last write wins)
function testGetCompressedMemories()
    memory_store:clear()
    local character_id = 'char_1'

    memory_store:update_narrative(character_id, 'Memory 1', 0)
    memory_store:update_narrative(character_id, 'Memory 2', 1)
    memory_store:update_narrative(character_id, 'Memory 3', 2)

    local narrative = memory_store:get_narrative(character_id)
    luaunit.assertNotNil(narrative)
    luaunit.assertEquals(narrative.narrative, 'Memory 3')
    luaunit.assertEquals(narrative.last_update_time_ms, 2)
end


-- ============================================================================
-- Memory Store Versioning Tests
-- ============================================================================

-- Test get_save_data() returns versioned structure
function testGetSaveDataReturnsVersionedStructure()
    memory_store:clear()
    memory_store:update_narrative('char_1', 'Test narrative', 1000)
    
    local save_data = memory_store:get_save_data()
    
    luaunit.assertNotNil(save_data.memories_version)
    luaunit.assertEquals(save_data.memories_version, "2")
    luaunit.assertNotNil(save_data.memories)
    luaunit.assertNotNil(save_data.memories['char_1'])
    luaunit.assertEquals(save_data.memories['char_1'].narrative, 'Test narrative')
end

-- Test load_save_data() with versioned data
function testLoadSaveDataWithVersionedData()
    memory_store:clear()
    
    local save_data = {
        memories_version = "2",
        memories = {
            ['char_1'] = { narrative = 'Test narrative', last_update_time_ms = 1000 },
            ['char_2'] = { narrative = 'Another narrative', last_update_time_ms = 2000 },
        }
    }
    
    memory_store:load_save_data(save_data)
    
    local mem1 = memory_store:get_narrative('char_1')
    local mem2 = memory_store:get_narrative('char_2')
    luaunit.assertNotNil(mem1)
    luaunit.assertEquals(mem1.narrative, 'Test narrative')
    luaunit.assertNotNil(mem2)
    luaunit.assertEquals(mem2.narrative, 'Another narrative')
end

-- Test load_save_data() with legacy data (object format, no version)
function testLoadSaveDataWithLegacyObjectFormat()
    memory_store:clear()
    
    -- Legacy format: just the memories map, no version field
    local legacy_data = {
        ['char_1'] = { narrative = 'Legacy narrative', last_update_time_ms = 1000 },
    }
    
    memory_store:load_save_data(legacy_data)
    
    local mem1 = memory_store:get_narrative('char_1')
    luaunit.assertNotNil(mem1)
    luaunit.assertEquals(mem1.narrative, 'Legacy narrative')
end

-- Test load_save_data() with legacy data (old list format)
function testLoadSaveDataWithLegacyListFormat()
    memory_store:clear()
    
    -- Old format: list of events per character
    local old_list_data = {
        ['char_1'] = {
            { content = 'Memory 1', game_time_ms = 500 },
            { content = 'Memory 2', game_time_ms = 1000 },
        },
    }
    
    memory_store:load_save_data(old_list_data)
    
    local mem1 = memory_store:get_narrative('char_1')
    luaunit.assertNotNil(mem1)
    -- Migration concatenates content
    luaunit.assertStrContains(mem1.narrative, 'Memory 1')
    luaunit.assertStrContains(mem1.narrative, 'Memory 2')
    luaunit.assertEquals(mem1.last_update_time_ms, 1000)
end

-- Test load_save_data() with nil data
function testLoadSaveDataWithNilData()
    memory_store:clear()
    -- Pre-populate
    memory_store:update_narrative('char_1', 'Existing narrative', 1000)
    
    memory_store:load_save_data(nil)
    
    local mem1 = memory_store:get_narrative('char_1')
    luaunit.assertNil(mem1, "Nil data should result in empty store")
end

-- Test load_save_data() with unknown version clears store
function testLoadSaveDataWithUnknownVersionClearsStore()
    memory_store:clear()
    
    local unknown_version_data = {
        memories_version = "999",
        memories = {
            ['char_1'] = { narrative = 'Should not load', last_update_time_ms = 1000 },
        }
    }
    
    memory_store:load_save_data(unknown_version_data)
    
    local mem1 = memory_store:get_narrative('char_1')
    luaunit.assertNil(mem1, "Unknown version should result in empty store")
end


-- Run the tests
os.exit(luaunit.LuaUnit.run())
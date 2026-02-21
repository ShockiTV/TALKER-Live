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

-- Test getting memories for a character based on witnessed events
function testGetMemoriesForCharacterId()
    event_store:clear()
    memory_store:clear()
    -- Create events with witnesses
    local event1 = create_mock_event(1000, {{game_id = 'char_1'}, {game_id = 'char_2'}})
    local event2 = create_mock_event(2000, {{game_id = 'char_2'}})
    local event3 = create_mock_event(3000, {{game_id = 'char_1'}, {game_id = 'char_3'}})

    event_store:store_event(event1)
    event_store:store_event(event2)
    event_store:store_event(event3)

    local memories_char1 = memory_store:get_memories('char_1')

    luaunit.assertEquals(#memories_char1, 2)
    luaunit.assertEquals(memories_char1[1], event1)
    luaunit.assertEquals(memories_char1[2], event3)

    local memories_char2 = memory_store:get_memories('char_2')
    luaunit.assertEquals(#memories_char2, 2)
    luaunit.assertEquals(memories_char2[1], event1)
    luaunit.assertEquals(memories_char2[2], event2)

    local memories_char3 = memory_store:get_memories('char_3')
    luaunit.assertEquals(#memories_char3, 1)
    luaunit.assertEquals(memories_char3[1], event3)

    local memories_char4 = memory_store:get_memories('char_4')
    luaunit.assertEquals(#memories_char4, 0)
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

-- Test getting new events since last narrative update
function testGetUncompressedMemoriesSinceLastCompression()
    memory_store:clear()
    event_store:clear()
    local character_1 = {game_id = 'char_1'}

    -- Set narrative with last update at time 1600
    memory_store:update_narrative(character_1.game_id, 'Compressed summary', 1600)

    -- Store events: two before and two after last update time
    local event1 = create_mock_event(1000, {character_1})
    local event2 = create_mock_event(1600, {character_1})
    local event3 = create_mock_event(2500, {character_1})
    local event4 = create_mock_event(3000, {character_1})

    event_store:store_event(event1)
    event_store:store_event(event2)
    event_store:store_event(event3)
    event_store:store_event(event4)

    local new_events = memory_store:get_new_events(character_1.game_id)

    -- Only events after last_update_time_ms=1600 should be included
    luaunit.assertEquals(#new_events, 2)
    luaunit.assertEquals(new_events[1], event3, 'first event wrong')
    luaunit.assertEquals(new_events[2], event4, 'second event wrong')
end

-- Test getting full memory context for dialogue generation
function testGetAllMemories()
    print("testing get all memories")
    memory_store:clear()
    event_store:clear()
    local character_1 = {game_id = 'char_1'}

    -- Set up narrative with last update at time 1600
    memory_store:update_narrative(character_1.game_id, 'Compressed narrative', 1600)

    -- Store events; only those after 1600 should be in new_events
    local event1 = create_mock_event(1000, {character_1})
    local event2 = create_mock_event(1600, {character_1})
    local event3 = create_mock_event(2500, {character_1})
    local event4 = create_mock_event(3000, {character_1})

    event_store:store_event(event1)
    event_store:store_event(event2)
    event_store:store_event(event3)
    event_store:store_event(event4)

    local context = memory_store:get_memory_context(character_1.game_id)
    luaunit.assertNotNil(context)
    luaunit.assertEquals(context.narrative, 'Compressed narrative')
    luaunit.assertEquals(context.last_update_time_ms, 1600)
    luaunit.assertEquals(#context.new_events, 2)
    luaunit.assertEquals(context.new_events[1], event3, 'first new event wrong')
    luaunit.assertEquals(context.new_events[2], event4, 'second new event wrong')
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
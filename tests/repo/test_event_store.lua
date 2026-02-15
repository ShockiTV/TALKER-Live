-- Adjust the package path
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'

-- Require LuaUnit and event_store module
local luaunit = require('tests.utils.luaunit')
local event_store = require('domain.repo.event_store')
local Event = require('domain.model.event')
local EventType = require('domain.model.event_types')

-- Helper function to create mock typed events
local function create_mock_event(game_time_ms, source_event)
    local context = { action_description = "Mock Event" }
    local witnesses = {}
    local flags = nil
    if source_event then
        flags = { source_event = source_event }
    end
    return Event.create(EventType.ACTION, context, game_time_ms, "Somewhere", witnesses, flags)
end

-- Helper function to store a sequence of events
local function store_mock_events(es, count, start_time, interval)
    for i = 1, count do
        es:store_event(create_mock_event(start_time + (i - 1) * interval, nil))
    end
end

-- Test storing a single event
function testStoreSingleEvent()
    event_store:clear()
    local event = create_mock_event(1000, nil)
    event_store:store_event(event)
    local retrieved_event = event_store:get_event(1000)

    luaunit.assertNotNil(retrieved_event)
    luaunit.assertEquals(retrieved_event.type, EventType.ACTION)
    luaunit.assertEquals(retrieved_event.game_time_ms, 1000)
end

-- Test storing multiple events with the same game_time
function testStoreMultipleEventsSameTime()
    event_store:clear()
    for i = 1, 3 do
        event_store:store_event(create_mock_event(1000, nil))
    end

    for i = 0, 2 do
        local retrieved_event = event_store:get_event(1000 + i)
        luaunit.assertNotNil(retrieved_event)
        luaunit.assertEquals(retrieved_event.game_time_ms, 1000 + i)
    end
end

-- Test retrieving an event that does not exist
function testRetrieveNonExistentEvent()
    event_store:clear()
    luaunit.assertNil(event_store:get_event(9999))
end

-- Test that the event source_event reference is preserved correctly
function testSourceEventPreservation()
    event_store:clear()
    local source_event = create_mock_event(500, nil)
    event_store:store_event(source_event)
    local child_event = create_mock_event(1000, source_event)
    event_store:store_event(child_event)

    local retrieved_event = event_store:get_event(1000)
    luaunit.assertNotNil(retrieved_event)
    luaunit.assertNotNil(retrieved_event.flags)
    luaunit.assertNotNil(retrieved_event.flags.source_event)
    luaunit.assertEquals(retrieved_event.flags.source_event.game_time_ms, 500)
end

-- Test getting recent events
function testGetEventsSince()
    event_store:clear()
    store_mock_events(event_store, 5, 1000, 1000)

    local recent_events = event_store:get_events_since(2000)

    luaunit.assertEquals(#recent_events, 3)
    luaunit.assertEquals(recent_events[1].game_time_ms, 3000)
    luaunit.assertEquals(recent_events[2].game_time_ms, 4000)
    luaunit.assertEquals(recent_events[3].game_time_ms, 5000)
end

-- Test counting recent events
function testGetCountEventSince()
    event_store:clear()
    store_mock_events(event_store, 5, 1000, 1000)

    local recent_events_count = event_store:get_count_events_since(3000)

    luaunit.assertEquals(recent_events_count, 2)
end

-- ============================================================================
-- Event Store Versioning Tests
-- ============================================================================

-- Test get_save_data() returns versioned structure
function testGetSaveDataReturnsVersionedStructure()
    event_store:clear()
    store_mock_events(event_store, 2, 1000, 1000)
    
    local save_data = event_store:get_save_data()
    
    luaunit.assertNotNil(save_data.events_version)
    luaunit.assertEquals(save_data.events_version, "2")
    luaunit.assertNotNil(save_data.events)
    luaunit.assertNotNil(save_data.events[1000])
    luaunit.assertNotNil(save_data.events[2000])
end

-- Test load_save_data() with versioned data
function testLoadSaveDataWithVersionedData()
    event_store:clear()
    
    -- Create versioned save data
    local event1 = create_mock_event(1000, nil)
    local event2 = create_mock_event(2000, nil)
    local save_data = {
        events_version = "2",
        events = {
            [1000] = event1,
            [2000] = event2,
        }
    }
    
    event_store:load_save_data(save_data)
    
    local all_events = event_store:get_all_events()
    luaunit.assertEquals(#all_events, 2)
    luaunit.assertEquals(all_events[1].game_time_ms, 1000)
    luaunit.assertEquals(all_events[2].game_time_ms, 2000)
end

-- Test load_save_data() with legacy data (no version) clears store
function testLoadSaveDataWithLegacyDataClearsStore()
    event_store:clear()
    
    -- Create legacy format (just events, no version field)
    local event1 = create_mock_event(1000, nil)
    local legacy_data = {
        [1000] = event1,
    }
    
    event_store:load_save_data(legacy_data)
    
    local all_events = event_store:get_all_events()
    luaunit.assertEquals(#all_events, 0, "Legacy data should result in empty store")
end

-- Test load_save_data() with nil data
function testLoadSaveDataWithNilData()
    event_store:clear()
    -- Pre-populate to ensure it gets cleared
    store_mock_events(event_store, 2, 1000, 1000)
    
    event_store:load_save_data(nil)
    
    local all_events = event_store:get_all_events()
    luaunit.assertEquals(#all_events, 0, "Nil data should result in empty store")
end

-- Test load_save_data() with unknown version clears store
function testLoadSaveDataWithUnknownVersionClearsStore()
    event_store:clear()
    
    -- Create data with unknown version
    local event1 = create_mock_event(1000, nil)
    local unknown_version_data = {
        events_version = "999",  -- Unknown version
        events = {
            [1000] = event1,
        }
    }
    
    event_store:load_save_data(unknown_version_data)
    
    local all_events = event_store:get_all_events()
    luaunit.assertEquals(#all_events, 0, "Unknown version should result in empty store")
end

-- Run the tests
os.exit(luaunit.LuaUnit.run())
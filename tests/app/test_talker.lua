---@diagnostic disable: duplicate-set-field
print(_VERSION)

package.path = package.path .. ';./bin/lua/?.lua'
package.path = package.path .. ';./bin/lua/*/?.lua'

-- Import required modules
local luaunit = require('tests.utils.luaunit')
local mock_situation = require("tests.mocks.mock_situation")
local assert_or_record = require("tests.utils.assert_or_record")
local talker = require('app.talker')
local mock_game_adapter = require('tests.mocks.mock_game_adapter')
talker.set_game_adapter(mock_game_adapter)

local event_store = require('domain.repo.event_store')


-- Test Scenario: Event Registration
-- In Phase 2+, talker.lua only stores events. AI dialogue is handled by Python service.
function Test_EventRegistration()
    print("Test_EventRegistration")

    -- Clear the event store
    event_store:clear()

    -- Simulate the event where a character has been killed
    local events = mock_situation
    talker.register_event(events[1], true)

    -- Retrieve events and verify the event was stored
    local result = event_store:get_events_since(0)
    luaunit.assertEquals(#result, 1, "Expected 1 event to be stored")
    assert_or_record('app', 'Test_EventRegistration', result)
end

-- Test Scenario: Silent Event
function Test_SilentEvent()
    print("Test_SilentEvent")

    -- Clear the event store
    event_store:clear()

    -- Create a silent event
    local silent_event = {
        type = "TEST",
        game_time_ms = 1000,
        witnesses = {},
        flags = { is_silent = true }
    }

    talker.register_event(silent_event, false)

    -- Silent events should still be stored (for memory/history)
    local result = event_store:get_events_since(0)
    luaunit.assertEquals(#result, 1, "Expected silent event to be stored")
end

-- Run the tests
os.exit(luaunit.LuaUnit.run())
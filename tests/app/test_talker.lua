---@diagnostic disable: duplicate-set-field
print(_VERSION)

package.path = package.path .. ';./bin/lua/?.lua'
package.path = package.path .. ';./bin/lua/*/?.lua'
require("tests.test_bootstrap")

-- Import required modules
local luaunit = require('tests.utils.luaunit')
local mock_situation = require("tests.mocks.mock_situation")
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

    -- Verify event structure (not backstory IDs which are randomly assigned)
    local event = result[1]
    luaunit.assertEquals(event.game_time_ms, 100, "Expected game_time_ms = 100")
    luaunit.assertEquals(event.context.actor.name, "Sarik", "Expected actor name")
    luaunit.assertEquals(event.context.actor.faction, "Freedom", "Expected actor faction")
    luaunit.assertEquals(#event.witnesses, 6, "Expected 6 witnesses")
    luaunit.assertEquals(event.flags, {}, "Expected empty flags")
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
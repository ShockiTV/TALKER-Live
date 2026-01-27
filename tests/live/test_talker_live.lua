-- Import required modules
local luaunit = require('tests.utils.luaunit')
-- Import modules
local talker = require('app.talker')
local file_io = require('infra.file_io')
local event_store = require('domain.repo.event_store')
-- Import mocks
local mock_situation = require("tests.mocks.mock_situation")
local mock_game_adapter = require('tests.mocks.mock_game_adapter')
local game_adapter_recorder = require('infra.game_adapter_recorder')

-- Mock dialogue delivery
local mocked = false
local current_test = 'unset'
mock_game_adapter.display_dialogue = function(character_id, dialogue)
    print('mocking display_dialogue')
    file_io.override("tests/live/output/" .. current_test ..'.txt', dialogue .. '\n')
    mocked = true
end
talker.set_game_adapter(mock_game_adapter)

----------------------------------------------------------------------------------------------------------------
-- Situation generator
----------------------------------------------------------------------------------------------------------------
local mock_characters = require('tests.mocks.mock_characters')
local Event = require('domain.model.event')
local EventType = require('domain.model.event_types')

function create_mock_event(description, objects)
    -- Create typed ACTION event for test purposes
    local context = { action_description = description, involved_objects = objects }
    return Event.create(EventType.ACTION, context, 100, "Cordon", mock_characters)
end

----------------------------------------------------------------------------------------------------------------
-- Load up events
-- this module accepts a table of events, stores all but the last, which is registered
----------------------------------------------------------------------------------------------------------------
function load_events(events)
    for i = 1, #events - 1 do
        event_store:store_event(events[i])
    end
    talker.register_event(events[#events], true)
end

----------------------------------------------------------------------------------------------------------------
-- Test Scenario: Kill Event
----------------------------------------------------------------------------------------------------------------
function Test_ScenarioKillLive()
    current_test = 'TestScenarioKillLive'
    -- Simulate the event where a character has been killed
    local events = mock_situation
    load_events(events)
    luaunit.assertEquals(mocked, true)
end

----------------------------------------------------------------------------------------------------------------
-- Test Scenario: Funny Story Event
----------------------------------------------------------------------------------------------------------------
function Test_ScenarioFunnyStoryLive()
    current_test = 'TestScenarioFunnyStoryLive'
    -- Simulate the event where a character tells a funny story
    local funny_story_event = create_mock_event("%s was telling a funny story", {mock_characters[1]})
    local sudden_interruption = create_mock_event("%s spotted a bandit scout", {mock_characters[2]})
    load_events({funny_story_event, sudden_interruption})
    luaunit.assertEquals(mocked, true)
end

----------------------------------------------------------------------------------------------------------------
-- Hello world test so this becomes green even if there are no other tests
----------------------------------------------------------------------------------------------------------------

function TestHelloWorld()
    luaunit.assertEquals(true, true)
end

----------------------------------------------------------------------------------------------------------------
-- Mock talker async
----------------------------------------------------------------------------------------------------------------
talker_game_async = {}
---@diagnostic disable-next-line: duplicate-set-field
talker_game_async.repeat_until_true = function(seconds, func, ...)
    -- wait one second and execute
    os.execute("sleep 2")
    print("Waiting for " .. seconds .. " seconds")
    func(...)
end

-- Run the tests
os.exit(luaunit.LuaUnit.run())
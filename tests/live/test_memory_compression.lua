-- Import required modules
local luaunit = require('tests.utils.luaunit')
local talker = require('app.talker')
local file_io = require('infra.file_io')
local event_store = require('domain.repo.event_store')
local memory_store = require('domain.repo.memory_store')
local json = require('infra.HTTP.json')
local AI_request = require('infra.AI.requests')

-- Import mock utilities
local mock_characters = require('tests.mocks.mock_characters')
local Event = require('domain.model.event')
local EventType = require('domain.model.event_types')
local mock_game_adapter = require('tests.mocks.mock_game_adapter')
local game_adapter_recorder = require('infra.game_adapter_recorder')

-- Setup
-- mock_game_adapter = game_adapter_recorder(mock_game_adapter)
talker.set_game_adapter(mock_game_adapter)

-- Helper functions for mock events
local time = 0
function create_mock_event(description, objects)
    time = time + 1
    -- Create typed ACTION event for test purposes
    local context = { action_description = description, involved_objects = objects }
    return Event.create(EventType.ACTION, context, time, "Cordon", mock_characters)
end

local events = {
    -- 1
    create_mock_event("%s spots a distant anomaly while scouting ahead", {mock_characters[1]}),
    create_mock_event("%s finds a strange reading on the detector", {mock_characters[2]}),
    create_mock_event("The team sets up camp to discuss the finding by %s", {mock_characters[2]}),
    create_mock_event("%s argues for a cautious approach to the anomaly", {mock_characters[3]}),
    create_mock_event("After some debate, %s's plan is adopted", {mock_characters[1]}),
    -- 5
    create_mock_event("Early morning, %s leads the group towards the anomaly", {mock_characters[1]}),
    create_mock_event("The group encounters a patch of irradiated area, %s navigates a safe path", {mock_characters[3]}),
    create_mock_event("%s detects a strong energy signature close by", {mock_characters[2]}),
    create_mock_event("%s uncovers a hidden artifact emitting strange sounds", {mock_characters[1]}),
    create_mock_event("While examining the artifact, %s hears distant howls", {mock_characters[4]}),
    -- 10
    create_mock_event("%s suggests hurrying back due to the howls", {mock_characters[3]}),
    create_mock_event("As they start back, %s spots mutant dogs approaching fast", {mock_characters[4]}),
    create_mock_event("%s fires a warning shot to scare the dogs", {mock_characters[5]}),
    create_mock_event("The dogs attack, %s and %s fight back fiercely", {mock_characters[1], mock_characters[3]}),
    create_mock_event("During the chaos, %s gets severely wounded", {mock_characters[5]}),
    -- 15
    create_mock_event("%s tries to help %s, but the situation worsens", {mock_characters[2], mock_characters[5]}),
    create_mock_event("The group retreats, leaving behind %s who is now beyond help", {mock_characters[5]}),
    create_mock_event("%s mourns the loss but urges the group to move on", {mock_characters[2]}),
    create_mock_event("The artifact is secured by %s, who vows to protect it in memory of %s", {mock_characters[1], mock_characters[5]}),
    create_mock_event("%s leads the remaining team back to the base, wary of further attacks", {mock_characters[3]}), 
    -- 20 
    create_mock_event("%s reports that they see strange lights near the anomaly", {mock_characters[4]}),
    create_mock_event("As the team investigates, %s steps on a hidden tripwire", {mock_characters[2]}),
    create_mock_event("The tripwire activates a hidden mechanism, startling %s", {mock_characters[3]}),
    create_mock_event("While disarming the trap, %s hears footsteps approaching", {mock_characters[1]}),
    create_mock_event("%s signals the group to hide as unknown figures approach", {mock_characters[4]}),
    -- 25
    create_mock_event("A group of bandits confronts the team, demanding their artifact", {mock_characters[1]}),
    create_mock_event("%s tries to negotiate with the bandits", {mock_characters[2]}),
    create_mock_event("Negotiations break down, and %s initiates a firefight", {mock_characters[3]}),
    create_mock_event("During the battle, %s is hit in the arm but continues to fight", {mock_characters[1]}),
    create_mock_event("%s flanks the bandits, turning the tide of the fight", {mock_characters[4]}),
    -- 30
    create_mock_event("The bandits retreat, leaving behind their wounded leader", {mock_characters[5]}),
    create_mock_event("The group interrogates the bandit leader, who reveals a hidden bunker nearby", {mock_characters[2]}),
    create_mock_event("The team decides to explore the bunker, with %s taking the lead", {mock_characters[3]}),
    create_mock_event("%s finds a locked door leading deeper into the bunker", {mock_characters[1]}),
    create_mock_event("%s manages to unlock the door using tools scavenged from the bandits", {mock_characters[4]}),
    -- 35
    create_mock_event("Inside, the team discovers a cache of old scientific equipment", {mock_characters[2]}),
    create_mock_event("%s examines the equipment and determines it was used to study the anomaly", {mock_characters[1]}),
    create_mock_event("While searching further, %s finds an encrypted journal belonging to a long-lost researcher", {mock_characters[3]}),
    create_mock_event("The journal details strange experiments conducted on the anomaly", {mock_characters[2]}),
    create_mock_event("%s proposes deciphering the journal to uncover more about the artifact", {mock_characters[1]})
}

function TestGetCurrentMemories()
    local current_test = 'TestGetCurrentMemories'
    -- insert 10 events into the event store
    for i = 1, 10 do
        event_store:store_event(events[i])
    end
    memory_store:store_compressed_memory(mock_characters[2].game_id, "Memory 1", 5)
    memory_store:store_compressed_memory(mock_characters[2].game_id, "Memory 2", 6)
    local output = memory_store:get_current_memories(mock_characters[2].game_id)
    luaunit.assertEquals(#output, 5)
    -- assert compressed one is first
    luaunit.assertEquals(output[1].content, "Memory 2")
    file_io.override("tests/live/output/" .. current_test ..'.json', json.encode(output))
end

-- Mock compression test
function Test_MemoryCompression()
    local current_test = 'TestMemoryCompression'

    -- For each event, store it and attempt to compress memories
    -- each event will save it's current state to a file
    for i, event in ipairs(events) do
        event_store:store_event(event)
        AI_request.compress_memories(mock_characters[2].game_id, function(speaker_id)
            local all_memories = memory_store:get_current_memories(speaker_id)
            local simpler_memories = {}
            for _, memory in ipairs(all_memories) do
                if memory.witnesses then
                    table.insert(simpler_memories, {
                        description = memory.description,
                        type = 'fresh'
                    })
                else
                    table.insert(simpler_memories, {
                        description = memory.content,
                        type = 'compressed'
                    })
                end
        
            end
            file_io.override("tests/live/output/" .. current_test .. '/' .. i ..'.json', json.encode(simpler_memories) .. '\n')
        end)
    end

    -- assert last 3 events are intact in the all_memories
    local all_memories = memory_store:get_all_memories(mock_characters[2].game_id)
    luaunit.assertEquals(all_memories[#all_memories-2].description, events[#events-2].description)
    luaunit.assertEquals(all_memories[#all_memories-1].description, events[#events-1].description)
    luaunit.assertEquals(all_memories[#all_memories].description, events[#events].description)
end



-- Configure LuaUnit
os.exit(luaunit.LuaUnit.run())
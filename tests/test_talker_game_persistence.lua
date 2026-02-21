package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")
local luaunit = require('tests.utils.luaunit')
local memory_store = require('domain.repo.memory_store')
local event_store = require('domain.repo.event_store')
package.path = package.path .. ';./gamedata/scripts/?.script'
-- Stub get_game_time_ms for the persistence script
talker_game_queries.get_game_time_ms = function() return 0 end
require('talker_game_persistence')

local function save_data()
    -- Initialize with known states for predictability
    event_store:clear()
    memory_store:clear()
    memory_store:update_narrative("character_id", "Memory 1", 5)
    local saved_data = {}
    save_state(saved_data)
    return saved_data
end

function testSaveState()
    local saved_data = save_data()

    luaunit.assertNotNil(saved_data.compressed_memories)
    luaunit.assertNotNil(saved_data.events)
end

function testLoadState()
    local saved_data = save_data()

    -- Empty both repos
    memory_store:clear()
    event_store:clear()

    luaunit.assertNil(memory_store:get_narrative("character_id"))
    luaunit.assertEquals(#event_store:get_all_events(), 0)

    load_state(saved_data)

    local narrative = memory_store:get_narrative("character_id")
    luaunit.assertNotNil(narrative)
    luaunit.assertEquals(narrative.narrative, "Memory 1")
    luaunit.assertEquals(narrative.last_update_time_ms, 5)
end

os.exit(luaunit.LuaUnit.run())
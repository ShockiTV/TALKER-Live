package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua;./gamedata/scripts/?.script'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")

AddScriptCallback = AddScriptCallback or function() end
talker_game_queries = talker_game_queries or {}
talker_game_queries.get_game_time_ms = talker_game_queries.get_game_time_ms or function()
    return 0
end

local published_messages = {}

local mock_bridge = {
    init = function(_url, _opts) end,
    set_on_reconnect = function(_cb) end,
    get_status = function() return "connected" end,
    publish = function(topic, payload)
        published_messages[#published_messages + 1] = { topic = topic, payload = payload }
    end,
    tick = function() end,
    shutdown = function() end,
    on = function() end,
}

package.loaded["infra.bridge.channel"] = mock_bridge

local persistence = require("talker_game_persistence")
talker_game_persistence = persistence

require("talker_ws_integration")

local function reset_state()
    published_messages = {}
end

function testLoadStateGeneratesSessionIdWhenMissing()
    reset_state()

    local save_data = {}
    persistence.load_state(save_data)

    local session_id = persistence.get_session_id()
    luaunit.assertNotNil(session_id)
    luaunit.assertStrContains(session_id, "-")
    luaunit.assertEquals(save_data.session_id, session_id)

    local out_data = {}
    persistence.save_state(out_data)
    luaunit.assertEquals(out_data.session_id, session_id)
end

function testLoadStatePreservesExistingSessionId()
    reset_state()

    local save_data = { session_id = "11111111-2222-4333-8444-555555555555" }
    persistence.load_state(save_data)

    luaunit.assertEquals(persistence.get_session_id(), save_data.session_id)

    local out_data = {}
    persistence.save_state(out_data)
    luaunit.assertEquals(out_data.session_id, save_data.session_id)
end

function testPublishConfigSyncIncludesSessionId()
    reset_state()

    local save_data = {}
    persistence.load_state(save_data)
    local session_id = persistence.get_session_id()

    local ok = publish_config_sync()
    luaunit.assertTrue(ok)
    luaunit.assertEquals(#published_messages, 1)
    luaunit.assertEquals(published_messages[1].topic, "config.sync")
    luaunit.assertEquals(published_messages[1].payload.session_id, session_id)
end

os.exit(luaunit.LuaUnit.run())

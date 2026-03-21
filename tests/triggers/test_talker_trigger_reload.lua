package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")
local luaunit = require('tests.utils.luaunit')
local mock_engine = require('tests.mocks.mock_engine')
local memory_store_v2 = require("domain.repo.memory_store_v2")
local EventType = require("domain.model.event_types")

-- Pre-inject mock game adapter before loading the trigger script
local mock_game_adapter = require('tests.mocks.mock_game_adapter')
package.loaded["infra.game_adapter"] = mock_game_adapter

package.path = package.path .. ';./gamedata/scripts/?.script'
require('talker_trigger_reload')

----------------------------------------------------------------------------------------------------
-- Setup
----------------------------------------------------------------------------------------------------

local function setup()
    mock_engine._reset()
    memory_store_v2:clear()
    -- Enable trigger with 100% chance so tests are deterministic
    mock_engine._set("triggers/reload/enable", true)
    mock_engine._set("triggers/reload/chance", 100)
end

----------------------------------------------------------------------------------------------------
-- Tests
----------------------------------------------------------------------------------------------------

function testTriggerReloadEnabled()
    setup()
    on_player_reloads_weapon()
    -- Should store an event
    local events, _ = memory_store_v2:query("1", "memory.events", {})
    luaunit.assertTrue(#events >= 1)
    luaunit.assertEquals(events[1].type, EventType.RELOAD)
end

function testTriggerReloadDisabled()
    setup()
    mock_engine._set("triggers/reload/enable", false)
    on_player_reloads_weapon()
    -- Should NOT store anything
    local events, _ = memory_store_v2:query("1", "memory.events", {})
    luaunit.assertEquals(#events, 0)
end

function testTriggerReloadChanceZero_storesOnly()
    setup()
    mock_engine._set("triggers/reload/chance", 0)
    on_player_reloads_weapon()
    -- Event should exist in memory (store_event) even when chance fails
    local events, _ = memory_store_v2:query("1", "memory.events", {})
    luaunit.assertTrue(#events >= 1)
end

function testSafeWrapperDoesNotThrow()
    setup()
    -- Just verify the safe wrapper doesn't error
    safe_on_player_reloads_weapon()
end

os.exit(luaunit.LuaUnit.run())
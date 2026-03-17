package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua;./gamedata/scripts/?.script'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local mock_engine = require("tests.mocks.mock_engine")

-- Mock keycloak client
local mock_keycloak_client = {
    _fetch_calls = 0,
    _fetched_token = nil,
    _fetch_error = nil,
}

function mock_keycloak_client.configure(token_url, client_id, refresh_token) end
function mock_keycloak_client.get_cached_token() return nil end
function mock_keycloak_client.fetch_token()
    mock_keycloak_client._fetch_calls = mock_keycloak_client._fetch_calls + 1
    return mock_keycloak_client._fetched_token, mock_keycloak_client._fetch_error
end
function mock_keycloak_client.clear() end

package.loaded["infra.auth.keycloak_client"] = mock_keycloak_client

-- Mock bridge channel — captures the before_connect and on_reconnect hooks
local captured_before_connect = nil

local mock_bridge = {}
function mock_bridge.init(url_fn, opts) end
function mock_bridge.set_before_connect(fn) captured_before_connect = fn end
function mock_bridge.set_on_reconnect(fn) end
function mock_bridge.get_status() return "disconnected" end
function mock_bridge.on(topic, fn) end
function mock_bridge.publish(topic, payload) end
function mock_bridge.tick() end
function mock_bridge.shutdown() end

package.loaded["infra.bridge.channel"] = mock_bridge

AddScriptCallback = AddScriptCallback or function() end

require("talker_ws_integration")

-- Trigger init_channels() once via a public API so the before_connect hook is registered.
-- Subsequent calls to register_command_handler are no-ops (is_initialized guard).
register_command_handler("test.init", function() end)

local function setup()
    mock_engine._reset()
    mock_keycloak_client._fetch_calls = 0
    mock_keycloak_client._fetched_token = nil
    mock_keycloak_client._fetch_error = nil
end

function testBeforeConnectHookIsRegisteredOnInit()
    setup()
    luaunit.assertNotNil(captured_before_connect, "bridge.set_before_connect should have been called during init")
end

function testReconnectFetchesTokenWhenAuthConfigured()
    setup()
    mock_engine._set("service_url", "wss://talker.example/ws/dev")
    mock_engine._set("auth_client_id", "talker-client")
    mock_engine._set("auth_refresh_token", "my-refresh-token")
    mock_keycloak_client._fetched_token = "fresh-access-token"

    -- Simulate bridge channel firing the pre-connect hook
    captured_before_connect()

    luaunit.assertEquals(mock_keycloak_client._fetch_calls, 1,
        "fetch_token should be called before reconnect when auth is configured")
end

function testReconnectSkipsFetchWhenAuthNotConfigured()
    setup()
    mock_engine._set("service_url", "ws://127.0.0.1:5557/ws")
    mock_engine._set("auth_client_id", "")
    mock_engine._set("auth_refresh_token", "")

    -- Simulate bridge channel firing the pre-connect hook
    captured_before_connect()

    luaunit.assertEquals(mock_keycloak_client._fetch_calls, 0,
        "fetch_token should NOT be called when auth is not configured")
end

os.exit(luaunit.LuaUnit.run())

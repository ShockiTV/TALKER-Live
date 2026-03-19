package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua;./gamedata/scripts/?.script'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local mock_engine = require("tests.mocks.mock_engine")

local mock_keycloak_client = {
    _configured = nil,
    _cached_token = nil,
    _fetched_token = nil,
    _fetch_error = nil,
    _fetch_calls = 0,
}

function mock_keycloak_client.configure(token_url, client_id, username, password, client_secret)
    mock_keycloak_client._configured = {
        token_url = token_url,
        client_id = client_id,
        username = username,
        password = password,
        client_secret = client_secret,
    }
end

function mock_keycloak_client.get_cached_token()
    return mock_keycloak_client._cached_token
end

function mock_keycloak_client.fetch_token()
    mock_keycloak_client._fetch_calls = mock_keycloak_client._fetch_calls + 1
    return mock_keycloak_client._fetched_token, mock_keycloak_client._fetch_error
end

function mock_keycloak_client.clear()
    mock_keycloak_client._configured = nil
    mock_keycloak_client._cached_token = nil
    mock_keycloak_client._fetched_token = nil
    mock_keycloak_client._fetch_error = nil
    mock_keycloak_client._fetch_calls = 0
end

package.loaded["infra.auth.keycloak_client"] = mock_keycloak_client

AddScriptCallback = AddScriptCallback or function() end

require("talker_ws_integration")

local function setup()
    mock_engine._reset()
    mock_keycloak_client.clear()
end

function testLocalDefaultUrl()
    setup()

    mock_engine._set("service_type", 0)
    mock_engine._set("service_url", "")
    mock_engine._set("service_ws_port", 5557)

    local url = build_service_url()

    luaunit.assertEquals(url, "ws://127.0.0.1:5557/ws")
end

function testLocalCustomUrl()
    setup()

    mock_engine._set("service_type", 0)
    mock_engine._set("service_url", "ws://192.168.1.50:7777/ws")

    local url = build_service_url()

    luaunit.assertEquals(url, "ws://192.168.1.50:7777/ws")
end

function testRemoteMainBranch()
    setup()

    mock_engine._set("service_type", 1)
    mock_engine._set("service_hub_url", "https://talker-live.duckdns.org")
    mock_engine._set("branch", 0)
    mock_engine._set("custom_branch", "")

    local url = build_service_url()

    luaunit.assertEquals(url, "wss://talker-live.duckdns.org/ws/main")
end

function testRemoteDevBranch()
    setup()

    mock_engine._set("service_type", 1)
    mock_engine._set("service_hub_url", "https://talker-live.duckdns.org")
    mock_engine._set("branch", 1)

    local url = build_service_url()

    luaunit.assertEquals(url, "wss://talker-live.duckdns.org/ws/dev")
end

function testRemoteCustomBranch()
    setup()

    mock_engine._set("service_type", 1)
    mock_engine._set("service_hub_url", "https://talker-live.duckdns.org")
    mock_engine._set("branch", 2)
    mock_engine._set("custom_branch", "feature-xyz")

    local url = build_service_url()

    luaunit.assertEquals(url, "wss://talker-live.duckdns.org/ws/feature-xyz")
end

function testRemoteWithoutCredentialsHasNoToken()
    setup()

    mock_engine._set("service_type", 1)
    mock_engine._set("service_hub_url", "https://talker-live.duckdns.org")
    mock_engine._set("branch", 0)
    mock_engine._set("auth_client_id", "")
    mock_engine._set("auth_username", "")
    mock_engine._set("auth_password", "")
    mock_engine._set("ws_token", "")

    local url = build_service_url()

    luaunit.assertEquals(url, "wss://talker-live.duckdns.org/ws/main")
    luaunit.assertEquals(mock_keycloak_client._fetch_calls, 0)
end

os.exit(luaunit.LuaUnit.run())

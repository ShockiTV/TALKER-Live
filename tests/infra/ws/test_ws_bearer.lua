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

function mock_keycloak_client.configure(token_url, client_id, refresh_token)
    mock_keycloak_client._configured = {
        token_url = token_url,
        client_id = client_id,
        refresh_token = refresh_token,
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

-- pollnet open_ws() has no header support; token goes as ?token= query param
-- in get_service_url(), so get_ws_connect_options() always returns nil.

function testConnectOptionsAlwaysNil()
    setup()
    mock_engine._set("ws_bearer_token", "token-123")

    local opts = build_ws_connect_options()

    luaunit.assertNil(opts)
end

function testConnectOptionsNilWhenTokenEmpty()
    setup()
    mock_engine._set("ws_bearer_token", "")

    local opts = build_ws_connect_options()

    luaunit.assertNil(opts)
end

function testServiceUrlPrefersRefreshTokenAuth()
    setup()

    mock_engine._set("service_url", "wss://talker.example/ws/dev")
    mock_engine._set("ws_bearer_token", "legacy-token")
    mock_engine._set("auth_client_id", "talker-client")
    mock_engine._set("auth_refresh_token", "refresh-token")

    mock_keycloak_client._fetched_token = "fresh-token"

    local url = build_service_url()

    luaunit.assertEquals(url, "wss://talker.example/ws/dev?token=fresh-token")
    luaunit.assertEquals(mock_keycloak_client._fetch_calls, 1)
end

function testServiceUrlFallsBackToBearerToken()
    setup()

    mock_engine._set("service_url", "wss://talker.example/ws/dev")
    mock_engine._set("ws_bearer_token", "legacy-token")
    mock_engine._set("auth_client_id", "")
    mock_engine._set("auth_refresh_token", "")

    local url = build_service_url()

    luaunit.assertEquals(url, "wss://talker.example/ws/dev?token=legacy-token")
    luaunit.assertEquals(mock_keycloak_client._fetch_calls, 0)
end

function testServiceUrlHasNoTokenWhenUnset()
    setup()

    mock_engine._set("service_url", "ws://127.0.0.1:5557/ws")
    mock_engine._set("ws_bearer_token", "")
    mock_engine._set("auth_client_id", "")
    mock_engine._set("auth_refresh_token", "")

    local url = build_service_url()

    luaunit.assertEquals(url, "ws://127.0.0.1:5557/ws")
end

function testServiceUrlUsesBearerWhenFetchFails()
    setup()

    mock_engine._set("service_url", "wss://talker.example/ws/dev")
    mock_engine._set("ws_bearer_token", "legacy-token")
    mock_engine._set("auth_client_id", "talker-client")
    mock_engine._set("auth_refresh_token", "refresh-token")

    mock_keycloak_client._fetched_token = nil
    mock_keycloak_client._fetch_error = "network down"

    local url = build_service_url()

    luaunit.assertEquals(url, "wss://talker.example/ws/dev?token=legacy-token")
    luaunit.assertEquals(mock_keycloak_client._fetch_calls, 1)
end

os.exit(luaunit.LuaUnit.run())

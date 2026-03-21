package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local mock_engine = require("tests.mocks.mock_engine")
local config = require("interface.config")

local function setup()
    mock_engine._reset()
end

function testAuthGettersUseDefaultsWhenUnset()
    setup()

    luaunit.assertEquals(config.service_type(), 0)
    luaunit.assertEquals(config.service_hub_url(), "")
    luaunit.assertEquals(config.branch(), 0)
    luaunit.assertEquals(config.custom_branch(), "")
    luaunit.assertEquals(config.service_url(), "")
    luaunit.assertEquals(config.service_ws_port(), 5557)
    luaunit.assertEquals(config.ws_token(), "")
    luaunit.assertEquals(config.auth_client_id(), "talker-client")
    luaunit.assertEquals(config.auth_client_secret(), "")
    luaunit.assertEquals(config.auth_username(), "")
    luaunit.assertEquals(config.auth_password(), "")
end

function testAuthGettersReturnOverrides()
    setup()

    mock_engine._set("service_type", 1)
    mock_engine._set("service_hub_url", "https://talker-live.duckdns.org")
    mock_engine._set("branch", 2)
    mock_engine._set("custom_branch", "feature-x")
    mock_engine._set("service_url", "ws://192.168.1.50:5557/ws")
    mock_engine._set("service_ws_port", 7777)
    mock_engine._set("ws_token", "invite-token")
    mock_engine._set("auth_client_id", "talker-client")
    mock_engine._set("auth_client_secret", "my-secret")
    mock_engine._set("auth_username", "bob")
    mock_engine._set("auth_password", "secret-value")

    luaunit.assertEquals(config.service_type(), 1)
    luaunit.assertEquals(config.service_hub_url(), "https://talker-live.duckdns.org")
    luaunit.assertEquals(config.branch(), 2)
    luaunit.assertEquals(config.custom_branch(), "feature-x")
    luaunit.assertEquals(config.service_url(), "ws://192.168.1.50:5557/ws")
    luaunit.assertEquals(config.service_ws_port(), 7777)
    luaunit.assertEquals(config.ws_token(), "invite-token")
    luaunit.assertEquals(config.auth_client_id(), "talker-client")
    luaunit.assertEquals(config.auth_client_secret(), "my-secret")
    luaunit.assertEquals(config.auth_username(), "bob")
    luaunit.assertEquals(config.auth_password(), "secret-value")
end

os.exit(luaunit.LuaUnit.run())

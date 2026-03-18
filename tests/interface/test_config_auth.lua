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

    luaunit.assertEquals(config.auth_client_id(), "")
    luaunit.assertEquals(config.auth_client_secret(), "")
    luaunit.assertEquals(config.auth_username(), "")
    luaunit.assertEquals(config.auth_password(), "")
end

function testAuthGettersReturnOverrides()
    setup()

    mock_engine._set("auth_client_id", "talker-client")
    mock_engine._set("auth_client_secret", "my-secret")
    mock_engine._set("auth_username", "bob")
    mock_engine._set("auth_password", "secret-value")

    luaunit.assertEquals(config.auth_client_id(), "talker-client")
    luaunit.assertEquals(config.auth_client_secret(), "my-secret")
    luaunit.assertEquals(config.auth_username(), "bob")
    luaunit.assertEquals(config.auth_password(), "secret-value")
end

os.exit(luaunit.LuaUnit.run())

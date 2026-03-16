package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua;./gamedata/scripts/?.script'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local mock_engine = require("tests.mocks.mock_engine")

AddScriptCallback = AddScriptCallback or function() end

require("talker_ws_integration")

local function setup()
    mock_engine._reset()
end

function testBearerHeaderPresentWhenTokenConfigured()
    setup()
    mock_engine._set("ws_bearer_token", "token-123")

    local opts = build_ws_connect_options()

    luaunit.assertNotNil(opts)
    luaunit.assertNotNil(opts.headers)
    luaunit.assertEquals(opts.headers.Authorization, "Bearer token-123")
end

function testBearerHeaderAbsentWhenTokenEmpty()
    setup()
    mock_engine._set("ws_bearer_token", "")

    local opts = build_ws_connect_options()

    luaunit.assertNil(opts)
end

os.exit(luaunit.LuaUnit.run())

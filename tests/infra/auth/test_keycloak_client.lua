package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")

local captured_logs = {}
local mock_logger = {
    debug = function(msg, ...)
        table.insert(captured_logs, string.format(msg, ...))
    end,
    info = function(msg, ...)
        table.insert(captured_logs, string.format(msg, ...))
    end,
    warn = function(msg, ...)
        table.insert(captured_logs, string.format(msg, ...))
    end,
    error = function(msg, ...)
        table.insert(captured_logs, string.format(msg, ...))
    end,
}

package.loaded["framework.logger"] = mock_logger
package.loaded["infra.auth.keycloak_client"] = nil

local keycloak_client = require("infra.auth.keycloak_client")

local function assertNoLogLeak(secret, token)
    local joined = table.concat(captured_logs, "\n")
    if secret and secret ~= "" then
        luaunit.assertNotStrContains(joined, secret)
    end
    if token and token ~= "" then
        luaunit.assertNotStrContains(joined, token)
    end
end

local function setup_with_time(time_value)
    captured_logs = {}
    keycloak_client._reset_for_test()

    local now_clock = 0
    local now_time = time_value or 1000

    keycloak_client._set_time_sources(
        function()
            return now_clock
        end,
        function()
            return now_time
        end
    )

    return {
        set_clock = function(value)
            now_clock = value
        end,
        set_time = function(value)
            now_time = value
        end,
        advance_time = function(delta)
            now_time = now_time + delta
            return now_time
        end,
    }
end

function testDisabledModeDoesNotCallHttp()
    setup_with_time()

    local calls = 0
    keycloak_client._set_transport(function()
        calls = calls + 1
        return nil
    end, nil)

    keycloak_client.configure("", "", "")
    local token, err = keycloak_client.fetch_token()

    luaunit.assertNil(token)
    luaunit.assertNil(err)
    luaunit.assertNil(keycloak_client.get_cached_token())
    luaunit.assertEquals(calls, 0)
end

function testDisabledWhenRefreshTokenMissing()
    -- token_url and client_id set, but refresh_token empty → auth disabled, no HTTP
    setup_with_time()

    local calls = 0
    keycloak_client._set_transport(function()
        calls = calls + 1
        return nil
    end, nil)

    keycloak_client.configure("https://auth.example/token", "talker-client", "")
    local token, err = keycloak_client.fetch_token()

    luaunit.assertNil(token)
    luaunit.assertNil(err)
    luaunit.assertNil(keycloak_client.get_cached_token())
    luaunit.assertEquals(calls, 0)
end

function testFetchTokenSuccessAndCaching()
    local time_ctl = setup_with_time(1000)

    local captured = {}
    local poll_calls = 0
    local token_value = "eyJ.token.value"
    local refresh_token_value = "refresh token value"

    local sock = {
        close = function(self)
            captured.closed = true
        end,
        status = function()
            return "open"
        end,
        poll = function()
            poll_calls = poll_calls + 1
            if poll_calls == 1 then
                return true, '{"access_token":"' .. token_value .. '","expires_in":300,"token_type":"Bearer"}'
            end
            return true, nil
        end,
    }

    keycloak_client._set_transport(function(url, headers, body, return_body_only)
        captured.url = url
        captured.headers = headers
        captured.body = body
        captured.return_body_only = return_body_only
        return sock
    end, nil)

    keycloak_client.configure("https://auth.example/token", "talker-client", refresh_token_value)

    local token, err = keycloak_client.fetch_token()
    luaunit.assertEquals(token, token_value)
    luaunit.assertNil(err)

    luaunit.assertEquals(captured.url, "https://auth.example/token")
    luaunit.assertEquals(captured.headers["content-type"], "application/x-www-form-urlencoded")
    luaunit.assertTrue(captured.return_body_only)
    luaunit.assertStrContains(captured.body, "grant_type=refresh_token")
    luaunit.assertStrContains(captured.body, "client_id=talker-client")
    luaunit.assertStrContains(captured.body, "refresh_token=refresh%20token%20value")
    luaunit.assertTrue(captured.closed)

    luaunit.assertEquals(keycloak_client.get_cached_token(), token_value)

    -- 50 seconds remaining falls inside the 60 second safety margin.
    time_ctl.advance_time(250)
    luaunit.assertNil(keycloak_client.get_cached_token())

    assertNoLogLeak(refresh_token_value, token_value)
end

function testFetchTokenRotatesRefreshTokenWhenProvided()
    setup_with_time(1000)

    local request_bodies = {}
    local response_index = 0

    keycloak_client._set_transport(function(url, headers, body, return_body_only)
        request_bodies[#request_bodies + 1] = body
        return {
            close = function() end,
            status = function()
                return "open"
            end,
            poll = function()
                response_index = response_index + 1
                if response_index == 1 then
                    return true, '{"access_token":"first","expires_in":300,"refresh_token":"rt-new"}'
                end
                return true, '{"access_token":"second","expires_in":300}'
            end,
        }
    end, nil)

    keycloak_client.configure("https://auth.example/token", "talker-client", "rt-old")

    local first = keycloak_client.fetch_token()
    local second = keycloak_client.fetch_token()

    luaunit.assertEquals(first, "first")
    luaunit.assertEquals(second, "second")
    luaunit.assertStrContains(request_bodies[1], "refresh_token=rt-old")
    luaunit.assertStrContains(request_bodies[2], "refresh_token=rt-new")
end

function testFetchTokenReturnsOauthErrorMessage()
    setup_with_time()

    local sock = {
        close = function() end,
        status = function()
            return "open"
        end,
        poll = function()
            return true, '{"error":"unauthorized_client","error_description":"Invalid client credentials"}'
        end,
    }

    keycloak_client._set_transport(function()
        return sock
    end, nil)

    keycloak_client.configure("https://auth.example/token", "talker-client", "refresh-token")

    local token, err = keycloak_client.fetch_token()
    luaunit.assertNil(token)
    luaunit.assertEquals(err, "unauthorized_client: Invalid client credentials")
    luaunit.assertNil(keycloak_client.get_cached_token())
end

function testFetchTokenTimeout()
    captured_logs = {}
    keycloak_client._reset_for_test()

    local clock_tick = 0
    keycloak_client._set_time_sources(
        function()
            clock_tick = clock_tick + 1
            return clock_tick
        end,
        function()
            return 1000
        end
    )

    local sock = {
        close = function() end,
        status = function()
            return "opening"
        end,
        poll = function()
            return true, nil
        end,
    }

    keycloak_client._set_transport(function()
        return sock
    end, nil)

    keycloak_client.configure("https://auth.example/token", "talker-client", "refresh-token")

    local token, err = keycloak_client.fetch_token()
    luaunit.assertNil(token)
    luaunit.assertEquals(err, "token fetch timeout")
end

function testClearResetsCacheAndConfiguration()
    setup_with_time()

    local poll_calls = 0
    local sock = {
        close = function() end,
        status = function()
            return "open"
        end,
        poll = function()
            poll_calls = poll_calls + 1
            if poll_calls == 1 then
                return true, '{"access_token":"abc","expires_in":300}'
            end
            return true, nil
        end,
    }

    local http_calls = 0
    keycloak_client._set_transport(function()
        http_calls = http_calls + 1
        return sock
    end, nil)

    keycloak_client.configure("https://auth.example/token", "talker-client", "refresh-token")
    local token = keycloak_client.fetch_token()
    luaunit.assertEquals(token, "abc")
    luaunit.assertEquals(keycloak_client.get_cached_token(), "abc")

    keycloak_client.clear()
    luaunit.assertNil(keycloak_client.get_cached_token())

    local refetched, err = keycloak_client.fetch_token()
    luaunit.assertNil(refetched)
    luaunit.assertNil(err)
    luaunit.assertEquals(http_calls, 1)
end

os.exit(luaunit.LuaUnit.run())

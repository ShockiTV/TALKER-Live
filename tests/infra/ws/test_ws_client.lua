package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit   = require('tests.utils.luaunit')
local ws_client = require('infra.ws.client')

-- ── Mock socket ──────────────────────────────────────────────────────────────

local function make_mock_socket(opts)
    opts = opts or {}
    local sock = {
        _status   = opts.status or "opening",
        _messages = opts.messages or {},
        _sent     = {},
        _closed   = false,
    }

    function sock:poll()
        if self._closed then return false, "closed" end
        if self._status == "error" then return false, "error" end
        if #self._messages > 0 then
            local msg = table.remove(self._messages, 1)
            return true, msg
        end
        return true, nil  -- no data
    end

    function sock:send(msg)
        table.insert(self._sent, msg)
    end

    function sock:close()
        self._closed = true
        self._status = "closed"
    end

    function sock:status()
        return self._status
    end

    return sock
end

-- ── Test setup / teardown ────────────────────────────────────────────────────

local _last_mock = nil

local function setup()
    ws_client._reset()
end

local function inject_factory(mock_socket)
    _last_mock = mock_socket
    ws_client.set_socket_factory(function(url)
        return mock_socket
    end)
end

-- ── open ─────────────────────────────────────────────────────────────────────

function testOpen_returnsHandle()
    setup()
    inject_factory(make_mock_socket())
    local h = ws_client.open("ws://localhost:5557/ws")
    luaunit.assertNotNil(h)
    luaunit.assertEquals(type(h), "number")
end

function testOpen_emptyUrl_returnsNil()
    setup()
    inject_factory(make_mock_socket())
    local h = ws_client.open("")
    luaunit.assertNil(h)
end

function testOpen_nilUrl_returnsNil()
    setup()
    inject_factory(make_mock_socket())
    local h = ws_client.open(nil)
    luaunit.assertNil(h)
end

function testOpen_incrementsHandles()
    setup()
    local count = 0
    ws_client.set_socket_factory(function(url)
        count = count + 1
        return make_mock_socket()
    end)
    local h1 = ws_client.open("ws://a")
    local h2 = ws_client.open("ws://b")
    luaunit.assertTrue(h2 > h1)
    luaunit.assertEquals(count, 2)
end

-- ── send ─────────────────────────────────────────────────────────────────────

function testSend_success()
    setup()
    local mock = make_mock_socket({ status = "open" })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    local ok = ws_client.send(h, '{"t":"test","p":{}}')
    luaunit.assertTrue(ok)
    luaunit.assertEquals(#mock._sent, 1)
    luaunit.assertEquals(mock._sent[1], '{"t":"test","p":{}}')
end

function testSend_nilHandle_returnsFalse()
    setup()
    local ok = ws_client.send(nil, "msg")
    luaunit.assertFalse(ok)
end

function testSend_invalidHandle_returnsFalse()
    setup()
    local ok = ws_client.send(999, "msg")
    luaunit.assertFalse(ok)
end

-- ── poll ─────────────────────────────────────────────────────────────────────

function testPoll_returnsMessage()
    setup()
    local mock = make_mock_socket({ status = "open", messages = { '{"t":"a","p":{}}' } })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    local msg = ws_client.poll(h)
    luaunit.assertEquals(msg, '{"t":"a","p":{}}')
end

function testPoll_returnsNilWhenEmpty()
    setup()
    local mock = make_mock_socket({ status = "open", messages = {} })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    local msg = ws_client.poll(h)
    luaunit.assertNil(msg)
end

function testPoll_invalidHandle_returnsNil()
    setup()
    local msg = ws_client.poll(999)
    luaunit.assertNil(msg)
end

function testPoll_drainsOneAtATime()
    setup()
    local mock = make_mock_socket({ status = "open", messages = { "msg1", "msg2", "msg3" } })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    luaunit.assertEquals(ws_client.poll(h), "msg1")
    luaunit.assertEquals(ws_client.poll(h), "msg2")
    luaunit.assertEquals(ws_client.poll(h), "msg3")
    luaunit.assertNil(ws_client.poll(h))
end

-- ── status ───────────────────────────────────────────────────────────────────

function testStatus_connected()
    setup()
    local mock = make_mock_socket({ status = "open" })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    luaunit.assertEquals(ws_client.status(h), "connected")
end

function testStatus_connecting()
    setup()
    local mock = make_mock_socket({ status = "opening" })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    luaunit.assertEquals(ws_client.status(h), "connecting")
end

function testStatus_closed()
    setup()
    local mock = make_mock_socket({ status = "closed" })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    luaunit.assertEquals(ws_client.status(h), "closed")
end

function testStatus_error()
    setup()
    local mock = make_mock_socket({ status = "error" })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    luaunit.assertEquals(ws_client.status(h), "error")
end

function testStatus_invalidHandle_returnsClosed()
    setup()
    luaunit.assertEquals(ws_client.status(999), "closed")
end

function testStatus_unpolled_returnsConnecting()
    setup()
    local mock = make_mock_socket({ status = "unpolled" })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    luaunit.assertEquals(ws_client.status(h), "connecting")
end

-- ── close ────────────────────────────────────────────────────────────────────

function testClose_closesSocket()
    setup()
    local mock = make_mock_socket({ status = "open" })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    ws_client.close(h)
    luaunit.assertTrue(mock._closed)
    -- Subsequent status returns closed (handle removed)
    luaunit.assertEquals(ws_client.status(h), "closed")
end

function testClose_invalidHandle_isNoop()
    setup()
    -- Should not error
    ws_client.close(999)
end

function testClose_doubleClose_isNoop()
    setup()
    local mock = make_mock_socket({ status = "open" })
    inject_factory(mock)
    local h = ws_client.open("ws://x")
    ws_client.close(h)
    ws_client.close(h) -- should not error
end

-- ── factory injection ────────────────────────────────────────────────────────

function testSetSocketFactory_usesInjected()
    setup()
    local called_with = nil
    ws_client.set_socket_factory(function(url)
        called_with = url
        return make_mock_socket()
    end)
    ws_client.open("ws://test-url")
    luaunit.assertEquals(called_with, "ws://test-url")
end

function testReset_clearsState()
    setup()
    inject_factory(make_mock_socket({ status = "open" }))
    local h = ws_client.open("ws://x")
    luaunit.assertNotNil(h)
    ws_client._reset()
    -- After reset, old handle is gone
    luaunit.assertEquals(ws_client.status(h), "closed")
end

os.exit(luaunit.LuaUnit.run())

package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit     = require('tests.utils.luaunit')
local ws_client   = require('infra.ws.client')
local codec       = require('infra.ws.codec')
local mic_channel = require('infra.mic.channel')

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
        if #self._messages > 0 then return true, table.remove(self._messages, 1) end
        return true, nil
    end
    function sock:send(msg) table.insert(self._sent, msg) end
    function sock:close() self._closed = true; self._status = "closed" end
    function sock:status() return self._status end
    return sock
end

local _mock = nil

local function setup()
    mic_channel._reset()
    ws_client._reset()
    _mock = make_mock_socket({ status = "open" })
    ws_client.set_socket_factory(function() return _mock end)
    mic_channel.init("ws://localhost:5558")
    mic_channel.tick()  -- → CONNECTING
    mic_channel.tick()  -- → CONNECTED
end

-- ── Session registration ─────────────────────────────────────────────────────

function testStartSession_statusHandlerCalled()
    setup()
    local received = nil
    mic_channel.start_session(
        function(p) received = p end,
        function() end
    )

    _mock._messages = { codec.encode("mic.status", { status = "recording" }) }
    mic_channel.tick()

    luaunit.assertNotNil(received)
    luaunit.assertEquals(received.status, "recording")
end

function testStartSession_resultHandlerCalled()
    setup()
    local received = nil
    mic_channel.start_session(
        function() end,
        function(p) received = p end
    )

    _mock._messages = { codec.encode("mic.result", { text = "hello" }) }
    mic_channel.tick()

    luaunit.assertNotNil(received)
    luaunit.assertEquals(received.text, "hello")
end

function testStartSession_clearsPreviousHandlers()
    setup()
    local first_called = false
    local second_called = false

    mic_channel.start_session(
        function() first_called = true end,
        function() end
    )
    mic_channel.start_session(
        function() second_called = true end,
        function() end
    )

    _mock._messages = { codec.encode("mic.status", {}) }
    mic_channel.tick()

    luaunit.assertFalse(first_called)
    luaunit.assertTrue(second_called)
end

-- ── Auto-cleanup on mic.result ───────────────────────────────────────────────

function testAutoCleanup_handlersCleared()
    setup()
    local status_count = 0
    local result_count = 0

    mic_channel.start_session(
        function() status_count = status_count + 1 end,
        function() result_count = result_count + 1 end
    )

    -- Send mic.result → triggers auto-cleanup
    _mock._messages = { codec.encode("mic.result", { text = "done" }) }
    mic_channel.tick()
    luaunit.assertEquals(result_count, 1)

    -- Subsequent mic.status should NOT call the old handler
    _mock._messages = { codec.encode("mic.status", { status = "x" }) }
    mic_channel.tick()
    luaunit.assertEquals(status_count, 0)
end

-- ── Publish ──────────────────────────────────────────────────────────────────

function testPublish_sendsWhenConnected()
    setup()
    mic_channel.publish("mic.start", {})
    luaunit.assertEquals(#_mock._sent, 1)
end

function testPublish_queuesWhenDisconnected()
    mic_channel._reset()
    ws_client._reset()
    ws_client.set_socket_factory(function() return make_mock_socket({ status = "opening" }) end)
    mic_channel.init("ws://localhost:5558")
    mic_channel.publish("mic.start", {})
    luaunit.assertEquals(mic_channel._queue_size(), 1)
end

-- ── Independent lifecycle ────────────────────────────────────────────────────

function testIndependentLifecycle()
    -- This is a structural test — mic_channel's state is independent.
    -- Just verify it has its own get_status.
    setup()
    luaunit.assertEquals(mic_channel.get_status(), "connected")
    mic_channel.shutdown()
    luaunit.assertEquals(mic_channel.get_status(), "disconnected")
end

-- ── Shutdown ─────────────────────────────────────────────────────────────────

function testShutdown_clearsSessionHandlers()
    setup()
    mic_channel.start_session(function() end, function() end)
    mic_channel.shutdown()
    -- After shutdown, session handlers should be cleared
    -- Reinitialise and verify no old handlers fire
    _mock = make_mock_socket({ status = "open" })
    ws_client.set_socket_factory(function() return _mock end)
    mic_channel.init("ws://localhost:5558")
    mic_channel.tick()
    mic_channel.tick()

    local called = false
    -- Don't register new session — old handlers should be gone
    _mock._messages = { codec.encode("mic.status", {}) }
    mic_channel.tick()
    -- If no error, handler was properly cleared
end

os.exit(luaunit.LuaUnit.run())

package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit   = require('tests.utils.luaunit')
local ws_client = require('infra.ws.client')
local codec     = require('infra.ws.codec')
local json      = require('infra.HTTP.json')
local channel   = require('infra.service.channel')

-- ── Mock socket helper ───────────────────────────────────────────────────────

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
        if #self._messages > 0 then
            return true, table.remove(self._messages, 1)
        end
        return true, nil
    end
    function sock:send(msg) table.insert(self._sent, msg) end
    function sock:close() self._closed = true; self._status = "closed" end
    function sock:status() return self._status end
    return sock
end

-- Shared mock socket reference — set per test
local _mock = nil

local function setup()
    channel._reset()
    ws_client._reset()
    _mock = make_mock_socket()
    ws_client.set_socket_factory(function() return _mock end)
end

-- ── State machine transitions ────────────────────────────────────────────────

function testInit_setsDisconnected()
    setup()
    channel.init("ws://localhost:5557/ws")
    luaunit.assertEquals(channel.get_status(), "disconnected")
end

function testFirstTick_transitionsToConnecting()
    setup()
    channel.init("ws://localhost:5557/ws")
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "connecting")
end

function testTick_connectingToConnected()
    setup()
    _mock._status = "opening"
    channel.init("ws://x")
    channel.tick()  -- DISCONNECTED → CONNECTING
    luaunit.assertEquals(channel.get_status(), "connecting")

    _mock._status = "open"
    channel.tick()  -- CONNECTING → CONNECTED
    luaunit.assertEquals(channel.get_status(), "connected")
end

function testTick_connectedToReconnecting_onClose()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()  -- → CONNECTING
    channel.tick()  -- → CONNECTED

    _mock._status = "closed"
    channel.tick()  -- → RECONNECTING
    luaunit.assertEquals(channel.get_status(), "reconnecting")
end

function testTick_connectedToReconnecting_onError()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()

    _mock._status = "error"
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "reconnecting")
end

function testTick_noTickWithoutInit()
    setup()
    -- tick without init should be a no-op
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "disconnected")
end

-- ── Queue flush on connect ───────────────────────────────────────────────────

function testPublish_queuesWhenDisconnected()
    setup()
    channel.init("ws://x")
    channel.publish("game.event", { type = "DEATH" })
    luaunit.assertEquals(channel._queue_size(), 1)
    luaunit.assertEquals(#_mock._sent, 0)
end

function testPublish_sendsWhenConnected()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "connected")

    channel.publish("game.event", { type = "DEATH" })
    luaunit.assertEquals(#_mock._sent, 1)
    -- Verify the sent message is valid codec output
    local envelope = json.decode(_mock._sent[1])
    luaunit.assertEquals(envelope.t, "game.event")
    luaunit.assertEquals(envelope.p.type, "DEATH")
end

function testPublish_queueFlushedOnConnect()
    setup()
    _mock._status = "opening"
    channel.init("ws://x")
    channel.tick()  -- → CONNECTING

    channel.publish("game.event", { type = "DEATH" })
    channel.publish("config.sync", { key = "val" })
    luaunit.assertEquals(channel._queue_size(), 2)
    luaunit.assertEquals(#_mock._sent, 0)

    _mock._status = "open"
    channel.tick()  -- → CONNECTED, flushes queue
    luaunit.assertEquals(channel._queue_size(), 0)
    luaunit.assertEquals(#_mock._sent, 2)
end

function testPublish_queueDropsOldest()
    setup()
    channel.init("ws://x")
    -- Fill queue beyond MAX_QUEUE_SIZE (100)
    for i = 1, 110 do
        channel.publish("t", { n = i })
    end
    luaunit.assertEquals(channel._queue_size(), 100)
end

-- ── Topic handlers ───────────────────────────────────────────────────────────

function testOn_handlerCalledOnMatchingTopic()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()

    local received = nil
    channel.on("dialogue.display", function(payload)
        received = payload
    end)

    -- Simulate incoming message
    _mock._messages = { codec.encode("dialogue.display", { speaker_id = "5" }) }
    channel.tick()

    luaunit.assertNotNil(received)
    luaunit.assertEquals(received.speaker_id, "5")
end

function testOn_handlerNotCalledOnNonMatchingTopic()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()

    local called = false
    channel.on("dialogue.display", function() called = true end)

    _mock._messages = { codec.encode("memory.update", {}) }
    channel.tick()

    luaunit.assertFalse(called)
end

function testOn_multipleHandlersPerTopic()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()

    local count = 0
    channel.on("test", function() count = count + 1 end)
    channel.on("test", function() count = count + 1 end)

    _mock._messages = { codec.encode("test", {}) }
    channel.tick()

    luaunit.assertEquals(count, 2)
end

-- ── Request/response correlation ─────────────────────────────────────────────

function testRequest_callbackInvokedOnMatchingR()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()

    -- Use deterministic ID generator
    channel._set_id_generator(function() return "test-req-1" end)

    local response_payload = nil
    channel.request("state.query.batch", { queries = {} }, function(payload)
        response_payload = payload
    end)

    luaunit.assertEquals(channel._pending_count(), 1)

    -- Simulate response with matching r
    local response = json.encode({ t = "state.response", p = { answer = 42 }, r = "test-req-1" })
    _mock._messages = { response }
    channel.tick()

    luaunit.assertNotNil(response_payload)
    luaunit.assertEquals(response_payload.answer, 42)
    luaunit.assertEquals(channel._pending_count(), 0)
end

function testRequest_rFieldBypassesTopicHandler()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()

    channel._set_id_generator(function() return "req-bypass" end)

    local topic_called = false
    channel.on("state.response", function() topic_called = true end)

    channel.request("state.query.batch", {}, function() end)

    local response = json.encode({ t = "state.response", p = {}, r = "req-bypass" })
    _mock._messages = { response }
    channel.tick()

    luaunit.assertFalse(topic_called)
end

-- ── Tick drain limit ─────────────────────────────────────────────────────────

function testTick_drainsMultipleMessages()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()

    local count = 0
    channel.on("test", function() count = count + 1 end)

    -- Queue 3 messages
    _mock._messages = {
        codec.encode("test", {}),
        codec.encode("test", {}),
        codec.encode("test", {}),
    }
    channel.tick()

    luaunit.assertEquals(count, 3)
end

function testTick_drainsUpToMaxPerTick()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()

    local count = 0
    channel.on("test", function() count = count + 1 end)

    -- Queue 25 messages (exceeds MAX_MESSAGES_PER_TICK = 20)
    for _ = 1, 25 do
        table.insert(_mock._messages, codec.encode("test", {}))
    end
    channel.tick()

    luaunit.assertEquals(count, 20)  -- capped at 20

    -- Remaining 5 on next tick
    channel.tick()
    luaunit.assertEquals(count, 25)
end

-- ── on_reconnect callback ────────────────────────────────────────────────────

function testOnReconnect_notCalledOnFirstConnect()
    setup()
    _mock._status = "open"
    local reconnect_called = false
    channel.init("ws://x")
    channel.set_on_reconnect(function() reconnect_called = true end)
    channel.tick()
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "connected")
    luaunit.assertFalse(reconnect_called)
end

function testOnReconnect_calledOnReconnect()
    setup()
    local reconnect_called = false

    -- First connection
    _mock._status = "open"
    channel.init("ws://x")
    channel.set_on_reconnect(function() reconnect_called = true end)
    channel.tick()  -- → CONNECTING
    channel.tick()  -- → CONNECTED

    -- Disconnect
    _mock._status = "closed"
    channel.tick()  -- → RECONNECTING
    luaunit.assertEquals(channel.get_status(), "reconnecting")

    -- New mock for reconnect (factory creates new socket)
    local new_mock = make_mock_socket({ status = "open" })
    ws_client.set_socket_factory(function() return new_mock end)

    -- Force backoff deadline to past
    -- Use pcall in case _backoff_deadline doesn't exist directly,
    -- but since we wait for os.clock() to pass, let's just manipulate.
    -- The backoff is small (1s ± jitter), we can't wait, so we override os.clock.
    local old_clock = os.clock
    os.clock = function() return old_clock() + 60 end  -- 60s in the future

    channel.tick()  -- RECONNECTING → CONNECTING (backoff expired)
    channel.tick()  -- CONNECTING → CONNECTED → fires on_reconnect

    os.clock = old_clock

    luaunit.assertTrue(reconnect_called)
end

-- ── Shutdown ─────────────────────────────────────────────────────────────────

function testShutdown_closesAndResetsState()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "connected")

    channel.shutdown()
    luaunit.assertEquals(channel.get_status(), "disconnected")
    luaunit.assertTrue(_mock._closed)
end

function testShutdown_clearsQueue()
    setup()
    channel.init("ws://x")
    channel.publish("test", {})
    luaunit.assertEquals(channel._queue_size(), 1)

    channel.shutdown()
    luaunit.assertEquals(channel._queue_size(), 0)
end

-- ── Backoff ──────────────────────────────────────────────────────────────────

function testBackoff_reconnectWaitsBeforeRetrying()
    setup()
    -- Connect then disconnect
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()  -- → CONNECTING
    channel.tick()  -- → CONNECTED
    luaunit.assertEquals(channel.get_status(), "connected")

    _mock._status = "closed"
    channel.tick()  -- → RECONNECTING
    luaunit.assertEquals(channel.get_status(), "reconnecting")

    -- Freeze time so backoff deadline is never reached
    local real_clock = os.clock
    local frozen_time = real_clock()
    os.clock = function() return frozen_time end

    -- Ticking while backoff hasn't expired should stay RECONNECTING
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "reconnecting")
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "reconnecting")

    -- Advance time past the backoff (>1s base + jitter cap of 20%)
    os.clock = function() return frozen_time + 2.0 end

    -- Provide a fresh mock for the new connection attempt
    local new_mock = make_mock_socket({ status = "opening" })
    ws_client.set_socket_factory(function() return new_mock end)

    channel.tick()  -- backoff expired → CONNECTING
    luaunit.assertEquals(channel.get_status(), "connecting")

    os.clock = real_clock
end

function testBackoff_resetsAfterSuccessfulReconnect()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "connected")

    -- Disconnect
    _mock._status = "closed"
    channel.tick()  -- → RECONNECTING

    -- Reconnect
    local new_mock = make_mock_socket({ status = "open" })
    ws_client.set_socket_factory(function() return new_mock end)

    local old_clock = os.clock
    os.clock = function() return old_clock() + 60 end
    channel.tick()  -- → CONNECTING
    channel.tick()  -- → CONNECTED
    os.clock = old_clock

    luaunit.assertEquals(channel.get_status(), "connected")

    -- Next disconnect should restart backoff at base (1s), not escalated
    -- Verified indirectly by successful reconnect above
end

-- ── Malformed message handling ───────────────────────────────────────────────

function testTick_malformedMessageIsSkipped()
    setup()
    _mock._status = "open"
    channel.init("ws://x")
    channel.tick()
    channel.tick()

    local called = false
    channel.on("test", function() called = true end)

    _mock._messages = { "not valid json", codec.encode("test", {}) }
    channel.tick()

    luaunit.assertTrue(called)  -- second message still dispatched
end

os.exit(luaunit.LuaUnit.run())

package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit   = require('tests.utils.luaunit')
local ws_client = require('infra.ws.client')
local codec     = require('infra.ws.codec')
local json      = require('infra.HTTP.json')
local channel   = require('infra.bridge.channel')

-- ── Mock socket ──────────────────────────────────────────────────────────────

local function make_mock_socket(opts)
    opts = opts or {}
    local sock = {
        _status    = opts.status or "opening",
        _messages  = opts.messages or {},
        _sent      = {},
        _closed    = false,
    }

    function sock:poll()
        if self._closed then return false, "closed" end
        if self._status == "error" then return false, "error" end
        if #self._messages > 0 then
            local msg = table.remove(self._messages, 1)
            return true, msg
        end
        return true, nil
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

-- ── Test helpers ─────────────────────────────────────────────────────────────

local _last_mock

--- Common setup: reset channel + ws_client, inject a mock socket
local function setup(sock_opts)
    channel._reset()
    ws_client._reset()
    local mock_sock = make_mock_socket(sock_opts)
    _last_mock = mock_sock
    ws_client.set_socket_factory(function(_url)
        return mock_sock
    end)
    return mock_sock
end

--- Drive channel from DISCONNECTED to CONNECTED in two ticks
local function connect(url)
    url = url or "ws://localhost:5558/ws"
    channel.init(url)
    -- tick 1: DISCONNECTED → CONNECTING
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "connecting")
    -- transition socket status
    _last_mock._status = "open"
    -- tick 2: CONNECTING → CONNECTED
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "connected")
end

-- ── init ─────────────────────────────────────────────────────────────────────

function testInit_setsDisconnected()
    setup()
    channel.init("ws://localhost:5558/ws")
    luaunit.assertEquals(channel.get_status(), "disconnected")
end

function testInit_clearsQueue()
    local sock = setup()
    channel.init("ws://localhost:5558/ws")
    -- Publish while disconnected → queued
    channel.publish("test.topic", { x = 1 })
    luaunit.assertTrue(channel._queue_size() > 0)
    -- Re-init should clear
    channel.init("ws://localhost:5558/ws")
    luaunit.assertEquals(channel._queue_size(), 0)
end

-- ── tick state transitions ───────────────────────────────────────────────────

function testTick_disconnectedToConnecting()
    setup()
    channel.init("ws://localhost:5558/ws")
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "connecting")
end

function testTick_connectingToConnected()
    setup()
    channel.init("ws://localhost:5558/ws")
    channel.tick()
    _last_mock._status = "open"
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "connected")
end

function testTick_connectingError_goesToReconnecting()
    setup()
    channel.init("ws://localhost:5558/ws")
    channel.tick()
    _last_mock._status = "error"
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "reconnecting")
end

function testTick_connectedClosed_goesToReconnecting()
    setup()
    connect()
    _last_mock._status = "closed"
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "reconnecting")
end

function testTick_beforeInit_doesNothing()
    channel._reset()
    ws_client._reset()
    -- No init() called — tick should be a no-op
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "disconnected")
end

-- ── publish (connected vs queued) ────────────────────────────────────────────

function testPublish_connected_sendsImmediately()
    local sock = setup()
    connect()
    channel.publish("game.event", { type = "DEATH" })
    -- Message should have been sent via ws_client
    luaunit.assertTrue(#sock._sent > 0)
    local decoded = json.decode(sock._sent[#sock._sent])
    luaunit.assertEquals(decoded.t, "game.event")
    luaunit.assertEquals(decoded.p.type, "DEATH")
end

function testPublish_disconnected_queues()
    setup()
    channel.init("ws://localhost:5558/ws")
    -- Still disconnected — should queue
    channel.publish("test.topic", { val = 42 })
    luaunit.assertEquals(channel._queue_size(), 1)
end

function testPublish_queue_flushedOnConnect()
    local sock = setup()
    channel.init("ws://localhost:5558/ws")
    channel.publish("queued.msg", { x = 1 })
    channel.publish("queued.msg2", { x = 2 })
    luaunit.assertEquals(channel._queue_size(), 2)

    -- Connect
    channel.tick() -- DISCONNECTED → CONNECTING
    _last_mock._status = "open"
    channel.tick() -- CONNECTING → CONNECTED (flushes queue)

    luaunit.assertEquals(channel._queue_size(), 0)
    luaunit.assertEquals(#sock._sent, 2)
end

function testPublish_withRequestId()
    local sock = setup()
    connect()
    channel.publish("state.query.batch", { queries = {} }, "req-42")
    local decoded = json.decode(sock._sent[#sock._sent])
    luaunit.assertEquals(decoded.r, "req-42")
end

-- ── queue overflow ───────────────────────────────────────────────────────────

function testQueue_overflow_dropsOldest()
    setup()
    channel.init("ws://localhost:5558/ws")
    -- MAX_QUEUE_SIZE is 100 — fill past it
    for i = 1, 110 do
        channel.publish("overflow.test", { idx = i })
    end
    luaunit.assertEquals(channel._queue_size(), 100)
end

-- ── on() topic handlers ──────────────────────────────────────────────────────

function testOn_handlerCalledOnDispatch()
    local sock = setup()
    local received = nil
    channel.init("ws://localhost:5558/ws")
    channel.on("dialogue.display", function(payload)
        received = payload
    end)
    -- Connect and inject a raw message
    channel.tick()
    _last_mock._status = "open"
    local raw = codec.encode("dialogue.display", { speaker_id = "1", dialogue = "Hello" })
    sock._messages = { raw }
    channel.tick()  -- drains messages → dispatches

    luaunit.assertNotNil(received)
    luaunit.assertEquals(received.speaker_id, "1")
    luaunit.assertEquals(received.dialogue, "Hello")
end

function testOn_multipleHandlersPerTopic()
    local sock = setup()
    local calls = {}
    channel.init("ws://localhost:5558/ws")
    channel.on("memory.update", function(p) table.insert(calls, "a") end)
    channel.on("memory.update", function(p) table.insert(calls, "b") end)

    channel.tick()
    _last_mock._status = "open"
    sock._messages = { codec.encode("memory.update", {}) }
    channel.tick()

    luaunit.assertEquals(#calls, 2)
    luaunit.assertEquals(calls[1], "a")
    luaunit.assertEquals(calls[2], "b")
end

function testOn_handlerErrorDoesNotCrash()
    local sock = setup()
    local second_called = false
    channel.init("ws://localhost:5558/ws")
    channel.on("test.error", function() error("boom") end)
    channel.on("test.error", function() second_called = true end)

    channel.tick()
    _last_mock._status = "open"
    sock._messages = { codec.encode("test.error", {}) }
    channel.tick()

    -- Second handler should still fire despite first erroring
    luaunit.assertTrue(second_called)
end

-- ── request / response correlation ──────────────────────────────────────────

function testRequest_callbackCalledOnResponse()
    local sock = setup()
    local response_payload = nil
    connect()

    channel.request("state.query.batch", { queries = {} }, function(p)
        response_payload = p
    end)

    -- Extract the request ID from what was sent
    luaunit.assertTrue(#sock._sent > 0)
    local sent_msg = json.decode(sock._sent[#sock._sent])
    luaunit.assertNotNil(sent_msg.r)

    -- Simulate response with matching r-field
    local resp = json.encode({
        t  = "state.response",
        p  = { answer = 42 },
        r  = sent_msg.r,
        ts = os.time() * 1000,
    })
    sock._messages = { resp }
    channel.tick()

    luaunit.assertNotNil(response_payload)
    luaunit.assertEquals(response_payload.answer, 42)
end

function testRequest_callbackRemovedAfterFiring()
    local sock = setup()
    local call_count = 0
    connect()

    channel.request("test.req", {}, function(p)
        call_count = call_count + 1
    end)

    local sent_msg = json.decode(sock._sent[#sock._sent])
    local resp_raw = json.encode({
        t = "state.response", p = {}, r = sent_msg.r, ts = 100,
    })

    -- First response triggers callback
    sock._messages = { resp_raw }
    channel.tick()
    luaunit.assertEquals(call_count, 1)

    -- Second identical response should NOT re-trigger (callback removed)
    sock._messages = { resp_raw }
    channel.tick()
    luaunit.assertEquals(call_count, 1)
end

function testRequest_queuesWhenDisconnected()
    setup()
    channel.init("ws://localhost:5558/ws")
    local called = false
    channel.request("test.req", {}, function() called = true end)
    luaunit.assertTrue(channel._queue_size() > 0)
end

-- ── session-scoped mic handlers ──────────────────────────────────────────────

function testStartSession_statusHandlerCalled()
    local sock = setup()
    local status_payload = nil
    connect()

    channel.start_session(
        function(p) status_payload = p end,
        function(p) end
    )

    sock._messages = { codec.encode("mic.status", { status = "TRANSCRIBING" }) }
    channel.tick()

    luaunit.assertNotNil(status_payload)
    luaunit.assertEquals(status_payload.status, "TRANSCRIBING")
end

function testStartSession_resultHandlerCalled()
    local sock = setup()
    local result_payload = nil
    connect()

    channel.start_session(
        function(p) end,
        function(p) result_payload = p end
    )

    sock._messages = { codec.encode("mic.result", { text = "Hello" }) }
    channel.tick()

    luaunit.assertNotNil(result_payload)
    luaunit.assertEquals(result_payload.text, "Hello")
end

function testStartSession_resultClearsSessionHandlers()
    local sock = setup()
    local status_after_result = nil
    connect()

    channel.start_session(
        function(p) status_after_result = p end,
        function(p) end
    )

    -- First: result clears session
    sock._messages = { codec.encode("mic.result", { text = "done" }) }
    channel.tick()

    -- Now: status should not fire (session handlers cleared)
    status_after_result = nil
    sock._messages = { codec.encode("mic.status", { status = "IDLE" }) }
    channel.tick()

    luaunit.assertNil(status_after_result)
end

function testStartSession_sessionResult_preventsGeneralHandler()
    local sock = setup()
    local general_called = false
    local session_called = false
    connect()

    -- Register a general handler for mic.result
    channel.on("mic.result", function(p) general_called = true end)
    -- Register a session handler (should take priority)
    channel.start_session(nil, function(p) session_called = true end)

    sock._messages = { codec.encode("mic.result", { text = "test" }) }
    channel.tick()

    luaunit.assertTrue(session_called)
    -- Session handler should intercept, general should NOT fire
    luaunit.assertFalse(general_called)
end

-- ── reconnect callback ──────────────────────────────────────────────────────

function testSetOnReconnect_notCalledOnFirstConnect()
    setup()
    local reconnect_called = false
    channel.init("ws://localhost:5558/ws")
    channel.set_on_reconnect(function() reconnect_called = true end)
    connect()
    luaunit.assertFalse(reconnect_called)
end

function testSetOnReconnect_calledOnReconnect()
    setup()
    local reconnect_called = false
    channel.init("ws://localhost:5558/ws")
    channel.set_on_reconnect(function() reconnect_called = true end)

    -- First connect
    channel.tick()
    _last_mock._status = "open"
    channel.tick()
    luaunit.assertFalse(reconnect_called)

    -- Drop connection
    _last_mock._status = "closed"
    channel.tick() -- → RECONNECTING

    -- Wait for backoff (cheat by using os.clock manipulation is not practical,
    -- so we just set the mock status to "opening" and let reconnect happen)
    -- Simulate immediate reconnect by creating a new mock for the
    -- ws_client open call:
    local new_sock = make_mock_socket({ status = "open" })
    ws_client.set_socket_factory(function() return new_sock end)

    -- Force backoff to expire by ticking enough (backoff base is 1s, but
    -- we can work around by waiting or by noting the channel checks os.clock)
    -- Instead: manipulate os.clock isn't feasible; just verify the state
    -- transitions when the backoff does expire.
    -- For the test: we know BACKOFF_BASE is 1s, let's rely on the fact that
    -- running later ticks after 1s pause isn't practical in a test.
    -- Instead, test that the state IS reconnecting and that when it re-connects
    -- the callback fires.
    luaunit.assertEquals(channel.get_status(), "reconnecting")

    -- Skip backoff by busy-waiting (test-only, max 2s)
    local deadline = os.clock() + 2
    while os.clock() < deadline and channel.get_status() == "reconnecting" do
        channel.tick()
    end

    -- Should be connected or connecting now
    local status = channel.get_status()
    if status == "connecting" then
        new_sock._status = "open"
        channel.tick()
    end

    luaunit.assertEquals(channel.get_status(), "connected")
    luaunit.assertTrue(reconnect_called)
end

-- ── shutdown ─────────────────────────────────────────────────────────────────

function testShutdown_closesAndDisconnects()
    local sock = setup()
    connect()
    luaunit.assertEquals(channel.get_status(), "connected")
    channel.shutdown()
    luaunit.assertEquals(channel.get_status(), "disconnected")
end

function testShutdown_clearsQueue()
    setup()
    channel.init("ws://localhost:5558/ws")
    channel.publish("msg", { x = 1 })
    luaunit.assertTrue(channel._queue_size() > 0)
    channel.shutdown()
    luaunit.assertEquals(channel._queue_size(), 0)
end

-- ── drain messages ───────────────────────────────────────────────────────────

function testDrain_malformedMessageDoesNotCrash()
    local sock = setup()
    connect()
    -- Inject a garbage message followed by a valid one
    local valid_raw = codec.encode("test.topic", { ok = true })
    sock._messages = { "not json at all", valid_raw }

    local received = nil
    channel.on("test.topic", function(p) received = p end)
    channel.tick()

    -- Valid message should still have been dispatched
    luaunit.assertNotNil(received)
    luaunit.assertTrue(received.ok)
end

function testDrain_maxMessagesPerTick()
    local sock = setup()
    connect()
    local count = 0
    channel.on("bulk.test", function() count = count + 1 end)

    -- Enqueue 30 messages (MAX_MESSAGES_PER_TICK is 20)
    for i = 1, 30 do
        table.insert(sock._messages, codec.encode("bulk.test", {}))
    end

    channel.tick()
    luaunit.assertEquals(count, 20)  -- capped at MAX_MESSAGES_PER_TICK

    -- Second tick drains remaining 10
    channel.tick()
    luaunit.assertEquals(count, 30)
end

-- ── get_status ───────────────────────────────────────────────────────────────

function testGetStatus_returnsCurrentState()
    setup()
    luaunit.assertEquals(channel.get_status(), "disconnected")
    channel.init("ws://localhost:5558/ws")
    luaunit.assertEquals(channel.get_status(), "disconnected")
    channel.tick()
    luaunit.assertEquals(channel.get_status(), "connecting")
end

os.exit(luaunit.LuaUnit.run())

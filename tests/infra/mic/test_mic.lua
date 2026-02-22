package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
local luaunit = require('tests.utils.luaunit')

-- ── Mock dependencies before loading microphone ─────────────────────────────

local bridge_calls = {}  -- records publish/register/unregister calls
local registered_handlers = {}

local mock_bridge = {}
function mock_bridge.publish(topic, payload)
    table.insert(bridge_calls, { fn = "publish", topic = topic, payload = payload })
end
function mock_bridge.register_handler(topic, fn)
    table.insert(bridge_calls, { fn = "register_handler", topic = topic })
    registered_handlers[topic] = fn
end
function mock_bridge.unregister_handler(topic)
    table.insert(bridge_calls, { fn = "unregister_handler", topic = topic })
    registered_handlers[topic] = nil
end

local mock_config = {}
function mock_config.language_short() return "en" end

local mock_logger = {}
function mock_logger.info(...) end
function mock_logger.debug(...) end
function mock_logger.error(...) end

package.preload["infra.zmq.bridge"]  = function() return mock_bridge end
package.preload["interface.config"]  = function() return mock_config end
package.preload["framework.logger"]  = function() return mock_logger end

local mic = require('infra.mic.microphone')

-- ── Helpers ──────────────────────────────────────────────────────────────────

local function reset()
    bridge_calls = {}
    registered_handlers = {}
    -- Force internal mic_on state off by calling stop if on
    if mic.is_mic_on() then
        mic.stop()
        bridge_calls = {}
    end
end

local function published_topics()
    local topics = {}
    for _, c in ipairs(bridge_calls) do
        if c.fn == "publish" then table.insert(topics, c.topic) end
    end
    return topics
end

-- ── Tests ────────────────────────────────────────────────────────────────────

function testIsOffInitially()
    luaunit.assertFalse(mic.is_mic_on())
end

function testStartSetsMicOn()
    reset()
    mic.start("Recording test prompt")
    luaunit.assertTrue(mic.is_mic_on())
end

function testStartPublishesMicStart()
    reset()
    mic.start("my prompt")
    luaunit.assertItemsEquals(published_topics(), { "mic.start" })
end

function testStartPublishesPromptAndLang()
    reset()
    mic.start("hello world")
    local pub
    for _, c in ipairs(bridge_calls) do
        if c.fn == "publish" and c.topic == "mic.start" then pub = c end
    end
    luaunit.assertNotNil(pub)
    luaunit.assertEquals(pub.payload.prompt, "hello world")
    luaunit.assertEquals(pub.payload.lang, "en")
end

function testStartRegistersHandlers()
    reset()
    mic.start("prompt")
    luaunit.assertNotNil(registered_handlers["mic.status"])
    luaunit.assertNotNil(registered_handlers["mic.result"])
end

function testStartWhenAlreadyOnIsNoop()
    reset()
    mic.start("first")
    bridge_calls = {}
    mic.start("second")  -- should be ignored
    luaunit.assertEquals(#bridge_calls, 0)
    luaunit.assertTrue(mic.is_mic_on())
end

function testStopSetsMicOff()
    reset()
    mic.start("prompt")
    mic.stop()
    luaunit.assertFalse(mic.is_mic_on())
end

function testStopPublishesMicStop()
    reset()
    mic.start("prompt")
    bridge_calls = {}
    mic.stop()
    luaunit.assertItemsEquals(published_topics(), { "mic.stop" })
end

function testStopUnregistersHandlers()
    reset()
    mic.start("prompt")
    mic.stop()
    luaunit.assertNil(registered_handlers["mic.status"])
    luaunit.assertNil(registered_handlers["mic.result"])
end

function testStopWhenAlreadyOffIsNoop()
    reset()
    luaunit.assertFalse(mic.is_mic_on())
    mic.stop()
    luaunit.assertEquals(#bridge_calls, 0)
end

function testOnResultCallbackFiredAndMicTurnedOff()
    reset()
    local received_text = nil
    mic.start("prompt", {
        on_result = function(text) received_text = text end
    })
    local handler = registered_handlers["mic.result"]
    luaunit.assertNotNil(handler)
    handler("mic.result", { text = "Hello Zone" })
    luaunit.assertEquals(received_text, "Hello Zone")
    luaunit.assertFalse(mic.is_mic_on())
end

function testOnStatusCallbackFired()
    reset()
    local received_status = nil
    mic.start("prompt", {
        on_status = function(s) received_status = s end
    })
    local handler = registered_handlers["mic.status"]
    luaunit.assertNotNil(handler)
    handler("mic.status", { status = "LISTENING" })
    luaunit.assertEquals(received_status, "LISTENING")
    luaunit.assertTrue(mic.is_mic_on())
end

os.exit(luaunit.LuaUnit.run())

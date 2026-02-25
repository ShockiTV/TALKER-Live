package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
local luaunit = require('tests.utils.luaunit')

-- ── Mock dependencies before loading microphone ─────────────────────────────

local publish_calls = {}   -- records publish(topic, payload) calls
local session_on_status = nil
local session_on_result = nil
local session_count = 0

local mock_channel = {}
function mock_channel.publish(topic, payload)
    table.insert(publish_calls, { topic = topic, payload = payload })
end
function mock_channel.start_session(on_status, on_result)
    session_count = session_count + 1
    session_on_status = on_status
    session_on_result = on_result
end

local mock_config = {}
function mock_config.language_short() return "en" end

local mock_logger = {}
function mock_logger.info(...) end
function mock_logger.debug(...) end
function mock_logger.error(...) end

package.preload["infra.bridge.channel"]  = function() return mock_channel end
package.preload["interface.config"]  = function() return mock_config end
package.preload["framework.logger"]  = function() return mock_logger end

local mic = require('infra.mic.microphone')

-- ── Helpers ──────────────────────────────────────────────────────────────────

local function reset()
    publish_calls = {}
    session_on_status = nil
    session_on_result = nil
    session_count = 0
    -- Force internal mic_on state off by calling stop if on
    if mic.is_mic_on() then
        mic.stop()
        publish_calls = {}
        session_count = 0
    end
end

local function published_topics()
    local topics = {}
    for _, c in ipairs(publish_calls) do
        table.insert(topics, c.topic)
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
    for _, c in ipairs(publish_calls) do
        if c.topic == "mic.start" then pub = c end
    end
    luaunit.assertNotNil(pub)
    luaunit.assertEquals(pub.payload.prompt, "hello world")
    luaunit.assertEquals(pub.payload.lang, "en")
end

function testStartRegistersSession()
    reset()
    mic.start("prompt")
    luaunit.assertNotNil(session_on_status)
    luaunit.assertNotNil(session_on_result)
    luaunit.assertEquals(session_count, 1)
end

function testStartWhenAlreadyOnIsNoop()
    reset()
    mic.start("first")
    publish_calls = {}
    session_count = 0
    mic.start("second")  -- should be ignored
    luaunit.assertEquals(#publish_calls, 0)
    luaunit.assertEquals(session_count, 0)
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
    publish_calls = {}
    mic.stop()
    luaunit.assertItemsEquals(published_topics(), { "mic.stop" })
end

function testStopWhenAlreadyOffIsNoop()
    reset()
    luaunit.assertFalse(mic.is_mic_on())
    mic.stop()
    luaunit.assertEquals(#publish_calls, 0)
end

function testOnResultCallbackFiredAndMicTurnedOff()
    reset()
    local received_text = nil
    mic.start("prompt", {
        on_result = function(text) received_text = text end
    })
    luaunit.assertNotNil(session_on_result)
    session_on_result("Hello Zone")
    luaunit.assertEquals(received_text, "Hello Zone")
    luaunit.assertFalse(mic.is_mic_on())
end

function testOnStatusCallbackFired()
    reset()
    local received_status = nil
    mic.start("prompt", {
        on_status = function(s) received_status = s end
    })
    luaunit.assertNotNil(session_on_status)
    session_on_status("LISTENING")
    luaunit.assertEquals(received_status, "LISTENING")
    luaunit.assertTrue(mic.is_mic_on())
end

os.exit(luaunit.LuaUnit.run())

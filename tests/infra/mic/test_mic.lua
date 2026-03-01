package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
local luaunit = require('tests.utils.luaunit')

-- ── Mock dependencies before loading microphone ─────────────────────────────

local publish_calls = {}   -- records publish(topic, payload) calls

local mock_channel = {}
function mock_channel.publish(topic, payload)
    table.insert(publish_calls, { topic = topic, payload = payload })
end

local mock_logger = {}
function mock_logger.info(...) end
function mock_logger.debug(...) end
function mock_logger.error(...) end

package.preload["infra.bridge.channel"]  = function() return mock_channel end
package.preload["framework.logger"]  = function() return mock_logger end

local mic = require('infra.mic.microphone')

-- ── Helpers ──────────────────────────────────────────────────────────────────

local function reset()
    publish_calls = {}
    -- Force internal _recording off
    if mic.is_recording() then
        mic.stop_capture()
        publish_calls = {}
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

function testIsNotRecordingInitially()
    luaunit.assertFalse(mic.is_recording())
end

function testStartCaptureRecording()
    reset()
    mic.start_capture("dialogue")
    luaunit.assertTrue(mic.is_recording())
end

function testStartCapturePublishesMicStart()
    reset()
    mic.start_capture("dialogue")
    luaunit.assertItemsEquals(published_topics(), { "mic.start" })
end

function testStartCapturePublishesContextType()
    reset()
    mic.start_capture("whisper")
    local pub
    for _, c in ipairs(publish_calls) do
        if c.topic == "mic.start" then pub = c end
    end
    luaunit.assertNotNil(pub)
    luaunit.assertEquals(pub.payload.context_type, "whisper")
end

function testStartCaptureDefaultsToDialogue()
    reset()
    mic.start_capture()  -- no context_type
    local pub
    for _, c in ipairs(publish_calls) do
        if c.topic == "mic.start" then pub = c end
    end
    luaunit.assertNotNil(pub)
    luaunit.assertEquals(pub.payload.context_type, "dialogue")
end

function testStartCaptureWhenAlreadyRecordingIsNoop()
    reset()
    mic.start_capture("dialogue")
    publish_calls = {}
    mic.start_capture("dialogue")  -- should be ignored
    luaunit.assertEquals(#publish_calls, 0)
    luaunit.assertTrue(mic.is_recording())
end

function testStopCaptureEndsRecording()
    reset()
    mic.start_capture("dialogue")
    mic.stop_capture()
    luaunit.assertFalse(mic.is_recording())
end

function testStopCapturePublishesMicStop()
    reset()
    mic.start_capture("dialogue")
    publish_calls = {}
    mic.stop_capture()
    luaunit.assertItemsEquals(published_topics(), { "mic.stop" })
end

function testStopCaptureWhenNotRecordingIsNoop()
    reset()
    luaunit.assertFalse(mic.is_recording())
    mic.stop_capture()
    luaunit.assertEquals(#publish_calls, 0)
end

function testStartAfterStopWorks()
    reset()
    mic.start_capture("dialogue")
    mic.stop_capture()
    publish_calls = {}
    mic.start_capture("dialogue")
    luaunit.assertTrue(mic.is_recording())
    luaunit.assertItemsEquals(published_topics(), { "mic.start" })
end

function testOnStoppedResetsRecording()
    reset()
    mic.start_capture("dialogue")
    luaunit.assertTrue(mic.is_recording())
    mic.on_stopped()
    luaunit.assertFalse(mic.is_recording())
end

function testOnStoppedNoPublish()
    reset()
    mic.start_capture("dialogue")
    publish_calls = {}
    mic.on_stopped()
    -- on_stopped should NOT publish anything (bridge already knows)
    luaunit.assertEquals(#publish_calls, 0)
end

function testOnStoppedWhenNotRecordingIsNoop()
    reset()
    mic.on_stopped()
    luaunit.assertEquals(#publish_calls, 0)
end

function testStartAfterOnStoppedWorks()
    reset()
    mic.start_capture("dialogue")
    mic.on_stopped()
    publish_calls = {}
    mic.start_capture("dialogue")
    luaunit.assertTrue(mic.is_recording())
    luaunit.assertItemsEquals(published_topics(), { "mic.start" })
end

os.exit(luaunit.LuaUnit.run())

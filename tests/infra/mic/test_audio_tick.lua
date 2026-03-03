package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
local luaunit = require('tests.utils.luaunit')

-- ── Mock dependencies ───────────────────────────────────────────────────────

-- mock ffi (used by audio_tick for ffi.string)
local mock_ffi = {}
function mock_ffi.string(ptr, len)
    -- In tests, ptr IS the string data (we fake it)
    return ptr
end
package.preload["ffi"] = function() return mock_ffi end

-- mock talker_audio_ffi
local poll_returns  = {}  -- queue of {n, data} pairs
local poll_index    = 0
local ta_available  = true

local mock_ta = {}
function mock_ta.is_available() return ta_available end
function mock_ta.poll()
    poll_index = poll_index + 1
    local entry = poll_returns[poll_index]
    if not entry then return 0, nil end
    return entry.n, entry.data
end
package.preload["infra.mic.talker_audio_ffi"] = function() return mock_ta end

-- mock microphone
local mic_session   = 0
local mic_recording = false
local mic_stopped_calls = 0
local mic_ctx_type = "dialogue"

local mock_mic = {}
function mock_mic.session_id() return mic_session end
function mock_mic.is_recording() return mic_recording end
function mock_mic.context_type() return mic_ctx_type end
function mock_mic.on_stopped()
    mic_stopped_calls = mic_stopped_calls + 1
    mic_recording = false
end
package.preload["infra.mic.microphone"] = function() return mock_mic end

-- mock bridge_channel
local publish_calls = {}
local mock_channel = {}
function mock_channel.publish(topic, payload)
    table.insert(publish_calls, { topic = topic, payload = payload })
end
package.preload["infra.bridge.channel"] = function() return mock_channel end

-- mock base64
local mock_base64 = {}
function mock_base64.encode(data)
    return "B64:" .. (data or "")
end
package.preload["infra.base64"] = function() return mock_base64 end

-- mock logger
local mock_logger = {}
function mock_logger.info(...) end
function mock_logger.debug(...) end
function mock_logger.error(...) end
package.preload["framework.logger"] = function() return mock_logger end

-- Now require audio_tick
local audio_tick = require("infra.mic.audio_tick")

-- ── Helpers ──────────────────────────────────────────────────────────────────

local function reset()
    publish_calls = {}
    poll_returns = {}
    poll_index = 0
    mic_session = 0
    mic_recording = false
    mic_stopped_calls = 0
    mic_ctx_type = "dialogue"
    ta_available = true
    audio_tick._reset()
end

local function set_poll_returns(list)
    poll_returns = list
    poll_index = 0
end

local function published_topics()
    local topics = {}
    for _, c in ipairs(publish_calls) do
        table.insert(topics, c.topic)
    end
    return topics
end

-- ── Tests ────────────────────────────────────────────────────────────────────

function testTickNoopWhenDllUnavailable()
    reset()
    ta_available = false
    mic_session = 1
    mic_recording = true
    set_poll_returns({{ n = 100, data = "frame1" }})
    audio_tick.tick()
    luaunit.assertEquals(#publish_calls, 0)
end

function testTickNoopWhenNoActiveSession()
    reset()
    audio_tick.tick()
    luaunit.assertEquals(#publish_calls, 0)
end

function testTickDrainsFramesAndPublishesChunks()
    reset()
    mic_session = 1
    mic_recording = true
    set_poll_returns({
        { n = 50, data = "opus_frame_1" },
        { n = 60, data = "opus_frame_2" },
        { n = 0,  data = nil },
    })
    audio_tick.tick()
    luaunit.assertEquals(#publish_calls, 2)

    -- Verify first chunk
    local c1 = publish_calls[1]
    luaunit.assertEquals(c1.topic, "mic.audio.chunk")
    luaunit.assertEquals(c1.payload.format, "opus")
    luaunit.assertEquals(c1.payload.seq, 1)
    luaunit.assertEquals(c1.payload.session_id, 1)
    luaunit.assertEquals(c1.payload.audio_b64, "B64:opus_frame_1")

    -- Verify second chunk
    local c2 = publish_calls[2]
    luaunit.assertEquals(c2.payload.seq, 2)
    luaunit.assertEquals(c2.payload.audio_b64, "B64:opus_frame_2")
end

function testTickSeqIncrementsCrossTicks()
    reset()
    mic_session = 1
    mic_recording = true

    -- Tick 1: one frame
    set_poll_returns({
        { n = 50, data = "frame1" },
        { n = 0,  data = nil },
    })
    audio_tick.tick()

    -- Tick 2: another frame
    set_poll_returns({
        { n = 50, data = "frame2" },
        { n = 0,  data = nil },
    })
    audio_tick.tick()

    luaunit.assertEquals(#publish_calls, 2)
    luaunit.assertEquals(publish_calls[1].payload.seq, 1)
    luaunit.assertEquals(publish_calls[2].payload.seq, 2)
end

function testVadAutoStopSendsEndAndNotifiesRecorder()
    reset()
    mic_session = 1
    mic_recording = true

    local vad_called = false
    audio_tick.set_on_vad_stopped(function() vad_called = true end)

    set_poll_returns({
        { n = 50, data = "frame1" },
        { n = -1, data = nil },  -- VAD auto-stop
    })
    audio_tick.tick()

    -- Should have 1 chunk + 1 mic.audio.end
    local topics = published_topics()
    luaunit.assertEquals(topics[1], "mic.audio.chunk")
    luaunit.assertEquals(topics[2], "mic.audio.end")

    -- mic.audio.end payload
    local end_msg = publish_calls[2]
    luaunit.assertEquals(end_msg.payload.session_id, 1)
    luaunit.assertEquals(end_msg.payload.context.type, "dialogue")

    -- Callbacks
    luaunit.assertTrue(vad_called)
    luaunit.assertEquals(mic_stopped_calls, 1)
end

function testManualStopSendsEndButNoVadCallback()
    reset()
    mic_session = 1
    mic_recording = true

    local vad_called = false
    audio_tick.set_on_vad_stopped(function() vad_called = true end)

    set_poll_returns({
        { n = 50, data = "frame1" },
        { n = -2, data = nil },  -- manual stop
    })
    audio_tick.tick()

    local topics = published_topics()
    luaunit.assertEquals(topics[1], "mic.audio.chunk")
    luaunit.assertEquals(topics[2], "mic.audio.end")

    -- VAD callback should NOT fire for manual stop
    luaunit.assertFalse(vad_called)
    -- mic.on_stopped() should NOT be called for manual stop (already handled)
    luaunit.assertEquals(mic_stopped_calls, 0)
end

function testNewSessionResetsSeq()
    reset()
    mic_session = 1
    mic_recording = true

    -- Session 1: drain some frames
    set_poll_returns({
        { n = 50, data = "s1f1" },
        { n = -2, data = nil },
    })
    audio_tick.tick()
    luaunit.assertEquals(publish_calls[1].payload.seq, 1)

    -- Session 2: seq should reset
    publish_calls = {}
    mic_session = 2
    mic_recording = true
    set_poll_returns({
        { n = 50, data = "s2f1" },
        { n = 0,  data = nil },
    })
    audio_tick.tick()
    luaunit.assertEquals(publish_calls[1].payload.seq, 1)
    luaunit.assertEquals(publish_calls[1].payload.session_id, 2)
end

function testVadStoppedWithWhisperContext()
    reset()
    mic_session = 1
    mic_recording = true
    mic_ctx_type = "whisper"

    set_poll_returns({
        { n = -1, data = nil },
    })
    audio_tick.tick()

    local end_msg = publish_calls[1]
    luaunit.assertEquals(end_msg.topic, "mic.audio.end")
    luaunit.assertEquals(end_msg.payload.context.type, "whisper")
end

function testNoPollAfterDrainComplete()
    reset()
    mic_session = 1
    mic_recording = true

    set_poll_returns({
        { n = -2, data = nil },  -- immediate stop (no frames)
    })
    audio_tick.tick()

    -- After drain complete, next tick should not publish anything
    publish_calls = {}
    set_poll_returns({
        { n = 50, data = "should_not_appear" },
    })
    audio_tick.tick()

    -- No publishes because _draining was set to false and session hasn't changed
    luaunit.assertEquals(#publish_calls, 0)
end

function testVadCallbackErrorDoesNotCrash()
    reset()
    mic_session = 1
    mic_recording = true

    audio_tick.set_on_vad_stopped(function() error("boom") end)

    set_poll_returns({
        { n = -1, data = nil },
    })
    -- Should not throw
    audio_tick.tick()

    -- mic.audio.end should still have been sent
    luaunit.assertEquals(publish_calls[1].topic, "mic.audio.end")
end

os.exit(luaunit.LuaUnit.run())

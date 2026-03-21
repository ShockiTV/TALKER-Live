package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
local luaunit = require('tests.utils.luaunit')

-- ── Mocks ────────────────────────────────────────────────────────────────────

local publish_calls = {}
local on_handlers   = {}   -- topic → { fn, ... }
local hud_messages  = {}

-- mock bridge_channel
local mock_channel = {}
function mock_channel.publish(topic, payload)
    table.insert(publish_calls, { topic = topic, payload = payload })
end
function mock_channel.on(topic, fn)
    if not on_handlers[topic] then on_handlers[topic] = {} end
    table.insert(on_handlers[topic], fn)
end

-- mock mic — tracks calls, delegates to real logic via thin state
local mic_recording  = false
local mic_start_calls = 0
local mic_stop_calls  = 0
local mock_mic = {}
function mock_mic.is_recording() return mic_recording end
function mock_mic.is_available() return true end
function mock_mic.session_id() return 1 end
function mock_mic.context_type() return "dialogue" end
function mock_mic.start_capture(ctx)
    mic_start_calls = mic_start_calls + 1
    mic_recording = true
    return true
end
function mock_mic.stop_capture()
    mic_stop_calls = mic_stop_calls + 1
    mic_recording = false
end
function mock_mic.on_stopped()
    mic_recording = false
end

-- mock audio_tick — capture the VAD callback for tests
local vad_stopped_callback = nil
local mock_audio_tick = {}
function mock_audio_tick.set_on_vad_stopped(fn)
    vad_stopped_callback = fn
end
function mock_audio_tick.tick() end
function mock_audio_tick._reset()
    vad_stopped_callback = nil
end

-- mock engine
local mock_engine = {}
function mock_engine.display_hud_message(msg, dur)
    table.insert(hud_messages, msg)
end

-- mock game_adapter
local mock_game_adapter = {}
function mock_game_adapter.get_characters_near_player()
    return { { name = "Sidorovich" }, { name = "Wolf" } }
end

-- mock json
local mock_json = {}
function mock_json.utf8_to_codepage(s) return s end

-- mock logger
local mock_logger = {}
function mock_logger.info(...) end
function mock_logger.debug(...) end
function mock_logger.error(...) end
function mock_logger.warn(...) end

-- Wire up mocks
package.preload["infra.bridge.channel"]     = function() return mock_channel end
package.preload["infra.mic.microphone"]     = function() return mock_mic end
package.preload["infra.mic.audio_tick"]     = function() return mock_audio_tick end
package.preload["interface.engine"]         = function() return mock_engine end
package.preload["infra.game_adapter"]       = function() return mock_game_adapter end
package.preload["infra.HTTP.json"]          = function() return mock_json end
package.preload["framework.logger"]         = function() return mock_logger end

local recorder = require('interface.recorder')

-- ── Helpers ──────────────────────────────────────────────────────────────────

local function reset()
    publish_calls   = {}
    hud_messages    = {}
    mic_start_calls = 0
    mic_stop_calls  = 0
    mic_recording   = false
    vad_stopped_callback = nil
    recorder._reset()  -- reset internal state to idle
end

--- Simulate mic.result arriving from service via bridge
local function deliver_mic_result(text)
    local fns = on_handlers["mic.result"]
    if fns then
        for _, fn in ipairs(fns) do fn({ text = text }) end
    end
end

--- Simulate mic.status arriving from service via bridge
local function deliver_mic_status(status)
    local fns = on_handlers["mic.status"]
    if fns then
        for _, fn in ipairs(fns) do fn({ status = status }) end
    end
end

-- ── Tests ────────────────────────────────────────────────────────────────────

function testToggleFromIdleStartsCapture()
    reset()
    recorder.toggle(function() end)
    luaunit.assertEquals(recorder.state(), "capturing")
    luaunit.assertEquals(mic_start_calls, 1)
end

function testToggleFromCapturingStopsCapture()
    reset()
    recorder.toggle(function() end)           -- idle → capturing
    recorder.toggle(function() end)           -- capturing → transcribing
    luaunit.assertEquals(recorder.state(), "transcribing")
    luaunit.assertEquals(mic_stop_calls, 1)
end

function testToggleFromTranscribingStartsNewCapture()
    reset()
    recorder.toggle(function() end)           -- idle → capturing
    recorder.toggle(function() end)           -- capturing → transcribing
    mic_start_calls = 0
    recorder.toggle(function() end)           -- transcribing → capturing
    luaunit.assertEquals(recorder.state(), "capturing")
    luaunit.assertEquals(mic_start_calls, 1)
end

function testMicResultDeliversCallback()
    reset()
    local received = nil
    local cb = function(text) received = text end
    recorder.toggle(cb)                       -- idle → capturing
    recorder.toggle(cb)                       -- capturing → transcribing
    deliver_mic_result("Hello Stalker")
    luaunit.assertEquals(received, "Hello Stalker")
end

function testMicResultTransitionsToIdle()
    reset()
    recorder.toggle(function() end)           -- idle → capturing
    recorder.toggle(function() end)           -- capturing → transcribing
    deliver_mic_result("Hello")
    luaunit.assertEquals(recorder.state(), "idle")
end

function testMicResultDuringCapturingStaysCapturing()
    reset()
    recorder.toggle(function() end)           -- idle → capturing
    recorder.toggle(function() end)           -- capturing → transcribing
    recorder.toggle(function() end)           -- transcribing → capturing (new)
    -- Old transcription result arrives — state should stay "capturing"
    deliver_mic_result("old transcription")
    luaunit.assertEquals(recorder.state(), "capturing")
end

function testMicResultDuringCapturingStillDeliversCallback()
    reset()
    local received = nil
    local cb = function(text) received = text end
    recorder.toggle(cb)                       -- idle → capturing
    recorder.toggle(cb)                       -- capturing → transcribing
    recorder.toggle(cb)                       -- transcribing → capturing
    deliver_mic_result("old result")
    luaunit.assertEquals(received, "old result")
end

function testEmptyResultDoesNotFireCallback()
    reset()
    local called = false
    recorder.toggle(function() called = true end)
    recorder.toggle(function() called = true end)
    deliver_mic_result("")
    luaunit.assertFalse(called)
end


function testHudMessagesOnToggle()
    reset()
    recorder.toggle(function() end)           -- idle → capturing
    luaunit.assertTrue(#hud_messages > 0)
    local last = hud_messages[#hud_messages]
    luaunit.assertEquals(last, "RECORDING")

    hud_messages = {}
    recorder.toggle(function() end)           -- capturing → transcribing
    last = hud_messages[#hud_messages]
    luaunit.assertEquals(last, "TRANSCRIBING")
end

function testMicStatusSuppressedDuringCapture()
    -- HUD priority: RECORDING beats any mic.status from background transcription
    reset()
    recorder.toggle(function() end)           -- idle → capturing
    hud_messages = {}
    deliver_mic_status("TRANSCRIBING")        -- old session's status
    -- Should NOT appear in HUD because we're actively capturing
    luaunit.assertEquals(#hud_messages, 0)
end

function testMicStatusShownWhenNotCapturing()
    reset()
    recorder.toggle(function() end)           -- idle → capturing
    recorder.toggle(function() end)           -- capturing → transcribing
    hud_messages = {}
    deliver_mic_status("PROCESSING")
    local found = false
    for _, msg in ipairs(hud_messages) do
        if msg == "PROCESSING" then found = true end
    end
    luaunit.assertTrue(found)
end

function testFullCycleIdleToCaptureToTranscribeToIdle()
    reset()
    local results = {}
    local cb = function(text) table.insert(results, text) end

    recorder.toggle(cb)                       -- idle → capturing
    luaunit.assertEquals(recorder.state(), "capturing")

    recorder.toggle(cb)                       -- capturing → transcribing
    luaunit.assertEquals(recorder.state(), "transcribing")

    deliver_mic_result("Player said hello")
    luaunit.assertEquals(recorder.state(), "idle")
    luaunit.assertEquals(#results, 1)
    luaunit.assertEquals(results[1], "Player said hello")
end

function testOverlappingSessions()
    reset()
    local results = {}
    local cb = function(text) table.insert(results, text) end

    -- Session 1: capture → transcribe
    recorder.toggle(cb)                       -- idle → capturing
    recorder.toggle(cb)                       -- capturing → transcribing

    -- Session 2: start new capture during transcription
    recorder.toggle(cb)                       -- transcribing → capturing

    -- Old transcription finishes (session 1 result)
    deliver_mic_result("from session 1")
    luaunit.assertEquals(#results, 1)
    luaunit.assertEquals(recorder.state(), "capturing")  -- still in new capture

    -- Session 2: stop capture → transcribe
    recorder.toggle(cb)                       -- capturing → transcribing
    deliver_mic_result("from session 2")
    luaunit.assertEquals(#results, 2)
    luaunit.assertEquals(recorder.state(), "idle")
end

-- ── VAD (silence detection) scenarios ────────────────────────────────────────

function testVadStoppedTransitionsToTranscribing()
    reset()
    recorder.toggle(function() end)           -- idle → capturing
    recorder.on_vad_stopped()
    luaunit.assertEquals(recorder.state(), "transcribing")
end

function testVadStoppedThenResultDeliversCallback()
    reset()
    local received = nil
    local cb = function(text) received = text end
    recorder.toggle(cb)                       -- idle → capturing
    recorder.on_vad_stopped()                 -- VAD → transcribing
    deliver_mic_result("VAD transcription")
    luaunit.assertEquals(received, "VAD transcription")
    luaunit.assertEquals(recorder.state(), "idle")
end

function testVadThenKeyPressStartsNewCapture()
    reset()
    recorder.toggle(function() end)           -- idle → capturing
    recorder.on_vad_stopped()                 -- VAD → transcribing
    mic_start_calls = 0
    recorder.toggle(function() end)           -- transcribing → capturing
    luaunit.assertEquals(recorder.state(), "capturing")
    luaunit.assertEquals(mic_start_calls, 1)
end

function testVadFullCycle()
    -- Capture → VAD stops → transcription → idle → new capture
    reset()
    local results = {}
    local cb = function(text) table.insert(results, text) end

    recorder.toggle(cb)                       -- idle → capturing
    recorder.on_vad_stopped()                 -- VAD → transcribing
    deliver_mic_result("first")               -- → idle
    luaunit.assertEquals(recorder.state(), "idle")

    recorder.toggle(cb)                       -- idle → capturing
    recorder.on_vad_stopped()                 -- VAD → transcribing
    deliver_mic_result("second")              -- → idle
    luaunit.assertEquals(#results, 2)
    luaunit.assertEquals(results[1], "first")
    luaunit.assertEquals(results[2], "second")
end

function testVadOverlapWithNewCapture()
    -- VAD ends session 1, user starts session 2 during transcription
    -- Both results should be delivered
    reset()
    local results = {}
    local cb = function(text) table.insert(results, text) end

    recorder.toggle(cb)                       -- idle → capturing
    recorder.on_vad_stopped()                 -- VAD → transcribing
    recorder.toggle(cb)                       -- transcribing → capturing (new)
    deliver_mic_result("from session 1")      -- old transcription finishes
    luaunit.assertEquals(#results, 1)
    luaunit.assertEquals(recorder.state(), "capturing")  -- still in new capture
end

function testVadStoppedShowsTranscribingHud()
    reset()
    hud_messages = {}
    recorder.toggle(function() end)           -- idle → capturing
    hud_messages = {}  -- clear RECORDING
    recorder.on_vad_stopped()
    local found = false
    for _, msg in ipairs(hud_messages) do
        if msg == "TRANSCRIBING" then found = true end
    end
    luaunit.assertTrue(found)
end

os.exit(luaunit.LuaUnit.run())

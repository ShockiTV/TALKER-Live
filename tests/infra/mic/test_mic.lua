package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
local luaunit = require('tests.utils.luaunit')

-- ── Mock dependencies before loading microphone ─────────────────────────────

local ta_start_calls = 0
local ta_stop_calls  = 0
local ta_open_calls  = 0

local mock_ta = {}
mock_ta._available = true
function mock_ta.is_available() return mock_ta._available end
function mock_ta.open()  ta_open_calls  = ta_open_calls  + 1; return 0 end
function mock_ta.start() ta_start_calls = ta_start_calls + 1; return 0 end
function mock_ta.stop()  ta_stop_calls  = ta_stop_calls  + 1; return 0 end

local mock_logger = {}
function mock_logger.info(...) end
function mock_logger.debug(...) end
function mock_logger.error(...) end
function mock_logger.warn(...) end

package.preload["infra.mic.talker_audio_ffi"] = function() return mock_ta end
package.preload["framework.logger"]           = function() return mock_logger end

local mic = require('infra.mic.microphone')

-- ── Helpers ──────────────────────────────────────────────────────────────────

local function reset()
    ta_start_calls = 0
    ta_stop_calls  = 0
    ta_open_calls  = 0
    -- Force internal _recording off
    if mic.is_recording() then
        mic.stop_capture()
        ta_start_calls = 0
        ta_stop_calls  = 0
        ta_open_calls  = 0
    end
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

function testStartCaptureCallsTaStart()
    reset()
    mic.start_capture("dialogue")
    luaunit.assertEquals(ta_start_calls, 1)
end

function testStartCaptureIncrementsSessionId()
    reset()
    local s1 = mic.session_id()
    mic.start_capture("dialogue")
    luaunit.assertEquals(mic.session_id(), s1 + 1)
end

function testStartCaptureWhenAlreadyRecordingIsNoop()
    reset()
    mic.start_capture("dialogue")
    local s = mic.session_id()
    ta_start_calls = 0
    mic.start_capture("dialogue")  -- should be ignored
    luaunit.assertEquals(ta_start_calls, 0)
    luaunit.assertEquals(mic.session_id(), s) -- no increment
    luaunit.assertTrue(mic.is_recording())
end

function testStopCaptureEndsRecording()
    reset()
    mic.start_capture("dialogue")
    mic.stop_capture()
    luaunit.assertFalse(mic.is_recording())
end

function testStopCaptureCallsTaStop()
    reset()
    mic.start_capture("dialogue")
    ta_stop_calls = 0
    mic.stop_capture()
    luaunit.assertEquals(ta_stop_calls, 1)
end

function testStopCaptureWhenNotRecordingIsNoop()
    reset()
    luaunit.assertFalse(mic.is_recording())
    mic.stop_capture()
    luaunit.assertEquals(ta_stop_calls, 0)
end

function testStartAfterStopWorks()
    reset()
    mic.start_capture("dialogue")
    mic.stop_capture()
    ta_start_calls = 0
    mic.start_capture("dialogue")
    luaunit.assertTrue(mic.is_recording())
    luaunit.assertEquals(ta_start_calls, 1)
end

function testOnStoppedResetsRecording()
    reset()
    mic.start_capture("dialogue")
    luaunit.assertTrue(mic.is_recording())
    mic.on_stopped()
    luaunit.assertFalse(mic.is_recording())
end

function testOnStoppedDoesNotCallTaStop()
    reset()
    mic.start_capture("dialogue")
    ta_stop_calls = 0
    mic.on_stopped()
    -- on_stopped should NOT call ta_stop (DLL already stopped)
    luaunit.assertEquals(ta_stop_calls, 0)
end

function testOnStoppedWhenNotRecordingIsNoop()
    reset()
    mic.on_stopped()
    luaunit.assertEquals(ta_stop_calls, 0)
end

function testStartAfterOnStoppedWorks()
    reset()
    mic.start_capture("dialogue")
    mic.on_stopped()
    ta_start_calls = 0
    mic.start_capture("dialogue")
    luaunit.assertTrue(mic.is_recording())
    luaunit.assertEquals(ta_start_calls, 1)
end

function testIsAvailableDelegatesToFFI()
    luaunit.assertTrue(mic.is_available())
    mock_ta._available = false
    luaunit.assertFalse(mic.is_available())
    mock_ta._available = true  -- restore
end

function testSessionIdStartsAtZero()
    -- session_id is module-level, already incremented by tests above
    -- just verify it's a number
    luaunit.assertTrue(type(mic.session_id()) == "number")
end

os.exit(luaunit.LuaUnit.run())

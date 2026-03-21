-- microphone.lua
-- Thin wrapper around the native audio capture DLL (talker_audio.dll).
-- Only tracks whether the mic device is physically recording.
--
-- The mic is the only exclusive resource — one capture at a time.
-- Transcription, LLM, TTS all run concurrently in the background.
--
-- Higher-level toggle logic and result handling live in recorder.lua.

package.path = package.path .. ";./bin/lua/?.lua;"

local mic = {}

local ta     = require("infra.mic.talker_audio_ffi")
local logger = require("framework.logger")

-- Internal state: true only while mic hardware is actively capturing.
local _recording    = false
-- Monotonically increasing session counter — lets downstream discard stale data.
local _session_id   = 0
-- Context type for the current capture session ("dialogue" or "whisper").
local _context_type = "dialogue"
-- Whether ta_open() has been called (one-time PortAudio init).
local _opened       = false

--- Returns true if the mic is actively capturing audio.
function mic.is_recording()
    return _recording
end

--- Returns the current session ID (incremented on each start_capture).
function mic.session_id()
    return _session_id
end

--- Returns the context type for the current (or last) capture session.
function mic.context_type()
    return _context_type
end

--- Returns true if the native audio DLL is loaded and available.
function mic.is_available()
    return ta.is_available()
end

--- Start audio capture via the native DLL.
-- Opens PortAudio stream, begins filling the ring buffer with Opus frames.
-- If already recording, this is a no-op (use stop_capture() first or call
-- from recorder which handles the toggle).
-- @param context_type  string  "dialogue" or "whisper" (stored for downstream use)
-- @return boolean  true if capture started, false if DLL unavailable or error
function mic.start_capture(context_type)
    if _recording then return true end
    if not ta.is_available() then
        logger.warn("mic.start_capture: native DLL not available")
        return false
    end

    -- Lazy one-time PortAudio init
    if not _opened then
        local rc = ta.open()
        if rc ~= 0 then
            logger.error("mic.start_capture: ta_open() failed (rc=%d)", rc)
            return false
        end
        _opened = true
        logger.info("mic: PortAudio initialized (ta_open)")
    end

    local rc = ta.start()
    if rc ~= 0 then
        logger.error("mic.start_capture: ta_start() failed (rc=%d)", rc)
        return false
    end

    _session_id = _session_id + 1
    _recording = true
    _context_type = context_type or "dialogue"
    logger.info("mic.start_capture (native DLL, session=%d, context=%s)",
                _session_id, tostring(context_type or "dialogue"))
    return true
end

--- Graceful stop — end capture, remaining frames drain via ta_poll().
function mic.stop_capture()
    if not _recording then return end
    _recording = false
    ta.stop()
    logger.info("mic.stop_capture (native DLL, session=%d)", _session_id)
end

--- Called when VAD auto-stop is detected (poll returned -1).
--- Syncs Lua state to match reality — the DLL already stopped capturing.
function mic.on_stopped()
    if not _recording then return end
    _recording = false
    logger.info("mic: VAD auto-stopped (session=%d)", _session_id)
end

return mic

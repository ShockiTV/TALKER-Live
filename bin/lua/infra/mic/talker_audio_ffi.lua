-- talker_audio_ffi.lua
-- LuaJIT FFI binding for talker_audio.dll (native mic capture + Opus encoding).
--
-- Loads the DLL via pcall(ffi.load, ...) so the game runs normally even when
-- the DLL is absent — mic features are simply disabled.
--
-- Usage:
--     local ta = require("infra.mic.talker_audio_ffi")
--     if not ta.is_available() then return end   -- graceful fallback
--     ta.open()
--     ta.start()
--     -- per tick:
--     local n = ta.poll(buf, buf_len)
--     ...
--     ta.close()

package.path = package.path .. ";./bin/lua/?.lua;"

local ffi   = require("ffi")

-- ── C declarations ───────────────────────────────────────────────────────────

ffi.cdef[[
/* Lifecycle */
int  ta_open(void);
void ta_close(void);

/* Capture */
int  ta_start(void);
int  ta_stop(void);
int  ta_is_capturing(void);

/* Poll — returns >0 (bytes), 0 (empty), -1 (VAD stop), -2 (manual stop) */
int  ta_poll(uint8_t *buf, int buf_len);

/* VAD configuration */
void ta_set_vad(int energy_threshold, int silence_ms);

/* Device enumeration & selection */
int         ta_get_device_count(void);
int         ta_get_device_name(int index, char *buf, int buf_len);
int         ta_get_default_device(void);
int         ta_set_device(int index);

/* Opus encoder configuration */
void ta_set_opus_bitrate(int bps);
void ta_set_opus_frame_ms(int ms);
void ta_set_opus_complexity(int complexity);
]]

-- ── Load DLL ─────────────────────────────────────────────────────────────────
-- CWD in Anomaly is <game>/bin/ — match pollnet.lua's working LIBDIR pattern.

local LIBDIR = "./pollnet/"

local _lib       -- FFI library object (nil if load failed)
local _available  -- boolean

local ok, lib_or_err = pcall(ffi.load, LIBDIR .. "talker_audio.dll")
if ok then
    _lib = lib_or_err
    _available = true
else
    _available = false
    -- Log the error so it shows up in talker_debug.log for diagnostics
    local log_ok, log = pcall(require, "framework.logger")
    if log_ok then
        log.warn("talker_audio.dll failed to load: " .. tostring(lib_or_err))
    end
end

-- ── Reusable poll buffer (4096 bytes covers any Opus frame) ──────────────────

local POLL_BUF_SIZE = 4096
local _poll_buf = _available and ffi.new("uint8_t[?]", POLL_BUF_SIZE) or nil

-- ── Lua wrapper table ────────────────────────────────────────────────────────

local M = {}

--- Returns true if talker_audio.dll was loaded successfully.
function M.is_available()
    return _available
end

--- Initialise PortAudio and internal state.
-- @return int 0 on success
function M.open()
    if not _available then return -1 end
    return _lib.ta_open()
end

--- Teardown — stops capture, releases PortAudio, frees buffers.
function M.close()
    if not _available then return end
    _lib.ta_close()
end

--- Start audio capture on the selected (or default) device.
-- @return int 0 on success
function M.start()
    if not _available then return -1 end
    return _lib.ta_start()
end

--- Stop capture.  Buffered frames remain available via poll().
-- @return int 0 on success
function M.stop()
    if not _available then return -1 end
    return _lib.ta_stop()
end

--- Returns true if the DLL is actively capturing audio.
function M.is_capturing()
    if not _available then return false end
    return _lib.ta_is_capturing() == 1
end

--- Drain one Opus frame from the ring buffer.
-- @return int n, cdata buf_ptr
--   n > 0 : opus bytes written to buf_ptr
--   n == 0 : nothing available (capture still active)
--   n == -1 : VAD auto-stop (all frames drained)
--   n == -2 : manual stop (all frames drained)
function M.poll()
    if not _available then return 0, nil end
    local n = _lib.ta_poll(_poll_buf, POLL_BUF_SIZE)
    return n, _poll_buf
end

--- Configure VAD parameters.
-- @param energy_threshold  int  Amplitude threshold (default 1000)
-- @param silence_ms        int  Silence duration to auto-stop (default 2000)
function M.set_vad(energy_threshold, silence_ms)
    if not _available then return end
    _lib.ta_set_vad(energy_threshold or 1000, silence_ms or 2000)
end

--- Returns the number of capture input devices.
function M.get_device_count()
    if not _available then return 0 end
    return _lib.ta_get_device_count()
end

--- Returns the name of the device at the given index.
-- @param index  int  0-based device index
-- @return string|nil  Device name, or nil on error
function M.get_device_name(index)
    if not _available then return nil end
    local buf = ffi.new("char[256]")
    local rc = _lib.ta_get_device_name(index, buf, 256)
    if rc == 0 then
        return ffi.string(buf)
    end
    return nil
end

--- Returns the index of the system default capture device.
function M.get_default_device()
    if not _available then return -1 end
    return _lib.ta_get_default_device()
end

--- Select a specific capture device by index.
-- @param index  int  0-based device index
-- @return int  0 on success, non-zero on error
function M.set_device(index)
    if not _available then return -1 end
    return _lib.ta_set_device(index)
end

--- Set Opus encoder bitrate (bps).  Default 24000.
function M.set_opus_bitrate(bps)
    if not _available then return end
    _lib.ta_set_opus_bitrate(bps or 24000)
end

--- Set Opus frame duration (ms).  Default 20.
function M.set_opus_frame_ms(ms)
    if not _available then return end
    _lib.ta_set_opus_frame_ms(ms or 20)
end

--- Set Opus encoder complexity (0–10).  Default 5.
function M.set_opus_complexity(complexity)
    if not _available then return end
    _lib.ta_set_opus_complexity(complexity or 5)
end

return M

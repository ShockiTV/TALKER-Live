-- audio_tick.lua
-- Poll loop for native mic capture — called once per game tick.
--
-- Drains Opus-encoded frames from the native DLL ring buffer, base64-encodes
-- them, and publishes mic.audio.chunk messages through the bridge channel.
-- Handles VAD auto-stop (-1) and manual stop (-2) signalling.
--
-- Integration:  call audio_tick.tick() from the same timer that drives
--               bridge_channel.tick().

package.path = package.path .. ";./bin/lua/?.lua;"

local ta             = require("infra.mic.talker_audio_ffi")
local mic            = require("infra.mic.microphone")
local bridge_channel = require("infra.bridge.channel")
local base64         = require("infra.base64")
local ffi            = require("ffi")
local logger         = require("framework.logger")

local M = {}

-- ── Configuration ────────────────────────────────────────────────────────────

-- Maximum Opus frames to drain per tick.
-- At 20ms/frame and 50ms tick, expect ~2-3 frames normally.
-- Higher cap handles burst after a brief hitch.
local MAX_FRAMES_PER_TICK = 20

-- ── State ────────────────────────────────────────────────────────────────────

local _seq = 0               -- 1-based per-session sequence counter
local _active_session = 0    -- mirrors mic.session_id() to detect stale drains
local _draining = false       -- true while we have an active poll session
local _on_vad_stopped = nil   -- callback: fn()  — registered by recorder

-- ── Public API ───────────────────────────────────────────────────────────────

--- Register a callback fired when VAD auto-stop is detected (poll returns -1).
-- The recorder module calls this to wire up its state transition.
-- @param fn  function()  Callback (no arguments)
function M.set_on_vad_stopped(fn)
    _on_vad_stopped = fn
end

--- Main tick function — drain the ring buffer and publish chunks.
-- Call once per game tick (~50ms).  No-op when the DLL is unavailable
-- or no capture session is active.
function M.tick()
    if not ta.is_available() then return end

    -- Start draining when a new capture session begins
    local current_session = mic.session_id()
    if current_session ~= _active_session then
        if mic.is_recording() or current_session > _active_session then
            _active_session = current_session
            _seq = 0
            _draining = true
        end
    end

    if not _draining then return end

    for _ = 1, MAX_FRAMES_PER_TICK do
        local n, buf = ta.poll()

        if n > 0 then
            -- Opus frame available — base64-encode and publish
            _seq = _seq + 1
            local raw = ffi.string(buf, n)
            local encoded = base64.encode(raw)
            bridge_channel.publish("mic.audio.chunk", {
                audio_b64  = encoded,
                seq        = _seq,
                session_id = _active_session,
                format     = "opus",
            })

        elseif n == 0 then
            -- Nothing ready — break out of drain loop for this tick
            break

        elseif n == -1 then
            -- VAD auto-stop: all frames drained, capture already stopped by DLL
            _draining = false
            _send_audio_end()
            mic.on_stopped()
            if _on_vad_stopped then
                local ok, err = pcall(_on_vad_stopped)
                if not ok then
                    logger.error("audio_tick: on_vad_stopped callback error: %s", tostring(err))
                end
            end
            logger.info("audio_tick: VAD auto-stop (session=%d, chunks=%d)", _active_session, _seq)
            break

        elseif n == -2 then
            -- Manual stop: all frames drained, ta_stop() was called by microphone.lua
            _draining = false
            _send_audio_end()
            logger.info("audio_tick: manual stop drained (session=%d, chunks=%d)", _active_session, _seq)
            break
        end
    end
end

-- ── Internal ─────────────────────────────────────────────────────────────────

--- Send mic.audio.end to signal transcription should begin.
function _send_audio_end()
    bridge_channel.publish("mic.audio.end", {
        session_id = _active_session,
        context    = { type = mic.context_type() },
    })
end

-- ── Test helpers ─────────────────────────────────────────────────────────────

function M._reset()
    _seq = 0
    _active_session = 0
    _draining = false
    _on_vad_stopped = nil
end

return M

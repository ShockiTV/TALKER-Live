-- microphone.lua
-- Thin wrapper around the mic hardware via bridge channel.
-- Only tracks whether the mic device is physically recording.
--
-- The mic is the only exclusive resource — one capture at a time.
-- Transcription, LLM, TTS all run concurrently in the background.
--
-- Higher-level toggle logic and result handling live in recorder.lua.

package.path = package.path .. ";./bin/lua/?.lua;"

local mic = {}

local bridge_channel = require("infra.bridge.channel")
local logger  = require("framework.logger")

-- Internal state: true only while mic hardware is actively capturing.
local _recording = false

--- Returns true if the mic is actively capturing audio.
function mic.is_recording()
    return _recording
end

--- Start audio capture.
-- Publishes mic.start to bridge, which begins streaming audio chunks.
-- If already recording, this is a no-op (use stop() first or call start
-- from recorder which handles the toggle).
function mic.start_capture(context_type)
    if _recording then return end
    _recording = true
    bridge_channel.publish("mic.start", {
        context_type = context_type or "dialogue",
    })
    logger.info("mic.start_capture published (context=%s)", tostring(context_type or "dialogue"))
end

--- Graceful stop — end capture, trigger transcription.
-- Bridge sends mic.audio.end to service, which transcribes and sends mic.result.
function mic.stop_capture()
    if not _recording then return end
    _recording = false
    bridge_channel.publish("mic.stop", {})
    logger.info("mic.stop_capture published")
end

--- Called when the bridge reports that the mic hardware stopped capturing
--- (e.g. VAD silence detection).  Syncs Lua state to match reality.
function mic.on_stopped()
    if not _recording then return end
    _recording = false
    logger.info("mic: hardware stopped (bridge notified)")
end

return mic

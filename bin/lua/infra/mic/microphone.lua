-- microphone.lua
-- Manages the microphone and transcription process via ZMQ.
-- Sends mic.start / mic.stop commands to mic_python via the ZMQ bridge.
-- ZMQ handlers for mic.status and mic.result are registered per recording session
-- and passed as callbacks to callers (e.g. recorder.lua).

package.path = package.path .. ";./bin/lua/?.lua;"

local mic = {}

local bridge = require("infra.zmq.bridge")
local config  = require("interface.config")
local logger  = require("framework.logger")

-- Internal state
local mic_on = false

--- Returns true if a recording session is currently active.
function mic.is_mic_on()
    return mic_on
end

--- Start recording.
-- Publishes mic.start to mic_python and registers per-session ZMQ handlers.
-- @param transcription_prompt  Hint string forwarded to the transcription provider.
-- @param opts Table with optional callbacks:
--   opts.on_status(status_str)  Called when mic.status is received ("LISTENING" | "TRANSCRIBING").
--   opts.on_result(text_str)    Called once when mic.result is received; handlers are then cleaned up.
function mic.start(transcription_prompt, opts)
    if mic_on then return end
    local lang_code = config.language_short()
    mic_on = true

    -- Register per-session ZMQ handlers that fire the caller's callbacks.
    bridge.register_handler("mic.status", function(topic, payload)
        if opts and opts.on_status then
            opts.on_status(payload.status or "")
        end
    end)

    bridge.register_handler("mic.result", function(topic, payload)
        mic_on = false
        bridge.unregister_handler("mic.status")
        bridge.unregister_handler("mic.result")
        if opts and opts.on_result then
            opts.on_result(payload.text or "")
        end
    end)

    bridge.publish("mic.start", {
        lang   = lang_code,
        prompt = transcription_prompt or "",
    })

    logger.info("mic.start published (lang=%s)", tostring(lang_code))
end

--- Stop recording early (cancellation).
-- Publishes mic.stop to mic_python and cleans up session handlers.
function mic.stop()
    if not mic_on then return end
    mic_on = false
    bridge.unregister_handler("mic.status")
    bridge.unregister_handler("mic.result")
    bridge.publish("mic.stop", {})
    logger.info("mic.stop published")
end

return mic

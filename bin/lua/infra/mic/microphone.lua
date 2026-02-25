-- microphone.lua
-- Manages the microphone and transcription process via WebSocket.
-- Sends mic.start / mic.stop commands to talker_bridge via the bridge channel.
-- mic.status and mic.result handlers are registered per recording session
-- using mic_channel.start_session().

package.path = package.path .. ";./bin/lua/?.lua;"

local mic = {}

local mic_channel = require("infra.mic.channel")
local config  = require("interface.config")
local logger  = require("framework.logger")

-- Internal state
local mic_on = false

--- Returns true if a recording session is currently active.
function mic.is_mic_on()
    return mic_on
end

--- Start recording.
-- Publishes mic.start to talker_bridge and registers per-session handlers
-- via mic_channel.start_session().
-- @param transcription_prompt  Hint string forwarded to the transcription provider.
-- @param opts Table with optional callbacks:
--   opts.on_status(status_str)  Called when mic.status is received ("LISTENING" | "TRANSCRIBING").
--   opts.on_result(text_str)    Called once when mic.result is received; session handlers auto-cleanup.
function mic.start(transcription_prompt, opts)
    if mic_on then return end
    local lang_code = config.language_short()
    mic_on = true

    -- Register per-session handlers via mic_channel.
    -- start_session clears any previous handlers and registers on_status + on_result.
    -- on_result auto-cleans up session handlers.
    mic_channel.start_session(
        function(payload)
            -- on_status callback — payload is {status = "LISTENING"} etc.
            if opts and opts.on_status then
                local status_str = (type(payload) == "table" and payload.status) or tostring(payload)
                opts.on_status(status_str)
            end
        end,
        function(payload)
            -- on_result callback — payload is {text = "transcribed text"}
            -- session handlers are auto-cleaned by mic_channel
            mic_on = false
            if opts and opts.on_result then
                local text_str = (type(payload) == "table" and payload.text) or tostring(payload)
                opts.on_result(text_str)
            end
        end
    )

    mic_channel.publish("mic.start", {
        lang   = lang_code,
        prompt = transcription_prompt or "",
    })

    logger.info("mic.start published (lang=%s)", tostring(lang_code))
end

--- Stop recording early (cancellation).
-- Publishes mic.stop to talker_bridge.
function mic.stop()
    if not mic_on then return end
    mic_on = false
    mic_channel.publish("mic.stop", {})
    logger.info("mic.stop published")
end

return mic

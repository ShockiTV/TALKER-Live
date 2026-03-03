-- recorder.lua
-- Player recording session manager — toggle-based state machine.
--
-- Key press behaviour:
--   idle         → start capture        → RECORDING
--   capturing    → stop capture          → TRANSCRIBING  (transcription runs)
--   transcribing → start new capture     → RECORDING      (old transcription continues)
--
-- The mic device is the only exclusive resource.
-- Transcription, LLM, and TTS all run concurrently in the background.
--
-- VAD auto-stop:  audio_tick.lua calls recorder.on_vad_stopped() when the
--   native DLL detects silence.  This replaces the old bridge_channel
--   "mic.stopped" handler.
-- Transcription results:  mic.result arrives from the service via
--   bridge_channel (proxied).

package.path = package.path .. ";./bin/lua/?.lua"
local logger         = require("framework.logger")
local game_adapter   = require("infra.game_adapter")
local engine         = require("interface.engine")
local mic            = require("infra.mic.microphone")
local bridge_channel = require("infra.bridge.channel")
local json           = require("infra.HTTP.json")

local recorder = {}

-- ── State ─────────────────────────────────────────────────────────────────────

local STATE_IDLE         = "idle"
local STATE_CAPTURING    = "capturing"
local STATE_TRANSCRIBING = "transcribing"

local _state    = STATE_IDLE
local _callback = nil   -- fn(text) — called for every transcription result

-- ── Helpers ───────────────────────────────────────────────────────────────────

local function get_names_of_nearby_characters()
    logger.info("get_names_of_nearby_characters")
    local nearby_characters = game_adapter.get_characters_near_player()
    local names = {}
    for _, character in ipairs(nearby_characters) do
        table.insert(names, character.name)
    end
    return names
end

local function create_transcription_prompt(names)
    logger.info("Creating transcription prompt")
    local prompt = "STALKER games setting, nearby characters are: "
    for i, name in ipairs(names) do
        prompt = prompt .. name
        if i < #names then
            prompt = prompt .. ", "
        end
    end
    return prompt
end

-- ── Topic handlers (registered once) ──────────────────────────────────────────

local _handlers_registered = false

local function register_handlers()
    if _handlers_registered then return end
    _handlers_registered = true

    -- mic.status — HUD display for transcription progress (from service via bridge)
    bridge_channel.on("mic.status", function(payload)
        local status = (type(payload) == "table" and payload.status) or tostring(payload)
        -- Capturing has highest HUD priority — don't let background
        -- transcription status overwrite "RECORDING".
        if _state == STATE_CAPTURING then
            logger.info("recorder: suppressed mic.status '%s' (capturing has priority)", status)
            return
        end
        engine.display_hud_message(status, 15)
    end)

    -- mic.result — final transcription text (from service via bridge)
    bridge_channel.on("mic.result", function(payload)
        local text = (type(payload) == "table" and payload.text) or ""
        logger.info("mic.result received: '%s' (state=%s)", text, _state)

        -- Transition: transcribing → idle (unless we're already in a new capture)
        if _state == STATE_TRANSCRIBING then
            _state = STATE_IDLE
        end

        if text ~= "" and _callback then
            text = json.utf8_to_codepage(text)
            _callback(text)
        end
    end)

    -- Wire up VAD callback from audio_tick
    local ok_at, audio_tick = pcall(require, "infra.mic.audio_tick")
    if ok_at and audio_tick then
        audio_tick.set_on_vad_stopped(function()
            recorder.on_vad_stopped()
        end)
    end

    logger.info("recorder: permanent handlers registered")
end

-- ── Public API ────────────────────────────────────────────────────────────────

--- Called by audio_tick when VAD auto-stop is detected (poll returned -1).
-- Replaces the old bridge_channel "mic.stopped" handler.
function recorder.on_vad_stopped()
    if _state ~= STATE_CAPTURING then return end
    _state = STATE_TRANSCRIBING
    engine.display_hud_message("TRANSCRIBING", 15)
    logger.info("recorder: VAD auto-stopped → transcribing")
end

--- Toggle the recording session.
-- Call on each key press.  Cycles: idle → capture → stop+transcribe → idle.
-- Can also start a new capture during transcription (old result still delivered).
-- @param callback  fn(text) — called with transcribed text for every completed result.
function recorder.toggle(callback)
    register_handlers()
    _callback = callback

    if _state == STATE_CAPTURING then
        -- Currently capturing → stop and transcribe
        _state = STATE_TRANSCRIBING
        mic.stop_capture()
        engine.display_hud_message("TRANSCRIBING", 15)
        logger.info("recorder: capture stopped → transcribing")
        return
    end

    -- idle or transcribing → start new capture
    -- (if transcribing, old result will still be delivered via mic.result handler)
    local names  = get_names_of_nearby_characters()
    local prompt = create_transcription_prompt(names)
    local started = mic.start_capture("dialogue")
    if not started then
        engine.display_hud_message("MIC NOT AVAILABLE", 5)
        logger.warn("recorder: mic.start_capture failed — DLL not loaded or init error")
        return
    end
    _state = STATE_CAPTURING
    engine.display_hud_message("RECORDING", 15)
    logger.info("recorder: capture started (state was %s)", _state)
end

--- Returns the current state string (for debugging / testing).
function recorder.state()
    return _state
end

--- Reset internal state to idle (for testing only).
function recorder._reset()
    _state = STATE_IDLE
    _callback = nil
end

return recorder

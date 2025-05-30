-- this module represents the microphone and transcription process to the inner application
-- it interacts with a script that truly controls the microphone
-- interaction is done via 2 files in the temp folder, one to send commands and one to receive transcriptions

local mic = {}

-- Import necessary modules
local file_io = require("infra.file_io")
local config = require('interface.config')

-- File paths in the temporary directory (must match Python script)
local COMMAND_FILE = "/talker_mic_io_commands"
local TRANSCRIPTION_FILE = "/talker_mic_io_transcription"

-- Commands (must match Python script)
local COMMANDS = {
    LISTENING = "LISTENING",
    START = "START",
    STOP = "STOP",
    TRANSCRIBING = "TRANSCRIBING",
    DONE = "DONE"
}

-- Internal state
local mic_on = false

-- Function to write to the command file
local function send_to_microphone(contents)
    file_io.override_temp(COMMAND_FILE, contents)
end

-- Function to read from the transcription file
local function read_transcription()
    return file_io.read_temp(TRANSCRIPTION_FILE)
end

-- Check if the microphone is currently on
function mic.is_mic_on()
    return mic_on
end

-- Get the latest transcription, if available
function mic.get_transcription()
    local transcription = read_transcription()
    if transcription and transcription ~= "" then
        return transcription
    else
        return nil
    end
end

-- Clear the transcription file
function mic.clear_transcription()
    file_io.override_temp(TRANSCRIPTION_FILE, "")
end

-- Start recording with an optional transcription prompt
function mic.start(transcription_prompt)
    if mic_on then return end          -- already recording
    mic_on = true

    -- convert long name from config.language() → ISO-639-1 code
    local lang_code = config.language_short()

    -- build “START-<lang>-<prompt>”
    send_to_microphone(string.format("%s-%s-%s",
        COMMANDS.START,                -- already ends with '-'
        lang_code,
        transcription_prompt or ""))
end

-- Stop recording
function mic.stop()
    if not mic_on then
        return -- Not recording
    end
    mic_on = false
    send_to_microphone(COMMANDS.STOP)
end

-- Read file to see if the script responded
function mic.check_if_listening()
    return file_io.read_temp(COMMAND_FILE) == COMMANDS.LISTENING
end

function mic.get_status()
    local status = file_io.read_temp(COMMAND_FILE)
    -- if starts with START, replace with LISTENING
    if status and status:sub(1, #COMMANDS.START) == COMMANDS.START then
        status =  COMMANDS.LISTENING
    end
    return status
end

return mic

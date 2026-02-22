-- recorder.lua
-- Manages the player recording session.
-- Calls mic.start(prompt, callbacks) — no polling loop needed with ZMQ.
-- mic.status ZMQ push refreshes HUD; mic.result delivers the transcription.

package.path = package.path .. ";./bin/lua/?.lua"
local logger       = require("framework.logger")
local game_adapter = require("infra.game_adapter")
local engine       = require("interface.engine")
local mic          = require("infra.mic.microphone")
local json         = require("infra.HTTP.json")

local recorder = {}

local function get_names_of_nearby_characters()
    logger.info("get_names_of_nearby_characters")
    local nearby_characters = game_adapter.get_characters_near_player()
    local names = {}
    for _, character in ipairs(nearby_characters) do
        table.insert(names, character.name)
    end
    return names
end

-- Create a simple prompt for the transcription provider
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

--- Start a recording session.
-- @param callback  Function called with the transcribed text when recording is complete.
function recorder.start(callback)
    logger.info("Listening for player dialogue...")
    mic.stop()  -- cancel any prior session

    local names  = get_names_of_nearby_characters()
    local prompt = create_transcription_prompt(names)

    -- Show initial status immediately; each mic.status ZMQ push will refresh it.
    -- Use a long duration so the text persists across the whole recording phase.
    engine.display_hud_message("LISTENING", 15)

    mic.start(prompt, {
        -- ZMQ push: new phase started — refresh HUD for up to 15 more seconds.
        on_status = function(status)
            engine.display_hud_message(status, 15)
        end,
        -- ZMQ push: result delivered — no loop to clean up.
        on_result = function(text)
            if text and text ~= "" then
                text = json.utf8_to_codepage(text)
                if callback then
                    callback(text)
                end
            end
        end,
    })
end

return recorder

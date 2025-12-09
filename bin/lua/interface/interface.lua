-- interface.lua
local log = require("framework.logger")
local talker = require("app.talker")
local game_adapter = require("infra.game_adapter")
local AI_request = require("infra.AI.requests")

-- game interfaces
local query = talker_game_queries

local m = {}

--- Instructs a specific character to perform a dialogue action, used for idle conversation prompts
function m.register_character_instructions(unformatted_description, character, important, flags)
    local witnesses = game_adapter.get_characters_near_player()
    return m.register_game_event(unformatted_description, {character}, witnesses, important, flags)
end

-- prototype

function m.register_game_event_near_player(unformatted_description, involved_objects, important)
    local witnesses = game_adapter.get_characters_near_player()
    return m.register_game_event(unformatted_description, involved_objects, witnesses, important, nil)
end

local function register_game_event(unformatted_description, event_objects, witnesses, important, flags)
    log.info("Registering game event")
    local new_event = game_adapter.create_game_event(unformatted_description, event_objects, witnesses, flags)
    log.debug("New event: %s", new_event)
    talker.register_event(new_event, important)
end

-- prevents issues later down the line with formatting
local function check_format_sanity(unformatted_description, ...)
    local additional_args = {...}
    local format_count = select(2, unformatted_description:gsub("%%s", ""))
    -- returns true if the amounts of variables like %s match the amount of arguments
    if (format_count > 0) and (format_count > #unpack(additional_args)) then
        log.error("Not enough arguments for description: %s", unformatted_description)
        return false
    end
    return true
end

function m.register_game_event(unformatted_description, event_objects, witnesses, important, flags)
    if not check_format_sanity(unformatted_description, event_objects) then return false end
    local success, error = pcall(register_game_event, unformatted_description, event_objects, witnesses, important, flags)
    if not success then
        log.error("Failed to register game event: %s", error)
        return false
    end
    return true
end

--- Checks if any NPC near the player has spoken within a given threshold.
-- This is used to determine if there is a "moment of silence" suitable for an idle conversation.
function m.has_anyone_spoken_recently()
    local RECENT_SPEECH_THRESHOLD_MS = 3 * 60 * 1000 -- 3 minutes

    local nearby_characters = game_adapter.get_characters_near_player()
    if not nearby_characters or #nearby_characters == 0 then
        return false -- No characters nearby, so nobody could have spoken.
    end

    local current_game_time = query.get_game_time_ms()

    for _, character in ipairs(nearby_characters) do
        local last_spoke_time = AI_request.get_last_spoke_time(character.game_id)
        if last_spoke_time then
            if current_game_time - last_spoke_time < RECENT_SPEECH_THRESHOLD_MS then
                -- Found someone who spoke within the last 3 minutes.
                return true
            end
        end
    end

    -- If we get here, it means no one nearby has spoken recently.
    return false
end
----------------------------------------------------------------------------------------------------
-- SEND PLAYER DIALOGUE TO GAME 
----------------------------------------------------------------------------------------------------

-- function recorder.to register the player's dialogue as a game event
function m.player_character_speaks(dialogue)
    log.info("Registering player speak event. Player said: " .. dialogue)
    local player = game_adapter.get_player_character()
    -- register new event
    m.register_game_event_near_player("%s, a %s rank member of the %s faction said: %s", {player.name, player.experience, player.faction, dialogue}, true )
    -- show dialogue in game UI
    game_adapter.display_dialogue(player.game_id, dialogue)
end

return m

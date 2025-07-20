package.path = package.path .. ";./bin/lua/?.lua;"
local event_store = require('domain.repo.event_store')
local logger = require('framework.logger')
local AI_request = require('infra.AI.requests')
local game_adapter = require('infra.game_adapter')
local config = require('interface.config')

local talker = {}

function talker.register_event(event, is_important)
    logger.info("talker.register_event")
    event_store:store_event(event)
    if should_someone_speak(event, is_important) then
        talker.generate_dialogue(event)
    end
end

local TEN_SECONDS_ms = 10 * 1000

function talker.generate_dialogue(event)
    logger.debug("Getting all events since " .. event.game_time_ms - TEN_SECONDS_ms)
    local recent_events = event_store:get_events_since(event.game_time_ms - TEN_SECONDS_ms)
    -- begin a dialogue generation request, input is recent_events, output is speaker_id and dialogue
    AI_request.generate_dialogue(recent_events, function(speaker_id, dialogue)
        -- on response:
        logger.info("talker.generate_dialogue: dialogue generated for speaker_id: " .. speaker_id .. ", dialogue: " .. dialogue)

        game_adapter.display_dialogue(speaker_id, dialogue)
        local dialogue_event = game_adapter.create_dialogue_event(speaker_id, dialogue)
        talker.register_event(dialogue_event)
    end)
end

function should_someone_speak(event, is_important)
    -- mostly a placeholder
    -- always should reply to player dialogue
    -- for all others, 25% chance
    if #event.witnesses == 1 and game_adapter.is_player(event.witnesses[1]) then
        logger.warn("Only witness is player, not generating dialogue, should probably not save this event at all")
        -- player is only witness
        return false
    end
    return is_important or math.random() < config.BASE_DIALOGUE_CHANCE
end

-- for mocking
function talker.set_game_adapter(adapter)
    game_adapter = adapter
end

return talker

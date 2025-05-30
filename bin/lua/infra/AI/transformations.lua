
local logger = require("framework.logger")
local game = require("infra.game_adapter")
local config = require("interface.config")

local transformation = {}
transformation.__index = transformation

function transformation.pick_potential_speakers(recent_events)
    local latest_event = recent_events[#recent_events]
    -- filter out any witnesses further than config.NPC_SPEAK_DISTANCE
    local witnesses = latest_event.witnesses
    logger.info("wintesses " .. #witnesses)
    logger.debug("witnesses %s",witnesses)

    for i = #witnesses, 1, -1 do  -- iterate in reverse to safely remove items
        if game.is_player(witnesses[i].game_id) or is_too_far_to_speak(witnesses[i]) then
            logger.debug("removing witness from speaker list: %s", witnesses[i])
            table.remove(witnesses, i)
        end
    end
    return witnesses
end

function is_too_far_to_speak(character)
    local distance = game.get_distance_to_player(character.game_id) 
    local result = distance > config.NPC_SPEAK_DISTANCE
    if result == true then
        logger.debug("too far to speak %s at distance %s when max distance is %s ", character.game_id, distance, config.NPC_SPEAK_DISTANCE)
    end
    return result
end

------------------------------------------------------------------------------------------------------
-- Constants for memory management
------------------------------------------------------------------------------------------------------
local MEMORY_COMPRESSION_TRESHHOLD = 8
local AMOUNT_OF_MEMORIES_WE_DONT_COMPRESS = 3

------------------------------------------------------------------------------------------------------
function transformation.select_old_memories_for_compression(memories)
    if #memories <= MEMORY_COMPRESSION_TRESHHOLD then
        return {}
    end

    local compression_count = #memories - AMOUNT_OF_MEMORIES_WE_DONT_COMPRESS
    local old_memories = {}
    for i = 1, compression_count do
        table.insert(old_memories, memories[i])
    end

    return old_memories
end

function transformation.mockGame(mockGame)
    game = mockGame
end



return transformation
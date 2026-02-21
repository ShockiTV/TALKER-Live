-- ZeroMQ Publisher for TALKER Expanded
-- High-level API for publishing events to the Python service
--
-- Provides topic constants and convenient send functions

package.path = package.path .. ";./bin/lua/?.lua;"

local bridge = require("infra.zmq.bridge")
local logger = require("framework.logger")
local Event = require("domain.model.event")
local engine = require("interface.engine")
local Character = require("domain.model.character")

local publisher = {}

--------------------------------------------------------------------------------
-- Topic Constants
--------------------------------------------------------------------------------

publisher.topics = {
    -- Game events
    GAME_EVENT = "game.event",
    
    -- Player actions
    PLAYER_DIALOGUE = "player.dialogue",
    PLAYER_WHISPER = "player.whisper",
    
    -- Configuration
    CONFIG_UPDATE = "config.update",
    CONFIG_SYNC = "config.sync",
    
    -- System
    HEARTBEAT = "system.heartbeat",
    
    -- State query responses (Lua -> Python)
    STATE_RESPONSE = "state.response",
}

--------------------------------------------------------------------------------
-- Helper Functions
--------------------------------------------------------------------------------

--- Convert a Character object to a serializable table.
-- @param char Character object
-- @return Table with character data
local function serialize_character(char)
    if not char then return nil end
    return {
        game_id = tostring(char.game_id),
        name = char.name,
        faction = char.faction,
        experience = char.experience,
        reputation = char.reputation,
        personality = char.personality,
        backstory = char.backstory,
        weapon = char.weapon,
        visual_faction = char.visual_faction,
    }
end

--- Serialize event context, converting any character objects within.
-- @param context Context table from typed event
-- @return Serialized context table
local function serialize_context(context)
    if not context then return {} end
    
    local result = {}
    local character_keys = {"victim", "killer", "actor", "spotter", "target", "taunter", "speaker"}
    
    for k, v in pairs(context) do
        -- Check if this is a character field
        local is_char_key = false
        for _, key in ipairs(character_keys) do
            if k == key then is_char_key = true; break end
        end
        
        if is_char_key and type(v) == "table" and v.game_id then
            result[k] = serialize_character(v)
        elseif k == "companions" and type(v) == "table" then
            -- Handle companions array
            result[k] = {}
            for _, char in ipairs(v) do
                if char and char.game_id then
                    table.insert(result[k], serialize_character(char))
                end
            end
        else
            -- Pass through other fields (text, item_name, action, etc.)
            result[k] = v
        end
    end
    
    return result
end

--- Convert an Event object to a serializable table.
-- @param event Event object (typed event from Event.create)
-- @return Table with event data
local function serialize_event(event)
    if not event then return nil end
    
    local witnesses = {}
    if event.witnesses then
        for _, w in ipairs(event.witnesses) do
            table.insert(witnesses, serialize_character(w))
        end
    end
    
    return {
        type = event.type,
        context = serialize_context(event.context),
        game_time_ms = event.game_time_ms,
        world_context = event.world_context,
        witnesses = witnesses,
        flags = event.flags,
    }
end

--------------------------------------------------------------------------------
-- Public API
--------------------------------------------------------------------------------

--- Initialize the publisher with optional configuration.
-- @param opts Configuration table (endpoint, enabled)
-- @return true if initialized, false otherwise
function publisher.init(opts)
    return bridge.init(opts)
end

--- Send a game event to the Python service.
-- @param event Event object
-- @param is_important Whether the event is important
-- @return true if sent, false otherwise
function publisher.send_game_event(event, is_important)
    if not bridge.is_connected() then
        return false
    end
    
    local payload = {
        event = serialize_event(event),
        is_important = is_important or false,
    }
    
    local success = bridge.publish(publisher.topics.GAME_EVENT, payload)
    if success then
        logger.debug("Sent game event: %s", event.type or "unknown")
    end
    return success
end

--- Send player dialogue to the Python service.
-- @param text Dialogue text
-- @param context Optional context table
-- @return true if sent, false otherwise
function publisher.send_player_dialogue(text, context)
    if not bridge.is_connected() then
        return false
    end
    
    local payload = {
        text = text,
        context = context or {},
    }
    
    local success = bridge.publish(publisher.topics.PLAYER_DIALOGUE, payload)
    if success then
        logger.debug("Sent player dialogue")
    end
    return success
end

--- Send player whisper to the Python service.
-- @param text Whisper text
-- @param target Optional target character
-- @return true if sent, false otherwise
function publisher.send_player_whisper(text, target)
    if not bridge.is_connected() then
        return false
    end
    
    local payload = {
        text = text,
        target = target and serialize_character(target) or nil,
    }
    
    local success = bridge.publish(publisher.topics.PLAYER_WHISPER, payload)
    if success then
        logger.debug("Sent player whisper")
    end
    return success
end

--- Send a configuration update to the Python service.
-- @param key Configuration key that changed
-- @param value New value
-- @return true if sent, false otherwise
function publisher.send_config_update(key, value)
    if not bridge.is_connected() then
        return false
    end
    
    local payload = {
        key = key,
        value = value,
    }
    
    local success = bridge.publish(publisher.topics.CONFIG_UPDATE, payload)
    if success then
        logger.debug("Sent config update: %s", key)
    end
    return success
end

--- Send full configuration sync to the Python service.
-- @param config_table Full configuration table
-- @return true if sent, false otherwise
function publisher.send_config_sync(config_table)
    if not bridge.is_connected() then
        return false
    end
    
    local payload = {
        config = config_table,
    }
    
    local success = bridge.publish(publisher.topics.CONFIG_SYNC, payload)
    if success then
        logger.info("Sent full config sync")
    end
    return success
end

--- Send a heartbeat to the Python service.
-- @return true if sent, false otherwise
function publisher.send_heartbeat()
    if not bridge.is_connected() then
        return false
    end
    
    local payload = {
        game_time_ms = 0, -- Will be populated by caller if available
        status = "alive",
    }
    
    -- Try to get game time via engine facade
    local t = engine.get_game_time_ms()
    if t and t > 0 then
        payload.game_time_ms = t
    end
    
    local success = bridge.publish(publisher.topics.HEARTBEAT, payload)
    if success then
        logger.debug("Sent heartbeat")
    end
    return success
end

--- Publish a state query response to the Python service.
-- @param topic Response topic (typically "state.response")
-- @param payload Response payload with request_id and data
-- @return true if sent, false otherwise
function publisher.publish_response(topic, payload)
    if not bridge.is_connected() then
        return false
    end
    
    local success = bridge.publish(topic or publisher.topics.STATE_RESPONSE, payload)
    if success then
        logger.debug("Sent state response: %s", payload.response_type or "unknown")
    end
    return success
end

--- Check if publisher is connected.
-- @return true if connected, false otherwise
function publisher.is_connected()
    return bridge.is_connected()
end

--- Shutdown the publisher.
function publisher.shutdown()
    bridge.shutdown()
end

return publisher

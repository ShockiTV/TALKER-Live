-- infra/zmq/serializer.lua
-- ZMQ wire-format serialization for Character, Event, and Context objects.
-- Extracted from the local serialization functions in talker_zmq_query_handlers.script.
-- Zero engine dependencies — pure data transformation.
--
-- Wire format is intentionally byte-identical to the originals so that no Python-side
-- changes are required.
local M = {}

--- Convert a Character object to a wire-format table.
-- game_id is coerced to string for consistent JSON serialization.
-- @param char  Character table (may be nil)
-- @return      Flat table with string game_id, or nil if char is nil
function M.serialize_character(char)
    if not char then return nil end
    local result = {
        game_id       = tostring(char.game_id),
        name          = char.name,
        faction       = char.faction,
        experience    = char.experience,
        reputation    = char.reputation,
        weapon        = char.weapon,
        visual_faction = char.visual_faction,
        story_id      = char.story_id,
    }
    return result
end

--- Serialize an event context table, recursively serializing any Character objects.
-- Recognized character keys: victim, killer, actor, spotter, target, taunter, speaker
-- Recognized array key: companions (array of Characters)
-- @param context  Context table (may be nil)
-- @return         Serialized table; empty table {} if context is nil
function M.serialize_context(context)
    if not context then return {} end

    local result = {}
    local character_keys = { "victim", "killer", "actor", "spotter", "target", "taunter", "speaker", "task_giver" }

    for k, v in pairs(context) do
        -- Test whether this key holds a Character object
        local is_char_key = false
        for _, key in ipairs(character_keys) do
            if k == key then is_char_key = true; break end
        end

        if is_char_key and type(v) == "table" and v.game_id then
            result[k] = M.serialize_character(v)
        elseif k == "companions" and type(v) == "table" then
            result[k] = {}
            for _, char in ipairs(v) do
                if char and char.game_id then
                    table.insert(result[k], M.serialize_character(char))
                end
            end
        else
            result[k] = v
        end
    end

    return result
end

--- Convert an Event object to a wire-format table.
-- @param event  Event table (may be nil)
-- @return       Serialized table, or nil if event is nil
function M.serialize_event(event)
    if not event then return nil end

    local witnesses = {}
    if event.witnesses then
        for _, w in ipairs(event.witnesses) do
            table.insert(witnesses, M.serialize_character(w))
        end
    end

    return {
        type         = event.type,
        context      = M.serialize_context(event.context),
        game_time_ms = event.game_time_ms,
        world_context = event.world_context,
        witnesses    = witnesses,
        flags        = event.flags,
    }
end

--- Serialize an array of events.
-- @param events  Array of Event tables (may be nil)
-- @return        Array of serialized events; empty array {} if events is nil
function M.serialize_events(events)
    if not events then return {} end
    local result = {}
    for _, event in ipairs(events) do
        table.insert(result, M.serialize_event(event))
    end
    return result
end

return M

package.path = package.path .. ";./bin/lua/?.lua;"
local Item = require('domain.model.item')
-- Event data structure
local Event = {}
Event.TYPE = {
    DIALOGUE = "%s: '%s'",
    ACTION = "%s %s %s",
    KILL = "%s killed %s",
    SPOT = "%s spotted %s",
    HEAR = "%s heard %s",
}

-- Event constructor
function Event.create_event(unformatted_description_or_type, involved_objects, game_time_ms, world_context, witnesses, flags, source_event)
    local event = {}
    event.description = unformatted_description_or_type
    event.involved_objects = involved_objects or {}
    event.game_time_ms = game_time_ms
    event.world_context = world_context
    event.witnesses = witnesses or {}
    event.flags = flags or {} -- Add flags to the event object
    event.source_event = source_event
    return event
end

function Event.was_conversation(event)
    return event.source_event ~= nil
end

function table_to_args(table_input)
    local args = {}
    for key, value in pairs(table_input) do
        table.insert(args, value)
    end
    return unpack(args)
end

function Event.describe_event(event)
    local unformatted_description = event.description
    local involved_object_descriptions = {}
    for _, object in ipairs(event.involved_objects) do
        if type(object) == "string" then
            table.insert(involved_object_descriptions, object)
        else
            table.insert(involved_object_descriptions, Item.describe_short(object))
        end
    end
    return string.format(unformatted_description, table_to_args(involved_object_descriptions))
end

function Event.describe_short(event)
    return Event.describe_event(event) -- temporary
end

function Event.was_witnessed_by(event, character_id)
    for _, witness in ipairs(event.witnesses) do
        if tostring(witness.game_id) == tostring(character_id) then
            return true
        end
    end
    return false
end

return Event

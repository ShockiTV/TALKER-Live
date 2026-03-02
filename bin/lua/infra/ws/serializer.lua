-- infra/ws/serializer.lua
-- Wire-format serialization for Character, Event, and Context objects.
-- Extracted from the local serialization functions in talker_ws_query_handlers.script.
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
        game_id        = tostring(char.game_id),
        name           = char.name,
        faction        = char.faction,
        experience     = char.experience,
        reputation     = char.reputation,
        weapon         = char.weapon,
        visual_faction = char.visual_faction,
        story_id       = char.story_id,
        sound_prefix   = char.sound_prefix,
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

--- Serialize an array of candidate characters.
-- @param candidates  Array of Character objects
-- @return            Array of serialized characters
function M.serialize_candidates(candidates)
    if not candidates then return {} end
    local result = {}
    for _, char in ipairs(candidates) do
        if char then
            table.insert(result, M.serialize_character(char))
        end
    end
    return result
end

--- Serialize traits map (already wire-ready, just validate structure).
-- Traits map: character_id → {personality_id, backstory_id}
-- @param traits  Traits map table
-- @return        Wire-ready traits map (passed through as-is)
function M.serialize_traits(traits)
    return traits or {}
end

--- Serialize a character with a derived gender field.
-- Gender is derived from sound_prefix: "woman" → "female", otherwise → "male".
-- Does NOT modify the Character domain model — gender is a serialization-time field.
-- @param char  Character table (may be nil)
-- @return      Serialized character with gender field, or nil if char is nil
function M.serialize_character_with_gender(char)
    local base = M.serialize_character(char)
    if not base then return nil end
    local prefix = base.sound_prefix or ""
    base.gender = (prefix == "woman") and "female" or "male"
    return base
end

--- Serialize a character with gender and background for the get_character_info tool.
-- Builds {character: {..., gender, background}, squad_members: [{...}, ...]}
-- @param char           Character table (main character)
-- @param squad_members  Array of Character tables (squad members, excluding main)
-- @param memory_store   memory_store_v2 instance for background lookup
-- @return               Table with character and squad_members fields
function M.serialize_character_info(char, squad_members, memory_store)
    local main = M.serialize_character_with_gender(char)
    if main and memory_store then
        local bg = memory_store:query(tostring(char.game_id), "memory.background")
        main.background = bg  -- nil if no background
    end

    local members = {}
    for _, member in ipairs(squad_members or {}) do
        local entry = M.serialize_character_with_gender(member)
        if entry and memory_store then
            local bg = memory_store:query(tostring(member.game_id), "memory.background")
            entry.background = bg  -- nil if no background
        end
        if entry then
            members[#members + 1] = entry
        end
    end

    return {
        character = main,
        squad_members = members,
    }
end

--- Serialize the v2 game event payload with candidates, world, and traits.
-- New payload format for tools-based-memory:
--   {event: {...}, candidates: [...], world: "...", traits: {...}}
-- @param event       Event object
-- @param candidates  Array of Character objects (speaker + witnesses)
-- @param world       World description string
-- @param traits      Traits map {character_id → {personality_id, backstory_id}}
-- @return            Complete v2 payload table
function M.serialize_game_event_v2(event, candidates, world, traits)
    return {
        event = M.serialize_event(event),
        candidates = M.serialize_candidates(candidates),
        world = world or "",
        traits = M.serialize_traits(traits),
    }
end

return M

-- mock_engine.lua — Test double for interface/engine.lua.
-- Implements the full engine facade API with safe stubs.
-- MCM values default to config_defaults. Use _set(key, value) to override.

local defaults = require("interface.config_defaults")

local M = {}

-- Internal override store for per-test injection
local _overrides = {}

-- Inject a custom return value for any engine function or MCM key.
-- Examples:
--   mock_engine._set("get_location_name", "Rostok")
--   mock_engine._set("debug_logging", 3)
--   mock_engine._set("get_player", { id = 0 })
function M._set(key, value)
    _overrides[key] = value
end

-- Reset all overrides (call in test teardown if needed)
function M._reset()
    _overrides = {}
end

-- Internal helper: look up an override or fall back to a default value
local function _get(key, fallback)
    if _overrides[key] ~= nil then
        return _overrides[key]
    end
    return fallback
end

------------------------------------------------------------
-- MCM config
------------------------------------------------------------

function M.get_mcm_value(key)
    -- Check per-key override first, then defaults table
    if _overrides[key] ~= nil then
        return _overrides[key]
    end
    return defaults[key]
end

------------------------------------------------------------
-- Game queries
------------------------------------------------------------

function M.get_name(obj)
    return _get("get_name", obj and (obj.name or obj.character_name and obj:character_name()) or "Unknown")
end

function M.get_id(obj)
    return _get("get_id", obj and obj.id or 0)
end

function M.is_alive(obj)
    return _get("is_alive", obj and (type(obj.alive) == "function" and obj:alive() or obj.alive) or false)
end

function M.get_faction(obj)
    return _get("get_faction", obj and obj.faction or "unknown")
end

function M.get_rank(obj)
    return _get("get_rank", "2")
end

function M.is_player(obj)
    return _get("is_player", obj and obj.id == 0 or false)
end

function M.is_stalker(obj)
    return _get("is_stalker", true)
end

function M.is_companion(obj)
    return _get("is_companion", false)
end

function M.is_in_combat(obj)
    return _get("is_in_combat", false)
end

function M.are_enemies(obj1, obj2)
    return _get("are_enemies", false)
end

function M.get_relations(obj1, obj2)
    return _get("get_relations", 0)
end

function M.get_player()
    return _get("get_player", { id = 0, alive = function() return true end, character_name = function() return "Player" end })
end

function M.is_player_alive()
    return _get("is_player_alive", true)
end

function M.get_player_weapon()
    return _get("get_player_weapon", nil)
end

function M.get_weapon(obj)
    return _get("get_weapon", nil)
end

function M.get_item_description(item)
    return _get("get_item_description", nil)
end

function M.get_nearby_characters(obj, distance, max, exclusion_list)
    return _get("get_nearby_characters", {})
end

function M.get_companions()
    return _get("get_companions", {})
end

function M.get_position(obj)
    return _get("get_position", { x = 0, y = 0, z = 0 })
end

function M.get_obj_by_id(id)
    return _get("get_obj_by_id", nil)
end

function M.get_technical_name(obj)
    return _get("get_technical_name", obj and obj.section or "")
end

function M.get_technical_name_by_id(id)
    return _get("get_technical_name_by_id", "")
end

function M.is_unique_character_by_id(id)
    return _get("is_unique_character_by_id", false)
end

function M.get_unique_character_personality(id)
    return _get("get_unique_character_personality", nil)
end

function M.get_location_name()
    return _get("get_location_name", "Unknown Location")
end

function M.get_location_technical_name()
    return _get("get_location_technical_name", "unknown_location")
end

function M.get_game_time_ms()
    return _get("get_game_time_ms", 0)
end

function M.iterate_nearest(location, distance, func)
    -- no-op by default; override with _set("iterate_nearest", fn) if needed
    local override = _overrides["iterate_nearest"]
    if override then override(location, distance, func) end
end

function M.is_living_character(obj)
    return _get("is_living_character", true)
end

function M.get_distance_between(obj1, obj2)
    return _get("get_distance_between", 0)
end

function M.load_xml(key)
    return _get("load_xml", "")
end

function M.load_random_xml(key)
    return _get("load_random_xml", "")
end

function M.describe_mutant(obj)
    return _get("describe_mutant", "")
end

function M.describe_world()
    return _get("describe_world", "")
end

function M.describe_current_time()
    return _get("describe_current_time", "")
end

function M.get_enemies_fighting_player()
    return _get("get_enemies_fighting_player", {})
end

function M.is_psy_storm_ongoing()
    return _get("is_psy_storm_ongoing", false)
end

function M.is_surge_ongoing()
    return _get("is_surge_ongoing", false)
end

function M.get_community_goodwill(faction)
    return _get("get_community_goodwill", 0)
end

function M.get_community_relation(f1, f2)
    return _get("get_community_relation", 0)
end

function M.get_real_player_faction()
    return _get("get_real_player_faction", "stalker")
end

function M.get_rank_value(obj)
    return _get("get_rank_value", 0)
end

function M.get_reputation_tier(value)
    return _get("get_reputation_tier", "Neutral")
end

function M.get_story_id(id)
    return _get("get_story_id", nil)
end

function M.get_character_event_info(obj)
    return _get("get_character_event_info", nil)
end

------------------------------------------------------------
-- Game commands (no-ops)
------------------------------------------------------------

function M.display_message(sender_id, message)
    -- no-op
end

function M.display_hud_message(message, seconds)
    -- no-op
end

function M.send_news_tip(sender_name, message, image, showtime)
    -- no-op
end

function M.play_sound(sound_name)
    -- no-op
end

function M.SendScriptCallback(callback_name, ...)
    -- no-op
end

------------------------------------------------------------
-- Async / files
------------------------------------------------------------

function M.repeat_until_true(seconds, func, ...)
    -- no-op
end

function M.get_base_path()
    return _get("get_base_path", "")
end

------------------------------------------------------------
-- Time events and callbacks (no-ops)
------------------------------------------------------------

function M.create_time_event(event_id, action_id, delay, func)
    -- no-op
end

function M.reset_time_event(event_id, action_id)
    -- no-op
end

function M.register_callback(name, handler)
    -- no-op
end

function M.printf(fmt, ...)
    print(string.format(fmt, ...))
end

return M

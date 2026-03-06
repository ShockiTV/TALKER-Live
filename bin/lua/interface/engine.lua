---@diagnostic disable: undefined-global
-- engine.lua — Thin facade around STALKER engine globals.
-- All bin/lua/ modules MUST use this module instead of accessing engine
-- globals (talker_mcm, talker_game_queries, etc.) directly.
--
-- Design: lazy binding — globals are resolved at call time, not at load time.
-- This means require("interface.engine") never crashes even when engine globals
-- are nil (test environment), and works regardless of STALKER script load order.

local M = {}

------------------------------------------------------------
-- Private getters (lazy binding)
------------------------------------------------------------

local function get_mcm()   return talker_mcm          end
local function get_q()     return talker_game_queries  end
local function get_cmd()   return talker_game_commands end
local function get_async() return talker_game_async    end
local function get_files() return talker_game_files    end

------------------------------------------------------------
-- MCM config
------------------------------------------------------------

function M.get_mcm_value(key)
    local mcm = get_mcm()
    if mcm and mcm.get then
        return mcm.get(key)
    end
    return nil
end

------------------------------------------------------------
-- Game queries
------------------------------------------------------------

function M.get_name(obj)
    local q = get_q()
    return q and q.get_name(obj) or "Unknown"
end

function M.get_id(obj)
    local q = get_q()
    return q and q.get_id(obj) or 0
end

function M.is_alive(obj)
    local q = get_q()
    return q and q.is_alive(obj) or false
end

function M.get_faction(obj)
    local q = get_q()
    return q and q.get_faction(obj) or nil
end

--- Returns the voice theme ID for an NPC from its sound_prefix, e.g. "stalker_1".
--- Returns nil if the object is not loaded or has no sound prefix.
function M.get_sound_prefix(obj)
    local q = get_q()
    return q and q.get_sound_prefix(obj) or nil
end

function M.get_rank(obj)
    local q = get_q()
    return q and q.get_rank(obj) or "0"
end

function M.is_player(obj)
    local q = get_q()
    return q and q.is_player(obj) or false
end

function M.is_stalker(obj)
    local q = get_q()
    return q and q.is_stalker(obj) or false
end

function M.is_companion(obj)
    local q = get_q()
    return q and q.is_companion(obj) or false
end

function M.is_in_combat(obj)
    local q = get_q()
    return q and q.is_in_combat(obj) or false
end

function M.are_enemies(obj1, obj2)
    local q = get_q()
    return q and q.are_enemies(obj1, obj2) or false
end

function M.get_relations(obj1, obj2)
    local q = get_q()
    return q and q.get_relations(obj1, obj2) or 0
end

function M.get_player()
    local q = get_q()
    return q and q.get_player() or nil
end

function M.is_player_alive()
    local q = get_q()
    return q and q.is_player_alive() or false
end

function M.get_player_weapon()
    local q = get_q()
    return q and q.get_player_weapon() or nil
end

function M.get_weapon(obj)
    local q = get_q()
    return q and q.get_weapon(obj) or nil
end

function M.get_item_description(item)
    local q = get_q()
    return q and q.get_item_description(item) or nil
end

function M.get_nearby_characters(obj, distance, max, exclusion_list)
    local q = get_q()
    return q and q.get_nearby_characters(obj, distance, max, exclusion_list) or {}
end

function M.get_companions()
    local q = get_q()
    return q and q.get_companions() or {}
end

function M.get_position(obj)
    local q = get_q()
    return q and q.get_position(obj) or nil
end

function M.get_obj_by_id(id)
    local q = get_q()
    return q and q.get_obj_by_id(id) or nil
end

function M.get_technical_name(obj)
    local q = get_q()
    return q and q.get_technical_name(obj) or ""
end

function M.get_technical_name_by_id(id)
    local q = get_q()
    return q and q.get_technical_name_by_id(id) or ""
end

function M.is_unique_character_by_id(id)
    local q = get_q()
    return q and q.is_unique_character_by_id(id) or false
end

function M.get_unique_character_personality(id)
    local q = get_q()
    return q and q.get_unique_character_personality(id) or nil
end

function M.get_location_name()
    local q = get_q()
    return q and q.get_location_name() or ""
end

function M.get_location_technical_name()
    local q = get_q()
    return q and q.get_location_technical_name() or ""
end

function M.get_game_time_ms()
    local q = get_q()
    return q and q.get_game_time_ms() or 0
end

function M.iterate_nearest(location, distance, func)
    local q = get_q()
    if q then q.iterate_nearest(location, distance, func) end
end

function M.is_living_character(obj)
    local q = get_q()
    return q and q.is_living_character(obj) or false
end

function M.get_distance_between(obj1, obj2)
    local q = get_q()
    return q and q.get_distance_between(obj1, obj2) or 0
end

function M.load_xml(key)
    local q = get_q()
    return q and q.load_xml(key) or ""
end

--- Returns true if the section string is a known anomaly section.
-- @param section  Technical section name (e.g. "zone_buzz_weak"), may be nil
-- @return         true/false
function M.is_anomaly_section(section)
    local q = get_q()
    return q and q.is_anomaly_section(section) or false
end

--- Returns the human-readable display name for a known anomaly section, or nil.
-- @param section  Technical section name (e.g. "zone_vortex"), may be nil
-- @return         Display name string, or nil if not found
function M.describe_anomaly_section(section)
    local q = get_q()
    return q and q.describe_anomaly_section(section) or nil
end

function M.load_random_xml(key)
    local q = get_q()
    return q and q.load_random_xml(key) or ""
end

function M.describe_mutant(obj)
    local q = get_q()
    return q and q.describe_mutant(obj) or ""
end

function M.describe_world(speaker, listener)
    local q = get_q()
    return q and q.describe_world(speaker, listener) or ""
end

function M.describe_current_time()
    local q = get_q()
    return q and q.describe_current_time() or ""
end

function M.get_enemies_fighting_player()
    local q = get_q()
    return q and q.get_enemies_fighting_player() or {}
end

function M.is_psy_storm_ongoing()
    local q = get_q()
    return q and q.is_psy_storm_ongoing() or false
end

function M.is_surge_ongoing()
    local q = get_q()
    return q and q.is_surge_ongoing() or false
end

function M.get_community_goodwill(faction)
    local q = get_q()
    return q and q.get_community_goodwill(faction) or 0
end

function M.get_community_relation(f1, f2)
    local q = get_q()
    return q and q.get_community_relation(f1, f2) or 0
end

function M.get_real_player_faction()
    local q = get_q()
    return q and q.get_real_player_faction() or "unknown"
end

function M.get_rank_value(obj)
    local q = get_q()
    return q and q.get_rank_value(obj) or 0
end

function M.get_reputation_tier(value)
    local q = get_q()
    return q and q.get_reputation_tier(value) or "Neutral"
end

function M.get_story_id(id)
    local q = get_q()
    return q and q.get_story_id(id) or nil
end

function M.get_character_event_info(obj)
    local q = get_q()
    return q and q.get_character_event_info(obj) or nil
end

------------------------------------------------------------
-- Game commands
------------------------------------------------------------

function M.display_message(sender_id, message)
    local cmd = get_cmd()
    if cmd then cmd.display_message(sender_id, message) end
end

function M.display_hud_message(message, seconds)
    local cmd = get_cmd()
    if cmd then cmd.display_hud_message(message, seconds) end
end

function M.send_news_tip(sender_name, message, image, showtime)
    local cmd = get_cmd()
    if cmd then cmd.send_news_tip(sender_name, message, image, showtime) end
end

function M.play_sound(sound_name)
    local cmd = get_cmd()
    if cmd then cmd.play_sound(sound_name) end
end

--- Create a sound_object for the given path.
-- @param path string Sound path (e.g. "characters_voice\\talker_tts\\slot_1")
-- @return table|nil sound_object instance
function M.create_sound_object(path)
    if sound_object then
        return sound_object(path)
    end
    return nil
end

--- Sound mode constants for play() / play_no_feedback().
M.S3D = sound_object and sound_object.s3d or 0
M.S2D = sound_object and sound_object.s2d or 0

function M.exec_console_cmd(command)
    local cmd = get_cmd()
    if cmd then cmd.exec_console_cmd(command) end
end

function M.SendScriptCallback(callback_name, ...)
    local cmd = get_cmd()
    if cmd then cmd.SendScriptCallback(callback_name, ...) end
end

------------------------------------------------------------
-- Async / files
------------------------------------------------------------

function M.repeat_until_true(seconds, func, ...)
    local async = get_async()
    if async then async.repeat_until_true(seconds, func, ...) end
end

function M.get_base_path()
    local files = get_files()
    return files and files.get_base_path() or ""
end

------------------------------------------------------------
-- Time events and callbacks
------------------------------------------------------------

function M.create_time_event(event_id, action_id, delay, func)
    if CreateTimeEvent then
        CreateTimeEvent(event_id, action_id, delay, func)
    end
end

function M.reset_time_event(event_id, action_id)
    if ResetTimeEvent then
        ResetTimeEvent(event_id, action_id)
    end
end

function M.remove_time_event(event_id, action_id)
    if RemoveTimeEvent then
        RemoveTimeEvent(event_id, action_id)
    end
end

function M.register_callback(name, handler)
    if RegisterScriptCallback then
        RegisterScriptCallback(name, handler)
    end
end

------------------------------------------------------------
-- Unique timestamp (collision-free monotonic)
------------------------------------------------------------

local unique_ts_mod = require("domain.service.unique_ts")

--- Return a globally unique, monotonically increasing timestamp.
-- Delegates to domain.service.unique_ts.
-- @return number  unique timestamp (integer)
function M.unique_ts()
    return unique_ts_mod.unique_ts()
end

--- Reset unique_ts state (call on game load / new game).
function M.reset_unique_ts()
    unique_ts_mod.reset()
end

------------------------------------------------------------
-- printf wrapper (engine provides this in STALKER)
------------------------------------------------------------

function M.printf(fmt, ...)
    if printf then
        printf(fmt, ...)
    else
        print(string.format(fmt, ...))
    end
end

return M

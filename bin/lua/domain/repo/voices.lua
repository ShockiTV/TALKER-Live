-- domain/repo/voices.lua
-- Per-character voice ID resolved from the STALKER engine's sound_prefix.
-- npc:sound_prefix() returns e.g. "characters_voice\human\stalker_1\" which
-- maps exactly to the voice theme folder name in talker_bridge/voices/.
--
-- When the engine object is not loaded, assignment is deferred (nil in cache)
-- and retried on the next call. No faction-pool fallback is used.

package.path = package.path .. ";./bin/lua/?.lua;"
local log    = require("framework.logger")
local engine = require("interface.engine")

local M = {}

-- Cache of game_id (string) → voice_id (string)
local character_voices = {}

-- Resolve voice_id for a character via engine sound_prefix.
local function assign_voice(char)
    local id = tostring(char.game_id)

    -- Player gets no voice
    if id == "0" then
        character_voices[id] = ""
        return
    end

    -- Ask the engine for this NPC's actual voice theme
    local obj = engine.get_obj_by_id(char.game_id)
    if not obj then
        -- Object not yet loaded — defer; do NOT cache so we retry next call
        log.spam("voice_id: object not loaded for character %s, deferring", id)
        return
    end

    local voice_id = engine.get_sound_prefix(obj)
    if voice_id and voice_id ~= "" then
        character_voices[id] = voice_id
        log.spam("voice_id '%s' for character %s (sound_prefix)", voice_id, id)
    else
        log.warn("voice_id: no sound_prefix for character %s, storing empty", id)
        character_voices[id] = ""
    end
end

-- Get the voice_id for a character.
-- Assigns one on first call; returns "" for the player.
function M.get_voice(char)
    local id = tostring(char.game_id)
    local voice = character_voices[id]
    if voice == nil then
        assign_voice(char)
        voice = character_voices[id]
    end
    return voice or ""
end

-- Explicitly set a voice_id for a character (used by persistence).
function M.set_voice(game_id, voice_id)
    character_voices[tostring(game_id)] = voice_id
end

-- Return the full game_id → voice_id map (for save).
function M.get_all_voices()
    return character_voices
end

-- Replace the full cache (for load).
function M.set_all_voices(tbl)
    character_voices = tbl or {}
end

-- Clear the cache (mostly used in tests).
function M.clear()
    character_voices = {}
end

return M

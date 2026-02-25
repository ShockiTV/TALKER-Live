--- TTS slot manager for in-engine NPC audio playback.
-- Manages a pool of 200 pre-deployed slot files, allocates them round-robin,
-- writes TTS audio bytes, and plays via play_no_feedback() for fire-and-forget
-- 3D spatial audio at the NPC's position.
--
-- @module tts_slot

local engine = require("interface.engine")
local log = require("framework.logger")

local M = {}

------------------------------------------------------------
-- State
------------------------------------------------------------

local current_slot = 1  -- Round-robin counter (1-200)
local SLOT_COUNT = 200
local CACHE_FLUSH_INTERVAL = 100  -- Flush sound cache every N slots

-- Sound path for X-Ray sound_object (used for 2D fallback and duration query).
-- No .ogg extension — X-Ray appends it automatically.
local SLOT_PATH_PREFIX = "characters_voice\\talker_tts\\slot_"

-- Filesystem path for writing slot files (appended to $fs_root$).
local SOUNDS_SUBDIR = "gamedata\\sounds\\characters_voice\\talker_tts\\"

-- DEBUG: Force 2D audio to isolate whether OGG decoding works.
-- When true, plays on the player in 2D (no distance attenuation).
-- Set to false for production (3D spatial audio on NPC).
local FORCE_2D_DEBUG = false

------------------------------------------------------------
-- Slot allocation
------------------------------------------------------------

--- Allocate the next slot in round-robin order.
-- Returns the slot number (1-200) and increments the counter.
-- Issues snd_restart every CACHE_FLUSH_INTERVAL slots (at 100 and 200)
-- so X-Ray re-reads the files we're about to overwrite.
-- The ~100 slot gap between flush and reuse gives the engine time to
-- complete the async cache reload.
--
-- @return number Allocated slot number (1-200)
function M.allocate()
    local slot = current_slot
    
    -- Increment and wrap
    current_slot = current_slot + 1
    if current_slot > SLOT_COUNT then
        current_slot = 1
    end
    
    -- Trigger cache flush at interval boundaries (100, 200, etc.)
    -- This flushes the NEXT batch of slots we'll overwrite, giving
    -- ~100 slots of lead time before we reuse them.
    if slot % CACHE_FLUSH_INTERVAL == 0 then
        log.info("TTS slot %d reached, issuing snd_restart (next batch: %d-%d)",
            slot, slot + 1, math.min(slot + CACHE_FLUSH_INTERVAL, SLOT_COUNT))
        engine.exec_console_cmd("snd_restart")
    end
    
    return slot
end

------------------------------------------------------------
-- Slot file I/O
------------------------------------------------------------

--- Write OGG audio bytes to the specified slot file.
-- Resolves the slot file path and writes raw binary data.
--
-- @param slot_num number Slot number (1-200)
-- @param ogg_bytes string Raw OGG Vorbis bytes
-- @return boolean true if write succeeded, false on error
function M.write_slot(slot_num, ogg_bytes)
    if not ogg_bytes or #ogg_bytes == 0 then
        log.warn("TTS write_slot: empty audio data for slot %d", slot_num)
        return false
    end
    
    -- Resolve absolute filesystem path via $fs_root$
    -- e.g. "F:\GAMMA\anomaly\gamedata\sounds\characters_voice\talker_tts\slot_3.ogg"
    local base = engine.get_base_path()
    local filename = string.format("slot_%d.ogg", slot_num)
    local filepath = base .. SOUNDS_SUBDIR .. filename
    
    -- Write binary data
    local file, err = io.open(filepath, "wb")
    if not file then
        log.error("TTS write_slot: failed to open %s for writing: %s", filepath, err or "unknown error")
        return false
    end
    
    file:write(ogg_bytes)
    file:close()
    
    log.debug("TTS wrote %d bytes to slot %d (%s)", #ogg_bytes, slot_num, filepath)
    return true
end

------------------------------------------------------------
-- Audio playback (fire-and-forget)
------------------------------------------------------------

--- Play audio from the specified slot on the given NPC.
-- For 3D: uses play_no_feedback() for fire-and-forget spatial audio
-- at the NPC's position (proven pattern from xr_wounded.script).
-- Falls back to 2D audio on the player if NPC is nil/dead.
--
-- @param slot_num number Slot number (1-200)
-- @param npc_obj table|nil NPC game object
-- @return table|nil sound_object instance, or nil on error
function M.play_on_npc(slot_num, npc_obj)
    -- Resolve sound path (characters_voice\talker_tts\slot_N, no .ogg extension)
    local sound_path = SLOT_PATH_PREFIX .. tostring(slot_num)

    -- Create sound_object via engine facade
    local snd = engine.create_sound_object(sound_path)
    if not snd then
        log.error("TTS play_on_npc: failed to create sound_object for %s", sound_path)
        return nil
    end

    -- Check if NPC is valid and alive
    local use_3d = npc_obj and engine.is_alive(npc_obj)

    if use_3d and not FORCE_2D_DEBUG then
        -- Fire-and-forget 3D playback at NPC position.
        -- play_no_feedback: proven pattern from xr_wounded.script.
        -- Args: (obj, flags, delay, pos, volume, frequency)
        local pos = engine.get_position(npc_obj)
        snd:play_no_feedback(npc_obj, engine.S3D, 0, pos, 1, 1)
        log.info("TTS playing slot %d on NPC via play_no_feedback (3D)", slot_num)
    else
        -- 2D audio on player actor
        local player = engine.get_player()
        if player then
            snd:play(player, 0, engine.S2D)
            snd.volume = 1
            snd.frequency = 1
            if FORCE_2D_DEBUG then
                log.info("TTS playing slot %d on player (2D DEBUG mode)", slot_num)
            else
                log.warn("TTS playing slot %d on player (2D fallback, NPC unavailable)", slot_num)
            end
        else
            log.error("TTS play_on_npc: no player available, cannot play audio")
            return nil
        end
    end

    return snd
end

------------------------------------------------------------
-- Testing/debug helpers
------------------------------------------------------------

--- Get current slot counter value (for testing)
function M._get_current_slot()
    return current_slot
end

--- Reset slot counter to 1 (for testing)
function M._reset_counter()
    current_slot = 1
end

return M

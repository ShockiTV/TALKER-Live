--- TTS slot manager for in-engine NPC audio playback.
-- Manages a pool of 200 pre-deployed slot files, allocates them round-robin,
-- writes TTS audio bytes, and plays via play_at_pos() with a set_position()
-- tracking loop so the audio source follows the NPC in real-time.
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

-- Persistent references to in-flight sound_objects.
-- Keyed by slot_num.  Prevents Lua GC from collecting the luabind
-- userdata (whose C++ destructor calls stop()) while audio is playing.
-- Cleared by the tracking / polling loop when playback finishes.
local active_sounds = {}

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
        local next_start = (slot % SLOT_COUNT) + 1
        local next_end = math.min(next_start + CACHE_FLUSH_INTERVAL - 1, SLOT_COUNT)
        log.info("TTS slot %d reached, issuing snd_restart (next batch: %d-%d)",
            slot, next_start, next_end)
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
-- Position-tracking playback
------------------------------------------------------------

--- Start a tracking loop that updates the sound position to follow the NPC.
-- Uses CreateTimeEvent (via engine facade) to tick each engine frame.
-- The callback returns false to keep ticking, true to self-remove.
-- Maintains a tick counter for diagnostics (low count = GC truncation).
--
-- @param snd table sound_object instance (must be playing)
-- @param npc_obj table NPC game object
-- @param slot_num number Slot number (used for unique event key)
local function start_tracking(snd, npc_obj, slot_num)
    local event_id = "talker_tts_track"
    local action_id = "slot_" .. slot_num
    local ticks = 0

    engine.create_time_event(event_id, action_id, 0, function()
        ticks = ticks + 1

        -- Stop tracking when sound finishes
        if not snd:playing() then
            active_sounds[slot_num] = nil
            log.debug("TTS tracking slot %d: sound finished after %d ticks, removing", slot_num, ticks)
            return true
        end

        -- Stop tracking when NPC becomes invalid (despawned/nil position)
        local pos = engine.get_position(npc_obj)
        if not pos then
            active_sounds[slot_num] = nil
            log.debug("TTS tracking slot %d: NPC position nil after %d ticks, removing", slot_num, ticks)
            return true
        end

        -- Update sound position to follow NPC
        snd:set_position(pos)
        return false
    end)
end

--- Start a simplified polling loop for 2D playback.
-- Only checks snd:playing() and releases the active_sounds reference
-- when done.  No position tracking needed for 2D audio.
--
-- @param snd table sound_object instance (must be playing)
-- @param slot_num number Slot number (used for unique event key)
local function start_2d_poll(snd, slot_num)
    local event_id = "talker_tts_track"
    local action_id = "slot_" .. slot_num
    local ticks = 0

    engine.create_time_event(event_id, action_id, 0, function()
        ticks = ticks + 1

        if not snd:playing() then
            active_sounds[slot_num] = nil
            log.debug("TTS 2D poll slot %d: sound finished after %d ticks, removing", slot_num, ticks)
            return true
        end

        return false
    end)
end

--- Play audio from the specified slot on the given NPC.
-- For 3D: uses play_at_pos() with a set_position() tracking loop so
-- the audio source follows the NPC in real-time (proven pattern from
-- ph_sound.script). Falls back to 2D audio on the player if NPC is nil/dead.
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

    -- Store persistent reference BEFORE play to prevent GC
    active_sounds[slot_num] = snd

    -- Check if NPC is valid and alive
    local use_3d = npc_obj and engine.is_alive(npc_obj)

    if use_3d and not FORCE_2D_DEBUG then
        -- 3D playback at NPC position with position tracking.
        -- play_at_pos + set_position loop: proven pattern from ph_sound.script.
        local pos = engine.get_position(npc_obj)
        snd:play_at_pos(npc_obj, pos, 0, engine.S3D)
        start_tracking(snd, npc_obj, slot_num)
        log.info("TTS playing slot %d on NPC via play_at_pos (3D tracking)", slot_num)
    else
        -- 2D audio on player actor
        local player = engine.get_player()
        if player then
            snd:play(player, 0, engine.S2D)
            start_2d_poll(snd, slot_num)
            if FORCE_2D_DEBUG then
                log.info("TTS playing slot %d on player (2D DEBUG mode)", slot_num)
            else
                log.warn("TTS playing slot %d on player (2D fallback, NPC unavailable)", slot_num)
            end
        else
            active_sounds[slot_num] = nil
            log.error("TTS play_on_npc: no player available, cannot play audio")
            return nil
        end
    end

    snd.volume = 1
    snd.frequency = 1

    return snd
end

------------------------------------------------------------
-- Testing/debug helpers
------------------------------------------------------------

--- Get current slot counter value (for testing)
function M._get_current_slot()
    return current_slot
end

--- Flush X-Ray sound cache.
-- Call on game load to purge any stale cached slot audio from a
-- previous save/session.  Also resets the round-robin counter so
-- fresh writes start from slot 1.
function M.flush_cache()
    current_slot = 1
    active_sounds = {}
    engine.exec_console_cmd("snd_restart")
    log.info("TTS flush_cache: snd_restart issued, slot counter reset to 1, active_sounds cleared")
end

--- Reset slot counter to 1 (for testing)
function M._reset_counter()
    current_slot = 1
    active_sounds = {}
end

--- Get number of active (playing) sounds (for testing/diagnostics)
function M._get_active_count()
    local count = 0
    for _ in pairs(active_sounds) do
        count = count + 1
    end
    return count
end

return M

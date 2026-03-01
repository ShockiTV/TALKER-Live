package.path = package.path .. ";./bin/lua/?.lua;"
require("tests.test_bootstrap")

local mock_engine = require("tests.mocks.mock_engine")
local tts_slot = require("domain.service.tts_slot")

-- Test tracking
local test_state = {
    console_commands = {},  -- Track console commands executed
    written_files = {},     -- Track file writes
    sound_played = nil,     -- Track sound playback
}

-- Override engine functions to track calls
local original_io_open = io.open
local function mock_io_open(path, mode)
    if mode == "wb" then
        -- Track write operations
        test_state.written_files[path] = true
        -- Return a mock file handle
        return {
            write = function(self, data)
                test_state.written_files[path] = data
            end,
            close = function(self) end
        }
    end
    return original_io_open(path, mode)
end

-- Mock console command execution
mock_engine._set("exec_console_cmd", function(cmd)
    table.insert(test_state.console_commands, cmd)
end)

-- Helper: reset test state
local function reset_state()
    test_state.console_commands = {}
    test_state.written_files = {}
    test_state.sound_played = nil
    tts_slot._reset_counter()
    mock_engine._reset()
    
    -- Re-apply overrides
    mock_engine._set("exec_console_cmd", function(cmd)
        table.insert(test_state.console_commands, cmd)
    end)
end

-- Test 1: Sequential allocation
local function test_allocation_sequence()
    reset_state()
    
    local slot1 = tts_slot.allocate()
    local slot2 = tts_slot.allocate()
    local slot3 = tts_slot.allocate()
    
    assert(slot1 == 1, "First slot should be 1")
    assert(slot2 == 2, "Second slot should be 2")
    assert(slot3 == 3, "Third slot should be 3")
    
    print("✓ Test 1: Sequential allocation")
end

-- Test 1b: flush_cache issues snd_restart and resets counter
local function test_flush_cache()
    reset_state()
    
    -- Advance the counter
    tts_slot.allocate()
    tts_slot.allocate()
    assert(tts_slot._get_current_slot() == 3, "Counter should be at 3")
    test_state.console_commands = {}  -- clear any commands from allocate
    
    -- flush_cache resets counter and issues snd_restart
    tts_slot.flush_cache()
    assert(tts_slot._get_current_slot() == 1, "Counter should reset to 1 after flush")
    assert(#test_state.console_commands == 1,
        string.format("flush_cache should issue snd_restart (got %d commands)", #test_state.console_commands))
    assert(test_state.console_commands[1] == "snd_restart", "Command should be snd_restart")
    
    -- Next allocation should return 1
    local slot = tts_slot.allocate()
    assert(slot == 1, "First slot after flush should be 1")
    
    print("\226\156\147 Test 1b: flush_cache resets counter and flushes sound cache")
end

-- Test 2: snd_restart fires at cache flush interval (slot 100)
local function test_cache_flush_at_interval()
    reset_state()
    
    -- Allocate 100 slots to reach first interval boundary
    for i = 1, 100 do
        tts_slot.allocate()
    end
    
    -- snd_restart should trigger once at interval (slot 100)
    assert(#test_state.console_commands == 1,
        string.format("snd_restart should trigger at interval (got %d commands)", #test_state.console_commands))
    assert(test_state.console_commands[1] == "snd_restart", "Command should be snd_restart")

    -- Next allocation should return 101 (not wrapped yet)
    local slot101 = tts_slot.allocate()
    assert(slot101 == 101, "Should return slot 101 after interval flush")
    
    print("✓ Test 2: snd_restart fires at cache flush interval (slot 100)")
end

-- Test 3: No snd_restart before interval boundary
local function test_no_restart_before_interval()
    reset_state()
    
    -- Allocate 50 slots (no interval boundary)
    for i = 1, 50 do
        tts_slot.allocate()
    end
    
    assert(#test_state.console_commands == 0, "snd_restart should not fire during normal allocation")
    
    print("\226\156\147 Test 3: No snd_restart before interval boundary")
end

-- Test 4: write_slot delegates to io.open
local function test_write_delegates_to_io_open()
    reset_state()
    
    -- Temporarily replace io.open
    local original_open = io.open
    io.open = mock_io_open
    
    local test_data = "OggS test data"
    local success = tts_slot.write_slot(5, test_data)
    
    assert(success, "write_slot should return true on success")
    assert(test_state.written_files["gamedata\\sounds\\characters_voice\\talker_tts\\slot_5.ogg"] == test_data,
        "Data should be written to correct file")
    
    -- Restore io.open
    io.open = original_open
    
    print("✓ Test 4: write_slot delegates to io.open")
end

-- Test 5: Empty data returns false
local function test_write_empty_data()
    reset_state()
    
    local success1 = tts_slot.write_slot(1, "")
    local success2 = tts_slot.write_slot(1, nil)
    
    assert(not success1, "Empty string should return false")
    assert(not success2, "Nil data should return false")
    
    print("✓ Test 5: Empty data returns false")
end

-- Test 6: play_on_npc with alive NPC uses play_at_pos (3D) and starts tracking
local function test_play_3d_on_alive_npc()
    reset_state()
    
    -- Mock a live NPC
    local mock_npc = {
        id = 5,
        alive = function() return true end
    }
    mock_engine._set("is_alive", true)
    mock_engine._set("get_id", 5)
    mock_engine._set("get_player", { id = 0 })
    mock_engine._set("get_position", { x = 10, y = 0, z = 20 })
    
    -- Track create_time_event calls
    local time_event_calls = {}
    mock_engine._set("create_time_event", function(event_id, action_id, delay, func)
        table.insert(time_event_calls, {
            event_id = event_id,
            action_id = action_id,
            delay = delay,
            func = func
        })
    end)
    
    -- Mock sound_object with play_at_pos
    local sound_object_mock = {
        s3d = "s3d",
        s2d = "s2d"
    }
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            return {
                play = function(_, obj, delay, mode)
                    test_state.sound_played = {
                        path = path,
                        obj = obj,
                        mode = mode
                    }
                end,
                play_at_pos = function(_, obj, pos, delay, mode)
                    test_state.sound_played = {
                        path = path,
                        obj = obj,
                        mode = mode,
                        pos = pos,
                        delay = delay,
                        used_play_at_pos = true
                    }
                end,
                playing = function() return true end,
                set_position = function() end,
                stop = function() test_state.sound_stopped = true end,
                length = function() return 3.0 end
            }
        end
    })
    _G.sound_object = sound_object_mock
    
    local snd = tts_slot.play_on_npc(10, mock_npc)
    
    assert(snd ~= nil, "Should return sound_object")
    assert(test_state.sound_played ~= nil, "Should have played sound")
    assert(test_state.sound_played.used_play_at_pos, "Should use play_at_pos for 3D")
    assert(test_state.sound_played.mode == "s3d", "Should use s3d mode")
    assert(test_state.sound_played.obj == mock_npc, "Should play on NPC object")
    assert(test_state.sound_played.pos.x == 10, "Position x should match NPC")
    assert(test_state.sound_played.delay == 0, "Delay should be 0")
    
    -- Verify tracking was started
    assert(#time_event_calls == 1, "Should register one time event for tracking")
    assert(time_event_calls[1].event_id == "talker_tts_track", "Event ID should be talker_tts_track")
    assert(time_event_calls[1].action_id == "slot_10", "Action ID should be slot_10")
    assert(time_event_calls[1].delay == 0, "Delay should be 0")
    assert(type(time_event_calls[1].func) == "function", "Should register a callback function")
    
    print("✓ Test 6: play_on_npc uses play_at_pos for 3D NPC audio with tracking")
end

-- Test 7: play_on_npc falls back to 2D when NPC is nil (no tracking)
local function test_play_2d_when_npc_nil()
    reset_state()
    
    mock_engine._set("is_alive", false)
    mock_engine._set("get_player", { id = 0 })
    
    -- Track create_time_event calls — 2D now starts a poll loop
    local time_event_calls = {}
    mock_engine._set("create_time_event", function(event_id, action_id, delay, func)
        table.insert(time_event_calls, { event_id = event_id, action_id = action_id, func = func })
    end)
    
    -- Mock sound_object
    local sound_object_mock = {
        s3d = "s3d",
        s2d = "s2d"
    }
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            return {
                play = function(_, obj, delay, mode)
                    test_state.sound_played = {
                        path = path,
                        obj = obj,
                        mode = mode
                    }
                end,
                play_at_pos = function(_, obj, pos, delay, mode)
                    test_state.sound_played = {
                        path = path,
                        used_play_at_pos = true
                    }
                end,
                playing = function() return true end,
                set_position = function() end,
                stop = function() test_state.sound_stopped = true end,
                length = function() return 2.0 end
            }
        end
    })
    _G.sound_object = sound_object_mock
    
    local snd = tts_slot.play_on_npc(10, nil)
    
    assert(snd ~= nil, "Should return sound_object")
    assert(test_state.sound_played.mode == "s2d", "Should use 2D mode when NPC is nil")
    assert(not test_state.sound_played.used_play_at_pos, "Should NOT use play_at_pos for 2D")
    -- 2D now starts a simplified poll loop for GC protection
    assert(#time_event_calls == 1, "Should start 2D poll loop")
    assert(time_event_calls[1].action_id == "slot_10", "2D poll should use slot action_id")
    
    print("✓ Test 7: play_on_npc falls back to 2D with poll loop")
end

-- Test 7b: Tracking loop calls set_position and returns false to keep ticking
local function test_tracking_loop_updates_position()
    reset_state()
    
    local mock_npc = { id = 5, alive = function() return true end }
    mock_engine._set("is_alive", true)
    mock_engine._set("get_player", { id = 0 })
    
    -- Initial position for play_at_pos
    mock_engine._set("get_position", { x = 10, y = 0, z = 20 })
    
    -- Capture the tracking callback
    local tracking_callback = nil
    mock_engine._set("create_time_event", function(event_id, action_id, delay, func)
        tracking_callback = func
    end)
    
    -- Track set_position calls on the sound object
    local set_position_calls = {}
    local sound_object_mock = { s3d = "s3d", s2d = "s2d" }
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            return {
                play_at_pos = function() end,
                play = function() end,
                playing = function() return true end,
                set_position = function(_, pos)
                    table.insert(set_position_calls, pos)
                end,
                stop = function() end,
                length = function() return 3.0 end
            }
        end
    })
    _G.sound_object = sound_object_mock
    
    tts_slot.play_on_npc(10, mock_npc)
    
    assert(tracking_callback ~= nil, "Tracking callback should be captured")
    
    -- Update NPC position before ticking
    mock_engine._set("get_position", { x = 15, y = 0, z = 25 })
    
    -- Tick the callback — sound still playing, NPC valid
    local result = tracking_callback()
    
    assert(result == false, "Tracking loop should return false to keep ticking")
    assert(#set_position_calls == 1, "Should have called set_position once")
    assert(set_position_calls[1].x == 15, "set_position should use updated NPC position")
    assert(set_position_calls[1].z == 25, "set_position z should match updated position")
    
    print("✓ Test 7b: Tracking loop calls set_position and returns false")
end

-- Test 7c: Tracking loop returns true when sound finishes (playing() == false)
local function test_tracking_loop_stops_when_finished()
    reset_state()
    
    local mock_npc = { id = 5, alive = function() return true end }
    mock_engine._set("is_alive", true)
    mock_engine._set("get_player", { id = 0 })
    mock_engine._set("get_position", { x = 10, y = 0, z = 20 })
    
    local tracking_callback = nil
    mock_engine._set("create_time_event", function(event_id, action_id, delay, func)
        tracking_callback = func
    end)
    
    -- Sound that reports not playing
    local is_playing = true
    local sound_object_mock = { s3d = "s3d", s2d = "s2d" }
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            return {
                play_at_pos = function() end,
                play = function() end,
                playing = function() return is_playing end,
                set_position = function() end,
                stop = function() end,
                length = function() return 3.0 end
            }
        end
    })
    _G.sound_object = sound_object_mock
    
    tts_slot.play_on_npc(10, mock_npc)
    assert(tracking_callback ~= nil, "Tracking callback should be captured")
    
    -- First tick: still playing → returns false
    local result1 = tracking_callback()
    assert(result1 == false, "Should return false while still playing")
    
    -- Sound finishes
    is_playing = false
    local result2 = tracking_callback()
    assert(result2 == true, "Should return true when sound finished (self-remove)")
    
    print("✓ Test 7c: Tracking loop returns true when sound finishes")
end

-- Test 7d: Tracking loop returns true when NPC position is nil (despawned)
local function test_tracking_loop_stops_when_npc_despawned()
    reset_state()
    
    local mock_npc = { id = 5, alive = function() return true end }
    mock_engine._set("is_alive", true)
    mock_engine._set("get_player", { id = 0 })
    
    -- Position: valid initially
    mock_engine._set("get_position", { x = 10, y = 0, z = 20 })
    
    local tracking_callback = nil
    mock_engine._set("create_time_event", function(event_id, action_id, delay, func)
        tracking_callback = func
    end)
    
    local sound_object_mock = { s3d = "s3d", s2d = "s2d" }
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            return {
                play_at_pos = function() end,
                play = function() end,
                playing = function() return true end,
                set_position = function() end,
                stop = function() end,
                length = function() return 3.0 end
            }
        end
    })
    _G.sound_object = sound_object_mock
    
    tts_slot.play_on_npc(10, mock_npc)
    assert(tracking_callback ~= nil, "Tracking callback should be captured")
    
    -- First tick: NPC valid → returns false
    local result1 = tracking_callback()
    assert(result1 == false, "Should return false while NPC is valid")
    
    -- NPC despawns (position becomes nil/false — mock_engine can't store nil)
    mock_engine._set("get_position", false)
    local result2 = tracking_callback()
    assert(result2 == true, "Should return true when NPC position is nil (self-remove)")
    
    print("✓ Test 7d: Tracking loop returns true when NPC despawned")
end

-- Test 7e: Concurrent tracking loops are independent (different slot numbers)
local function test_concurrent_tracking_independent()
    reset_state()

    local mock_npc_a = { id = 1, alive = function() return true end }
    local mock_npc_b = { id = 2, alive = function() return true end }
    mock_engine._set("is_alive", true)
    mock_engine._set("get_player", { id = 0 })
    mock_engine._set("get_position", { x = 10, y = 0, z = 20 })

    local time_event_calls = {}
    mock_engine._set("create_time_event", function(event_id, action_id, delay, func)
        table.insert(time_event_calls, {
            event_id = event_id,
            action_id = action_id,
            func = func
        })
    end)

    local sound_object_mock = { s3d = "s3d", s2d = "s2d" }
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            return {
                play_at_pos = function() end,
                play = function() end,
                playing = function() return true end,
                set_position = function() end,
                stop = function() end,
                length = function() return 3.0 end
            }
        end
    })
    _G.sound_object = sound_object_mock

    tts_slot.play_on_npc(5, mock_npc_a)
    tts_slot.play_on_npc(8, mock_npc_b)

    assert(#time_event_calls == 2, "Should register two separate time events")
    assert(time_event_calls[1].action_id == "slot_5", "First tracking should use slot_5")
    assert(time_event_calls[2].action_id == "slot_8", "Second tracking should use slot_8")
    assert(time_event_calls[1].event_id == "talker_tts_track", "Both use same event_id")
    assert(time_event_calls[2].event_id == "talker_tts_track", "Both use same event_id")

    print("✓ Test 7e: Concurrent tracking loops are independent")
end

-- Test 7f: Slot reuse replaces previous tracking (same slot number)
local function test_slot_reuse_replaces_tracking()
    reset_state()

    local mock_npc = { id = 1, alive = function() return true end }
    mock_engine._set("is_alive", true)
    mock_engine._set("get_player", { id = 0 })
    mock_engine._set("get_position", { x = 10, y = 0, z = 20 })

    local time_event_calls = {}
    mock_engine._set("create_time_event", function(event_id, action_id, delay, func)
        table.insert(time_event_calls, {
            event_id = event_id,
            action_id = action_id,
            func = func
        })
    end)

    local sound_object_mock = { s3d = "s3d", s2d = "s2d" }
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            return {
                play_at_pos = function() end,
                play = function() end,
                playing = function() return true end,
                set_position = function() end,
                stop = function() end,
                length = function() return 3.0 end
            }
        end
    })
    _G.sound_object = sound_object_mock

    tts_slot.play_on_npc(5, mock_npc)
    tts_slot.play_on_npc(5, mock_npc)

    assert(#time_event_calls == 2, "Should register two time events")
    assert(time_event_calls[1].action_id == "slot_5", "First uses slot_5")
    assert(time_event_calls[2].action_id == "slot_5", "Second uses same slot_5 (replaces)")
    -- Both calls use the same event_id + action_id, so CreateTimeEvent replaces the first
    assert(time_event_calls[1].func ~= time_event_calls[2].func,
        "Callbacks should be different function instances")

    print("✓ Test 7f: Slot reuse replaces previous tracking (same action_id)")
end

-- Test 8: Wrap-around at 200 slots, second snd_restart fires
local function test_wrap_at_200()
    reset_state()
    
    -- Allocate all 200 slots
    for i = 1, 200 do
        tts_slot.allocate()
    end
    
    -- snd_restart should fire twice: at slot 100 and slot 200
    assert(#test_state.console_commands == 2,
        string.format("snd_restart should fire 2x (got %d commands)", #test_state.console_commands))
    
    -- Next allocation wraps back to 1
    local slot1 = tts_slot.allocate()
    assert(slot1 == 1, "Should return slot 1 after full wrap")
    
    print("✓ Test 8: Wrap-around at 200 slots with double snd_restart")
end

------------------------------------------------------------
-- GC-fix tests: active_sounds persistent references
------------------------------------------------------------

-- Helper: create standard mock sound_object constructor
local function make_sound_mock(is_playing_val)
    local playing_val = is_playing_val
    if playing_val == nil then playing_val = true end
    local sound_object_mock = { s3d = "s3d", s2d = "s2d" }
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            return {
                play_at_pos = function() end,
                play = function() end,
                playing = function() return playing_val end,
                set_position = function() end,
                stop = function() end,
                length = function() return 3.0 end,
                _set_playing = function(_, val) playing_val = val end,
            }
        end
    })
    return sound_object_mock, function(val) playing_val = val end
end

-- Test 9: play_on_npc stores reference in active_sounds (3D)
local function test_play_stores_active_reference()
    reset_state()

    local mock_npc = { id = 5, alive = function() return true end }
    mock_engine._set("is_alive", true)
    mock_engine._set("get_player", { id = 0 })
    mock_engine._set("get_position", { x = 10, y = 0, z = 20 })
    mock_engine._set("create_time_event", function() end)

    _G.sound_object = make_sound_mock(true)

    assert(tts_slot._get_active_count() == 0, "Should start with 0 active sounds")

    tts_slot.play_on_npc(7, mock_npc)

    assert(tts_slot._get_active_count() == 1,
        string.format("Should have 1 active sound after play (got %d)", tts_slot._get_active_count()))

    print("✓ Test 9: play_on_npc stores reference in active_sounds")
end

-- Test 10: Tracking loop completion clears active_sounds entry
local function test_tracking_clears_active_on_finish()
    reset_state()

    local mock_npc = { id = 5, alive = function() return true end }
    mock_engine._set("is_alive", true)
    mock_engine._set("get_player", { id = 0 })
    mock_engine._set("get_position", { x = 10, y = 0, z = 20 })

    local tracking_cb = nil
    mock_engine._set("create_time_event", function(_, _, _, func)
        tracking_cb = func
    end)

    local _, set_playing = make_sound_mock(true)
    _G.sound_object = make_sound_mock(true)
    -- Need to re-capture set_playing for the actual sound object
    local actual_playing = true
    local sound_object_mock = { s3d = "s3d", s2d = "s2d" }
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            return {
                play_at_pos = function() end,
                play = function() end,
                playing = function() return actual_playing end,
                set_position = function() end,
                stop = function() end,
                length = function() return 3.0 end,
            }
        end
    })
    _G.sound_object = sound_object_mock

    tts_slot.play_on_npc(7, mock_npc)
    assert(tts_slot._get_active_count() == 1, "Should have 1 active sound")

    -- Tick once while playing
    local r1 = tracking_cb()
    assert(r1 == false, "Should keep ticking while playing")
    assert(tts_slot._get_active_count() == 1, "Still 1 active sound while playing")

    -- Sound finishes
    actual_playing = false
    local r2 = tracking_cb()
    assert(r2 == true, "Should self-remove when done")
    assert(tts_slot._get_active_count() == 0,
        string.format("Should have 0 active sounds after finish (got %d)", tts_slot._get_active_count()))

    print("✓ Test 10: Tracking loop completion clears active_sounds entry")
end

-- Test 11: flush_cache clears active_sounds
local function test_flush_cache_clears_active_sounds()
    reset_state()

    local mock_npc = { id = 5, alive = function() return true end }
    mock_engine._set("is_alive", true)
    mock_engine._set("get_player", { id = 0 })
    mock_engine._set("get_position", { x = 10, y = 0, z = 20 })
    mock_engine._set("create_time_event", function() end)

    _G.sound_object = make_sound_mock(true)

    tts_slot.play_on_npc(3, mock_npc)
    tts_slot.play_on_npc(7, mock_npc)
    assert(tts_slot._get_active_count() == 2, "Should have 2 active sounds")

    -- Re-apply console_cmd mock for flush
    test_state.console_commands = {}
    mock_engine._set("exec_console_cmd", function(cmd)
        table.insert(test_state.console_commands, cmd)
    end)

    tts_slot.flush_cache()
    assert(tts_slot._get_active_count() == 0,
        string.format("Should have 0 active sounds after flush (got %d)", tts_slot._get_active_count()))

    print("✓ Test 11: flush_cache clears active_sounds")
end

-- Test 12: 2D fallback also stores reference in active_sounds
local function test_2d_fallback_stores_active_reference()
    reset_state()

    mock_engine._set("is_alive", false)
    mock_engine._set("get_player", { id = 0 })

    local poll_cb = nil
    mock_engine._set("create_time_event", function(_, _, _, func)
        poll_cb = func
    end)

    local actual_playing = true
    local sound_object_mock = { s3d = "s3d", s2d = "s2d" }
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            return {
                play_at_pos = function() end,
                play = function() end,
                playing = function() return actual_playing end,
                set_position = function() end,
                stop = function() end,
                length = function() return 2.0 end,
            }
        end
    })
    _G.sound_object = sound_object_mock

    tts_slot.play_on_npc(12, nil)
    assert(tts_slot._get_active_count() == 1,
        string.format("2D fallback should store active reference (got %d)", tts_slot._get_active_count()))

    -- Poll loop should eventually clear
    assert(poll_cb ~= nil, "2D poll callback should be set")
    actual_playing = false
    local result = poll_cb()
    assert(result == true, "2D poll should self-remove when done")
    assert(tts_slot._get_active_count() == 0,
        string.format("active_sounds should be 0 after 2D poll finish (got %d)", tts_slot._get_active_count()))

    print("✓ Test 12: 2D fallback stores and clears active_sounds reference")
end

-- Test 13: Concurrent playback on different slots maintains independent entries
local function test_concurrent_active_sounds_independent()
    reset_state()

    local mock_npc_a = { id = 1, alive = function() return true end }
    local mock_npc_b = { id = 2, alive = function() return true end }
    mock_engine._set("is_alive", true)
    mock_engine._set("get_player", { id = 0 })
    mock_engine._set("get_position", { x = 10, y = 0, z = 20 })

    local callbacks = {}
    mock_engine._set("create_time_event", function(event_id, action_id, delay, func)
        callbacks[action_id] = func
    end)

    -- Each play_on_npc creates a distinct sound_object, so we need a mock that
    -- allows independent per-instance playing state.
    local playing_states = {}
    local sound_object_mock = { s3d = "s3d", s2d = "s2d" }
    local snd_counter = 0
    setmetatable(sound_object_mock, {
        __call = function(self, path)
            snd_counter = snd_counter + 1
            local my_id = snd_counter
            playing_states[my_id] = true
            return {
                play_at_pos = function() end,
                play = function() end,
                playing = function() return playing_states[my_id] end,
                set_position = function() end,
                stop = function() end,
                length = function() return 3.0 end,
                _id = my_id,
            }
        end
    })
    _G.sound_object = sound_object_mock

    tts_slot.play_on_npc(5, mock_npc_a)
    tts_slot.play_on_npc(8, mock_npc_b)

    assert(tts_slot._get_active_count() == 2,
        string.format("Should have 2 active sounds (got %d)", tts_slot._get_active_count()))

    -- Finish slot 5 only
    playing_states[1] = false
    local r5 = callbacks["slot_5"]()
    assert(r5 == true, "Slot 5 tracking should self-remove")
    assert(tts_slot._get_active_count() == 1,
        string.format("Should have 1 active sound after slot 5 finishes (got %d)", tts_slot._get_active_count()))

    -- Slot 8 still active
    local r8 = callbacks["slot_8"]()
    assert(r8 == false, "Slot 8 tracking should keep ticking")

    -- Finish slot 8
    playing_states[2] = false
    local r8b = callbacks["slot_8"]()
    assert(r8b == true, "Slot 8 tracking should self-remove")
    assert(tts_slot._get_active_count() == 0,
        string.format("Should have 0 active sounds after both finish (got %d)", tts_slot._get_active_count()))

    print("✓ Test 13: Concurrent playback maintains independent active_sounds entries")
end

-- Run all tests
local function run_tests()
    print("Running TTS slot manager tests...")
    print()
    
    local tests = {
        test_allocation_sequence,
        test_flush_cache,
        test_cache_flush_at_interval,
        test_no_restart_before_interval,
        test_write_delegates_to_io_open,
        test_write_empty_data,
        test_play_3d_on_alive_npc,
        test_play_2d_when_npc_nil,
        test_tracking_loop_updates_position,
        test_tracking_loop_stops_when_finished,
        test_tracking_loop_stops_when_npc_despawned,
        test_concurrent_tracking_independent,
        test_slot_reuse_replaces_tracking,
        test_wrap_at_200,
        -- GC-fix tests
        test_play_stores_active_reference,
        test_tracking_clears_active_on_finish,
        test_flush_cache_clears_active_sounds,
        test_2d_fallback_stores_active_reference,
        test_concurrent_active_sounds_independent,
    }
    
    local passed = 0
    local failed = 0
    
    for _, test in ipairs(tests) do
        local status, err = pcall(test)
        if status then
            passed = passed + 1
        else
            failed = failed + 1
            print("✗ Test failed: " .. tostring(err))
        end
    end
    
    print()
    print(string.format("Results: %d passed, %d failed", passed, failed))
    
    if failed > 0 then
        os.exit(1)
    end
end

run_tests()

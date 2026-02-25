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

-- Test 2: snd_restart fires at cache flush interval (slot 100)
local function test_cache_flush_at_interval()
    reset_state()
    
    -- Allocate 100 slots to reach first interval boundary
    for i = 1, 100 do
        tts_slot.allocate()
    end
    
    -- snd_restart should trigger when slot 100 is allocated (100 % 100 == 0)
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
    
    print("✓ Test 3: No snd_restart before interval boundary")
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

-- Test 6: play_on_npc with alive NPC uses play_no_feedback (3D)
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
    
    -- Mock sound_object with play_no_feedback
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
                play_no_feedback = function(_, obj, mode, delay, pos, vol, freq)
                    test_state.sound_played = {
                        path = path,
                        obj = obj,
                        mode = mode,
                        pos = pos,
                        volume = vol,
                        frequency = freq,
                        used_play_no_feedback = true
                    }
                end,
                playing = function() return true end,
                stop = function() test_state.sound_stopped = true end,
                length = function() return 3.0 end
            }
        end
    })
    _G.sound_object = sound_object_mock
    
    local snd = tts_slot.play_on_npc(10, mock_npc)
    
    assert(snd ~= nil, "Should return sound_object")
    assert(test_state.sound_played ~= nil, "Should have played sound")
    assert(test_state.sound_played.used_play_no_feedback, "Should use play_no_feedback for 3D")
    assert(test_state.sound_played.mode == "s3d", "Should use s3d mode")
    assert(test_state.sound_played.volume == 1, "Volume should be 1")
    assert(test_state.sound_played.frequency == 1, "Frequency should be 1")
    assert(test_state.sound_played.obj == mock_npc, "Should play on NPC object")
    
    print("✓ Test 6: play_on_npc uses play_no_feedback for 3D NPC audio")
end

-- Test 7: play_on_npc falls back to 2D when NPC is nil
local function test_play_2d_when_npc_nil()
    reset_state()
    
    mock_engine._set("is_alive", false)
    mock_engine._set("get_player", { id = 0 })
    
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
                play_no_feedback = function(_, obj, mode, delay, pos, vol, freq)
                    test_state.sound_played = {
                        path = path,
                        used_play_no_feedback = true
                    }
                end,
                playing = function() return true end,
                stop = function() test_state.sound_stopped = true end,
                length = function() return 2.0 end
            }
        end
    })
    _G.sound_object = sound_object_mock
    
    local snd = tts_slot.play_on_npc(10, nil)
    
    assert(snd ~= nil, "Should return sound_object")
    assert(test_state.sound_played.mode == "s2d", "Should use 2D mode when NPC is nil")
    assert(not test_state.sound_played.used_play_no_feedback, "Should NOT use play_no_feedback for 2D")
    
    print("✓ Test 7: play_on_npc falls back to 2D when NPC is nil")
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

-- Run all tests
local function run_tests()
    print("Running TTS slot manager tests...")
    print()
    
    local tests = {
        test_allocation_sequence,
        test_cache_flush_at_interval,
        test_no_restart_before_interval,
        test_write_delegates_to_io_open,
        test_write_empty_data,
        test_play_3d_on_alive_npc,
        test_play_2d_when_npc_nil,
        test_wrap_at_200,
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

package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")
local luaunit = require('tests.utils.luaunit')

-- ── Mock dependencies before loading the script ─────────────────────────────

-- The speak key is MCM-configurable via config.speak_key(). Tests use a
-- symbolic constant so no test ever references an actual key name.
local CONFIGURED_SPEAK_KEY = "DIK_ENTER"

local mock_config = {}
function mock_config.speak_key()      return CONFIGURED_SPEAK_KEY end
function mock_config.is_mic_enabled() return true end
setmetatable(mock_config, { __index = function() return function() end end })

local recorder_calls = {}
local mock_recorder = {}
function mock_recorder.toggle(callback)
    table.insert(recorder_calls, { fn = "toggle", callback = callback })
end

local trigger_calls = {}
local mock_trigger = {}
function mock_trigger.talker_player_speaks(dialogue)
    table.insert(trigger_calls, { fn = "talker_player_speaks", dialogue = dialogue })
end
function mock_trigger.talker_player_whispers(dialogue)
    table.insert(trigger_calls, { fn = "talker_player_whispers", dialogue = dialogue })
end
setmetatable(mock_trigger, { __index = function() return function() end end })

package.loaded["interface.config"]   = mock_config
package.loaded["interface.recorder"] = mock_recorder
package.loaded["interface.trigger"]  = mock_trigger

-- talker_whisper_state is an engine global set up by test_bootstrap as {}.
talker_whisper_state = { is_whisper_active = function() return false end }

-- Override bootstrap's is_player_alive stub.
talker_game_queries.is_player_alive = function() return true end

-- Load the actual script under test.
package.path = package.path .. ';./gamedata/scripts/?.script'

-- Intercept RegisterScriptCallback to capture the key-press handler.
local captured_key_handler = nil
RegisterScriptCallback = function(event, fn)
    if event == "on_key_press" then captured_key_handler = fn end
end

require('talker_input_mic')
on_game_start()  -- triggers RegisterScriptCallback("on_key_press", ...)

-- ── Helpers ──────────────────────────────────────────────────────────────────

local function reset()
    recorder_calls = {}
    trigger_calls  = {}
    talker_game_queries.is_player_alive   = function() return true end
    talker_whisper_state.is_whisper_active = function() return false end
    mock_config.speak_key      = function() return CONFIGURED_SPEAK_KEY end
    mock_config.is_mic_enabled = function() return true end
end

local function press(key)
    captured_key_handler(key)
end

-- ── Tests ────────────────────────────────────────────
function testIsLoaded()
    luaunit.assertTrue(is_loaded())
end

function testConfiguredSpeakKeyStartsRecorder()
    reset()
    press(CONFIGURED_SPEAK_KEY)
    luaunit.assertEquals(#recorder_calls, 1)
    luaunit.assertEquals(recorder_calls[1].fn, "toggle")
end

function testWrongKeyIsNoop()
    reset()
    press("DIK_SPACE")
    luaunit.assertEquals(#recorder_calls, 0)
end

function testMicDisabledIsNoop()
    reset()
    mock_config.is_mic_enabled = function() return false end
    press(CONFIGURED_SPEAK_KEY)
    luaunit.assertEquals(#recorder_calls, 0)
end

function testDeadPlayerIsNoop()
    reset()
    talker_game_queries.is_player_alive = function() return false end
    press(CONFIGURED_SPEAK_KEY)
    luaunit.assertEquals(#recorder_calls, 0)
end

function testTranscriptionFiresPlayerSpeaks()
    reset()
    press(CONFIGURED_SPEAK_KEY)
    luaunit.assertEquals(#recorder_calls, 1)
    recorder_calls[1].callback("Hello Zone")
    luaunit.assertEquals(#trigger_calls, 1)
    luaunit.assertEquals(trigger_calls[1].fn, "talker_player_speaks")
    luaunit.assertEquals(trigger_calls[1].dialogue, "Hello Zone")
end

function testTranscriptionInWhisperModeFiresPlayerWhispers()
    reset()
    talker_whisper_state.is_whisper_active = function() return true end
    press(CONFIGURED_SPEAK_KEY)
    recorder_calls[1].callback("Quiet words")
    luaunit.assertEquals(#trigger_calls, 1)
    luaunit.assertEquals(trigger_calls[1].fn, "talker_player_whispers")
    luaunit.assertEquals(trigger_calls[1].dialogue, "Quiet words")
end

function testDifferentConfiguredKeyRespected()
    -- Changing the MCM speak key binding should work without any code changes.
    reset()
    mock_config.speak_key = function() return "DIK_F5" end
    press("DIK_F5")
    luaunit.assertEquals(#recorder_calls, 1)
    -- The previously-configured key no longer works.
    recorder_calls = {}
    press(CONFIGURED_SPEAK_KEY)
    luaunit.assertEquals(#recorder_calls, 0)
end

os.exit(luaunit.LuaUnit.run())

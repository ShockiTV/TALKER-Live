package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
local luaunit = require('tests.utils.luaunit')

-- ── Test: FFI graceful fallback when DLL is absent ──────────────────────────
--
-- In the test environment LuaJIT's ffi.load("talker_audio.dll") will fail
-- because the DLL isn't present. The module must still load and every
-- function must return a safe fallback value.

-- The FFI module requires LuaJIT's ffi; in plain Lua 5.1 tests we need a
-- minimal shim that lets the module load but makes ffi.load always fail.

local real_ffi_ok, real_ffi = pcall(require, "ffi")

if not real_ffi_ok then
    -- Running under plain Lua 5.1 — provide a minimal ffi shim
    local shim = {}
    function shim.cdef() end
    function shim.load()
        error("cannot open shared object: talker_audio.dll")
    end
    function shim.new(ctype, ...)
        return nil
    end
    function shim.string(ptr)
        return ""
    end
    package.preload["ffi"] = function() return shim end
end

-- Now require the module — it should handle the failed load gracefully
local ta = require("infra.mic.talker_audio_ffi")

-- ── Tests ────────────────────────────────────────────────────────────────────

function testDllNotAvailable()
    -- In test env, the DLL won't be present
    luaunit.assertFalse(ta.is_available())
end

function testOpenReturnsErrorWhenUnavailable()
    luaunit.assertEquals(ta.open(), -1)
end

function testCloseDoesNotCrashWhenUnavailable()
    -- Should be a safe no-op
    ta.close()
end

function testStartReturnsErrorWhenUnavailable()
    luaunit.assertEquals(ta.start(), -1)
end

function testStopReturnsErrorWhenUnavailable()
    luaunit.assertEquals(ta.stop(), -1)
end

function testIsCapturingFalseWhenUnavailable()
    luaunit.assertFalse(ta.is_capturing())
end

function testPollReturnsZeroWhenUnavailable()
    local n, buf = ta.poll()
    luaunit.assertEquals(n, 0)
    luaunit.assertNil(buf)
end

function testSetVadDoesNotCrashWhenUnavailable()
    ta.set_vad(500, 3000)
end

function testGetDeviceCountZeroWhenUnavailable()
    luaunit.assertEquals(ta.get_device_count(), 0)
end

function testGetDeviceNameNilWhenUnavailable()
    luaunit.assertNil(ta.get_device_name(0))
end

function testGetDefaultDeviceNegativeWhenUnavailable()
    luaunit.assertEquals(ta.get_default_device(), -1)
end

function testSetDeviceReturnsErrorWhenUnavailable()
    luaunit.assertEquals(ta.set_device(0), -1)
end

function testSetOpusBitrateDoesNotCrashWhenUnavailable()
    ta.set_opus_bitrate(16000)
end

function testSetOpusFrameMsDoesNotCrashWhenUnavailable()
    ta.set_opus_frame_ms(40)
end

function testSetOpusComplexityDoesNotCrashWhenUnavailable()
    ta.set_opus_complexity(3)
end

os.exit(luaunit.LuaUnit.run())

---@diagnostic disable: lowercase-global
-- test_bootstrap.lua — Standard test setup for all bin/lua/ tests.
-- Require this as the first line (after package.path) in every Lua test file:
--
--   package.path = package.path .. ';./bin/lua/?.lua'
--   require("tests.test_bootstrap")
--
-- What this does:
--   1. Sets package.path to cover bin/lua/ and tests/
--   2. Injects mock_engine into package.loaded["interface.engine"] BEFORE any
--      bin/lua/ module is required, so the facade is already mocked when modules load
--   3. Sets engine globals to safe no-op stubs so legacy code that checks them
--      before migrating also works
--   4. Seeds math.random to ensure deterministic backstory/personality assignment
--
-- Idempotent: Lua's require() caches this module, so multiple requires are safe.

-- 0. Seed RNG for deterministic tests (backstory/personality use math.random)
math.randomseed(42)

-- 1. Ensure both bin/lua/ and the project root (for tests.*) are on the path
package.path = package.path
    .. ";./bin/lua/?.lua"
    .. ";./bin/lua/*/?.lua"
    .. ";./?.lua"

-- 2. Wire mock_engine into package.loaded BEFORE any module that requires
--    "interface.engine" is loaded.  This works because require() checks
--    package.loaded first, before searching the filesystem.
local mock_engine = require("tests.mocks.mock_engine")
package.loaded["interface.engine"] = mock_engine

-- 3. Set engine globals to safe stubs so any module that still checks
--    the raw globals (e.g. `if talker_game_queries then ...`) doesn't error.
talker_mcm = talker_mcm or {
    get = function(key)
        -- delegate to mock_engine so values are consistent
        return mock_engine.get_mcm_value(key)
    end
}
talker_game_queries  = talker_game_queries  or {}
talker_game_commands = talker_game_commands or {}
talker_game_async    = talker_game_async    or {}
talker_game_files    = talker_game_files    or { get_base_path = function() return "" end }

-- Safe no-op for printf (game engine provides this; tests use standard print)
printf = printf or function(fmt, ...)
    print(string.format(fmt, ...))
end

-- Safe no-op stubs for engine callbacks / time events
CreateTimeEvent       = CreateTimeEvent       or function() end
ResetTimeEvent        = ResetTimeEvent        or function() end
RegisterScriptCallback = RegisterScriptCallback or function() end

-- Safe stub for ini_file (legacy; should no longer be called after migration)
ini_file = ini_file or function() ---@diagnostic disable-line: unused-vararg
    return {
        section_exist = function() return false end,
        r_string_ex   = function() return nil   end,
    }
end

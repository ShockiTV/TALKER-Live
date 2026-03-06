-- unique_ts.lua — Global monotonic timestamp generator.
-- Returns collision-free millisecond timestamps suitable as identity keys.
-- If engine.get_game_time_ms() returns a value <= the last assigned timestamp,
-- bumps to last + 1. This replaces per-character seq counters.
package.path = package.path .. ";./bin/lua/?.lua;"
local engine = require("interface.engine")

local M = {}

-- Last assigned timestamp (module-level state)
local _last_ts = 0

--- Return a globally unique, monotonically increasing timestamp.
-- Uses engine.get_game_time_ms() as the base, bumping on collision.
-- @return number  unique timestamp (integer)
function M.unique_ts()
	local now = engine.get_game_time_ms()
	if now <= _last_ts then
		_last_ts = _last_ts + 1
	else
		_last_ts = now
	end
	return _last_ts
end

--- Reset internal state (called on game load / new game).
function M.reset()
	_last_ts = 0
end

--- Get current last_ts value (for testing/debugging).
-- @return number
function M.get_last_ts()
	return _last_ts
end

return M

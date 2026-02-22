-- logger.lua
local M = {}
package.path = package.path .. ";./bin/lua/?.lua;"

local inspect = require("framework.inspect")
local file_io = require("infra.file_io")
local engine = require("interface.engine")

-- print functions — prefer game printf when available
local function get_print()
    return printf or print
end

-- Logging levels
local levels = {
	spam = 0,
	debug = 1,
	info = 2,
	http = 3,
	warn = 4,
	error = 5,
}

-- Default write level
M.logLevel = levels.debug

-- depth for indentation
local depth = 0
local logFile = "logs/talker_debug.log"

function M.setLogFile(fileName)
	logFile = fileName
end

-- Generic write function with indentation based on depth
local function write_to_log(level, message, ...)
	if levels[level] < M.logLevel then
		return
	end

	local mode = tonumber(engine.get_mcm_value("debug_logging") or "0")

	local is_essential = levels[level] >= levels.warn
	local should_print = is_essential or (mode == 1 or mode == 3)
	local should_log = is_essential or (mode == 2 or mode == 3)

	if not (should_print or should_log) then
		return
	end

	local indent = string.rep("  ", depth)
	local args = { ... }
	local inspected_args = {}
	for i = 1, select("#", ...) do
		inspected_args[i] = inspect(args[i])
	end
	local formatted_message = string.format(message, unpack(inspected_args))
	local str = string.format("%s[%s]: %s", indent, level, formatted_message)

	if should_print then
		get_print()(str)
	end

	if should_log then
		file_io.add_line(logFile, str)
	end
end

function M.clean_log_files()
	return file_io.override(logFile, "")
end

local function write(level, message, ...)
	local result, err = pcall(write_to_log, level, message, ...)
	if not result then
		get_print()(
			string.format("Error in logging at level '%s' with message '%s': %s", level, message, tostring(err))
		)
	end
end

-- Convenience functions for different write levels
function M.debug(message, ...)
	write("debug", message, ...)
end

function M.info(message, ...)
	write("info", message, ...)
end

function M.warn(message, ...)
	write("warn", message, ...)
end

function M.spam(message, ...)
	write("spam", message, ...)
end

function M.error(message, ...)
	write("error", message, ...)
	-- Guard: only display to player if game_adapter is available (not in test env)
	local ok, game_adapter = pcall(require, "infra.game_adapter")
	if ok and game_adapter and game_adapter.display_error_to_player then
		local args = { ... }
		local inspected = {}
		for i = 1, select("#", ...) do inspected[i] = tostring(args[i]) end
		local formatted = #inspected > 0 and string.format(message, unpack(inspected)) or message
		pcall(game_adapter.display_error_to_player, "ERROR: " .. formatted)
	end
end

function M.http(message, ...)
	write("http", message, ...)
end

-- Start and end operations with depth tracking
function M.start(message, level)
	write(level or "info", "START: " .. message)
	depth = depth + 1
end

function M.close(message, level)
	depth = depth - 1
	write(level or "info", "END  : " .. message)
end

-- Set the global write level
function M.setLogLevel(level)
	if levels[level] then
		M.logLevel = levels[level]
	else
		M.error("Invalid log level: " .. tostring(level))
	end
end

return M

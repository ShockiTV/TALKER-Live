-- logger.lua
local M = {}
package.path = package.path .. ";./bin/lua/?.lua;"

local inspect = require("framework.inspect")
local file_io = require("infra.file_io")

-- print functions
local print_fun = printf or print -- depends on game state

-- Logging levels
local levels = {
    spam = 0,
    debug = 1,
    info = 2,
    warn = 3,
    error = 4,
    http = 5
}

-- Default write level
M.logLevel = levels.debug

-- Enable or disable logging to file
M.LOG_TO_FILE = true

-- Store depth for indentation
local depth = 0

local logFile = "logs/talker.log"

function M.setLogFile(fileName)
    logFile = fileName
end

-- Generic write function with indentation based on depth
local function write_to_log(level, message, ...)
    if levels[level] < M.logLevel then return end

    local indent = string.rep("  ", depth)
    -- inspect each in ...
    local inspected_args = {}
    for i, v in ipairs({...}) do
        inspected_args[i] = inspect(v)
    end
    local formatted_message = string.format(message, unpack(inspected_args))
    local str = string.format("%s[%s]: %s", indent, level, formatted_message)

    print_fun(str)

    if M.LOG_TO_FILE and levels[level] == levels.http then
        file_io.add_line("logs/talker_http.log", str)
    elseif M.LOG_TO_FILE then
        file_io.add_line(logFile, str)
    end
end

function M.clean_log_files()
    file_io.override(logFile, "")
    file_io.override("logs/talker_http.log", "")
end

local function write(level, message, ...)
    local result, error = pcall(write_to_log, level, message, ...)
    if not result then
        print_fun(string.format("Error in logging at level '%s' with message '%s': %s", level, message, tostring(error)))
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
    local game_adapter = require('infra.game_adapter')
    game_adapter.display_error_to_player('ERROR: ' .. message)
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

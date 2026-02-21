package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

-- Override debug_logging to mode 3 (print+log) so we can capture printed output
local mock_engine = require("tests.mocks.mock_engine")
mock_engine._set("debug_logging", 3)

local luaunit = require('tests.utils.luaunit')
local file_io = require('infra.file_io')

-- Mock the file_io.write function to avoid actual file operations during tests
---@diagnostic disable-next-line: duplicate-set-field
file_io.write = function(filename, content)
    print(string.format("Mock write to %s: %s", filename, content))
end

-- Mock the print function to capture printed output
local printed_output = {}
local function mock_print(...)
    table.insert(printed_output, table.concat({...}, " "))
end
printf = mock_print

-- Re-require logger after setting up printf mock
package.loaded["framework.logger"] = nil
local logger = require('framework.logger')


function setUp()
    printed_output = {}
    logger.setLogLevel("info")
end

function testSetLogLevel()
    logger.setLogLevel("debug")
    luaunit.assertEquals(logger.logLevel, 1)

    logger.setLogLevel("info")
    luaunit.assertEquals(logger.logLevel, 2)
end

function testLoggingAtDifferentLevels()
    printed_output = {}
    logger.setLogLevel("debug")

    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warn("This is a warning message")
    logger.error("This is an error message")
    logger.http("This is an HTTP message")

    luaunit.assertStrContains(printed_output[1], "debug")
    luaunit.assertStrContains(printed_output[2], "info")
    luaunit.assertStrContains(printed_output[3], "warn")
    luaunit.assertStrContains(printed_output[4], "error")
    luaunit.assertStrContains(printed_output[5], "http")
end

function testStartAndCloseFunctions()
    logger.start("Test operation")
    luaunit.assertStrContains(printed_output[#printed_output], "START: Test operation")

    logger.close("Test operation")
    luaunit.assertStrContains(printed_output[#printed_output], "END  : Test operation")
end

function testInvalidLogLevel()
    logger.setLogLevel("invalid")
    luaunit.assertStrContains(printed_output[#printed_output], "Invalid log level")
end

function testLogLevelFiltering()
    printed_output = {}
    logger.setLogLevel("warn")

    logger.debug("This debug message should not be logged")
    logger.info("This info message should not be logged")
    logger.warn("This warning message should be logged")
    logger.error("This error message should be logged")

    luaunit.assertEquals(#printed_output, 2)
    luaunit.assertStrContains(printed_output[1], "warn")
    luaunit.assertStrContains(printed_output[2], "error")
end

function testLogToFile()
    logger.setLogLevel("info")
    logger.LOG_TO_FILE = true

    logger.info("This is an info message to file")
    luaunit.assertStrContains(printed_output[#printed_output], "info")
    luaunit.assertStrContains(printed_output[#printed_output], "This is an info message to file")
end

os.exit(luaunit.LuaUnit.run())

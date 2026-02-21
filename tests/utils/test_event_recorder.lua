local test_data_path = "tests/utils/test_data/"

package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local event_recorder = require "framework.event_recorder"
local luaunit = require('tests.utils.luaunit')
local mock_situation = require("tests.mocks.mock_situation")

-- make test_data if not available (cross-platform)
os.execute('mkdir "' .. test_data_path:gsub("/", "\\") .. '" 2>nul || mkdir -p ' .. test_data_path .. ' 2>/dev/null')
function testSaveAndLoadTable()
    local test_file = "tests/utils/test_data/" .. "testSaveAndLoadTable.txt"
    local my_table = {a = 1, b = "hello", c = {1, 2, 3}}

    event_recorder.save_to_file(test_file, my_table)
    local loaded_table = event_recorder.load_from_file(test_file)
    os.remove(test_file)

    luaunit.assertNotNil(loaded_table)
    luaunit.assertEquals(loaded_table, my_table)
end

function testSaveAndLoadEmptyTable()
    local test_file = test_data_path .. "empty_data.txt"
    local empty_table = {}

    event_recorder.save_to_file(test_file, empty_table)
    local loaded_empty_table = event_recorder.load_from_file(test_file)
    os.remove(test_file)

    luaunit.assertNotNil(loaded_empty_table)
    luaunit.assertEquals(loaded_empty_table, empty_table)
end

function testSaveAndLoadNestedTable()
    local test_file = test_data_path .. "nested_data.txt"
    local nested_table = {a = {1, 2, 3}, b = {4, 5, 6}, c = {7, 8, 9}}

    event_recorder.save_to_file(test_file, nested_table)
    local loaded_nested_table = event_recorder.load_from_file(test_file)
    os.remove(test_file)

    luaunit.assertNotNil(loaded_nested_table)
    luaunit.assertEquals(loaded_nested_table, nested_table)
end

function testSaveAndLoadEvent()
    local test_file = test_data_path .. "event.txt"
    local event = mock_situation[1]

    event_recorder.save_to_file(test_file, event)
    local loaded_event = event_recorder.load_from_file(test_file)
    os.remove(test_file)

    luaunit.assertNotNil(loaded_event)
    luaunit.assertEquals(loaded_event, event)
end

luaunit.run()

package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")
local file_io = require("infra.file_io")
local luaunit = require('tests.utils.luaunit')

function testReadWrite()
    local test_file = "test_file.txt"
    local test_content = "Hello, World!"

    -- Test write
    file_io.write(test_file, test_content)
    local read_content = file_io.read(test_file)
    luaunit.assertEquals(read_content, test_content)

    -- Clean up
    file_io.delete(test_file)
end

function testOverride()
    local test_file = "test_override.txt"
    local initial_content = "Initial Content"
    local new_content = "New Content"

    -- Test override
    file_io.write(test_file, initial_content)
    file_io.override(test_file, new_content)
    local read_content = file_io.read(test_file)
    luaunit.assertEquals(read_content, new_content)

    -- Clean up
    file_io.delete(test_file)
end

function testDelete()
    local test_file = "test_delete.txt"
    local test_content = "To be deleted"

    -- Test delete
    file_io.write(test_file, test_content)
    file_io.delete(test_file)
    local read_content = file_io.read(test_file)
    luaunit.assertNil(read_content)

    -- Clean up (in case of failure)
    if file_io.read(test_file) then
        file_io.delete(test_file)
    end
end

function testTempFile()
    local test_temp_file = "test_temp_file.txt"
    local test_content = "Temporary Content"

    -- Test override_temp and read_temp
    file_io.override_temp(test_temp_file, test_content)
    local read_content = file_io.read_temp(test_temp_file)
    luaunit.assertEquals(read_content, test_content)

    -- Clean up
    file_io.delete_temp(test_temp_file)
end

os.exit(luaunit.LuaUnit.run())

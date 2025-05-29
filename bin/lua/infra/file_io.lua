-- file_io.lua
local file_io = {}

-- legacy flag workaround
local function get_base_path()
    local game_files = talker_game_files or require('tests.mocks.mock_game_adapter')
    return game_files.get_base_path()
end

-- always open in binary mode so UTF-8 bytes pass through untouched
local function open_file(path, mode)
    return io.open(path, mode .. "b")      -- "rb", "wb", "ab"
end

function file_io.read(file_name, not_game)
    local full_path = not_game and file_name or get_base_path() .. file_name
    local file = open_file(full_path, "r")
    if not file then return nil end
    local contents = file:read("*a")
    file:close()
    return contents
end

function file_io.write(file_name, contents, not_game)
    local full_path = not_game and file_name or get_base_path() .. file_name
    contents = contents or ""
    local file, err = open_file(full_path, "a")
    if not file then
        print("Error opening file:", err)
        return false
    end
    local ok, werr = file:write(contents)
    if not ok then
        print("Error writing to file:", werr)
        return false
    end
    file:close()
    return true
end

function file_io.add_line(file_name, contents)
    return file_io.write(file_name, (contents or "") .. "\n")
end

function file_io.override(file_name, contents, not_game)
    local full_path = not_game and file_name or get_base_path() .. file_name
    local file, err = open_file(full_path, "w")
    if not file then
        print("Error opening file:", err)
        return false
    end
    local ok, werr = file:write(contents or "")
    if not ok then
        print("Error writing to file:", werr)
        return false
    end
    file:close()
    return true
end

function file_io.delete(file_name, not_game)
    local full_path = not_game and file_name or get_base_path() .. file_name
    os.remove(full_path)
    return true
end

-- temporary-file helpers (UTF-8 safe through file_io.*)
local function mic_path(filename)
    local tmp = os.getenv("TMPDIR") or os.getenv("TMP") or os.getenv("TEMP")
    assert(tmp, "Temporary directory not found")
    return tmp .. "/" .. filename
end

function file_io.read_temp(filename)
    local p = mic_path(filename)
    local c = file_io.read(p, true)
    assert(c, "Temporary file not found: " .. p)
    return c
end

function file_io.override_temp(filename, contents)
    local p = mic_path(filename)
    assert(file_io.override(p, contents, true), "Failed to write to temporary file: " .. p)
    return true
end

return file_io

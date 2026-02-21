package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
local file_io = require("infra.file_io")

-- Function to event_recorder.serialize a Lua table (object) into a string
local event_recorder = {}
function event_recorder.serialize(obj)
    local lua_type = type(obj)
    if lua_type == "number" or lua_type == "boolean" then
        return tostring(obj)
    elseif lua_type == "string" then
        return string.format("%q", obj)
    elseif lua_type == "table" then
        local result = "{"
        for k, v in pairs(obj) do
            result = result .. "[" .. event_recorder.serialize(k) .. "]=" .. event_recorder.serialize(v) .. ","
        end
        return result .. "}"
    else
        error("Cannot event_recorder.serialize type: " .. lua_type)
    end
end

-- Function to save a event_recorder.serialized object into a file
function event_recorder.save_to_file(filename, obj)
    local serialized_data = event_recorder.serialize(obj)
    file_io.override(filename, serialized_data)
end

-- Function to load a Lua object from a file
function event_recorder.load_from_file(filename)
    local data = file_io.read(filename)
    -- Use loadstring (Lua 5.1) or load (Lua 5.2+) to convert string back to Lua table
    local loader = loadstring or load
    local func = loader("return " .. data)
    if func then
        return func()
    else
        print("Error loading data from file")
        return nil
    end
end

return event_recorder
-- framework/utils.lua
-- Common utility functions with zero dependencies on engine globals, domain modules, or infrastructure.
-- Extracted from gamedata/scripts/ (must_exist, try, join_tables, Set from talker_game_queries;
-- shuffle from talker_trigger_idle_conversation; safely from talker_game_commands;
-- array_iter from talker_zmq_query_handlers).
local M = {}

--- Raises an error if obj is nil.
-- @param obj     Any value to check
-- @param func_name  Name of the calling function (included in the error message)
function M.must_exist(obj, func_name)
    if not obj then
        error(func_name .. ": nil object")
    end
end

--- Wraps a function call in pcall, returning nil on error (errors are swallowed).
-- @param func  Function to call
-- @param ...   Arguments forwarded to func
-- @return      Return value of func, or nil on error
function M.try(func, ...)
    local status, result = pcall(func, ...)
    if not status then
        return nil
    end
    return result
end

--- Returns a new array containing all elements from t1 followed by all elements from t2.
-- Either argument may be nil (treated as an empty array).
-- @param t1  First array (or nil)
-- @param t2  Second array (or nil)
-- @return    New table with elements of t1 then t2
function M.join_tables(t1, t2)
    local result = {}
    if t1 then
        for _, v in ipairs(t1) do
            result[#result + 1] = v
        end
    end
    if t2 then
        for _, v in ipairs(t2) do
            result[#result + 1] = v
        end
    end
    return result
end

--- Converts an array to a set table (value → true) for O(1) membership tests.
-- @param t  Array of values
-- @return   Table where each value maps to true
function M.Set(t)
    local s = {}
    for _, v in pairs(t) do
        s[v] = true
    end
    return s
end

--- Performs an in-place Fisher-Yates shuffle of an array.
-- @param tbl  Array to shuffle (modified in place)
-- @return     The same table (shuffled)
function M.shuffle(tbl)
    for i = #tbl, 2, -1 do
        local j = math.random(i)
        tbl[i], tbl[j] = tbl[j], tbl[i]
    end
    return tbl
end

--- Returns a new function that wraps func in pcall.
-- On error, prints the error message and returns the error string.
-- On success, returns the function's return value.
-- @param func  Function to wrap
-- @param name  Human-readable name for error messages
-- @return      Wrapped function
function M.safely(func, name)
    return function(...)
        local ok, result = pcall(func, ...)
        if not ok then
            print(string.format("[safely] Error in %s: %s", tostring(name), tostring(result)))
        end
        return result
    end
end

--- Returns a stateful iterator closure over an array.
-- Each call to the returned function yields the next element, or nil when exhausted.
-- @param arr  Array to iterate
-- @return     Iterator function
function M.array_iter(arr)
    local i = 0
    return function()
        i = i + 1
        return arr[i]
    end
end

return M

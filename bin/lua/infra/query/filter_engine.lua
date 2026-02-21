-- filter_engine.lua — Generic recursive filter evaluator for Lua tables
-- MongoDB-style filter language: comparison, set, string, existence, array, logical operators
-- Plus sort, limit, and field projection pipeline
-- Pure Lua 5.1 — no game dependencies
package.path = package.path .. ";./bin/lua/?.lua;"

local M = {}

--------------------------------------------------------------------------------
-- Dotted Field Path Resolution
--------------------------------------------------------------------------------

--- Resolve a dotted field path (e.g., "context.victim.faction") against a table.
-- Numeric segments are treated as 0-based wire indices mapped to 1-based Lua indices.
-- @param doc table  The document to resolve against
-- @param path string  Dotted field path
-- @return any  The resolved value, or nil if path does not exist
local function resolve_path(doc, path)
    if doc == nil then return nil end
    if not path or path == "" then return doc end

    local current = doc
    for segment in string.gmatch(path, "[^%.]+") do
        if current == nil or type(current) ~= "table" then
            return nil
        end
        -- Try numeric index first (0-based wire → 1-based Lua)
        local num = tonumber(segment)
        if num ~= nil then
            current = current[num + 1]
        else
            current = current[segment]
        end
    end
    return current
end

M.resolve_path = resolve_path

--------------------------------------------------------------------------------
-- Filter Evaluation (recursive)
--------------------------------------------------------------------------------

--- Check if a value is a filter operator table (has at least one $-prefixed key).
local function is_operator_table(v)
    if type(v) ~= "table" then return false end
    for k, _ in pairs(v) do
        if type(k) == "string" and string.sub(k, 1, 1) == "$" then
            return true
        end
    end
    return false
end

--- Evaluate a single operator expression against a field value.
-- @param field_value any  The resolved field value from the document
-- @param op_table table  The operator expression (e.g., {["$gt"] = 50000})
-- @return boolean
local function evaluate_operators(field_value, op_table)
    for op, operand in pairs(op_table) do
        if op == "$eq" then
            if field_value ~= operand then return false end

        elseif op == "$ne" then
            if field_value == operand then return false end

        elseif op == "$gt" then
            if field_value == nil or field_value <= operand then return false end

        elseif op == "$gte" then
            if field_value == nil or field_value < operand then return false end

        elseif op == "$lt" then
            if field_value == nil or field_value >= operand then return false end

        elseif op == "$lte" then
            if field_value == nil or field_value > operand then return false end

        elseif op == "$in" then
            if field_value == nil then return false end
            local found = false
            for _, v in ipairs(operand) do
                if field_value == v then found = true; break end
            end
            if not found then return false end

        elseif op == "$nin" then
            if field_value ~= nil then
                for _, v in ipairs(operand) do
                    if field_value == v then return false end
                end
            end

        elseif op == "$regex" then
            if field_value == nil or type(field_value) ~= "string" then return false end
            local pattern = operand
            local val = field_value
            -- Check for case-insensitive flag
            local flags = op_table["$regex_flags"]
            if flags and string.find(flags, "i") then
                pattern = string.lower(pattern)
                val = string.lower(val)
            end
            if not string.find(val, pattern) then return false end

        elseif op == "$regex_flags" then
            -- Handled by $regex, skip
        elseif op == "$exists" then
            if operand then
                -- $exists: true — field must be non-nil
                if field_value == nil then return false end
            else
                -- $exists: false — field must be nil
                if field_value ~= nil then return false end
            end

        elseif op == "$size" then
            if type(field_value) ~= "table" then return false end
            if #field_value ~= operand then return false end

        elseif op == "$all" then
            if type(field_value) ~= "table" then return false end
            for _, required in ipairs(operand) do
                local found = false
                for _, v in ipairs(field_value) do
                    if v == required then found = true; break end
                end
                if not found then return false end
            end

        elseif op == "$elemMatch" then
            if type(field_value) ~= "table" then return false end
            local any_match = false
            for _, elem in ipairs(field_value) do
                if M.evaluate_filter(elem, operand) then
                    any_match = true
                    break
                end
            end
            if not any_match then return false end

        elseif op == "$not" then
            -- $not negates a sub-expression
            if is_operator_table(operand) then
                if evaluate_operators(field_value, operand) then return false end
            else
                -- Bare value in $not means $not: {$eq: value}
                if field_value == operand then return false end
            end
        end
    end
    return true
end

--- Evaluate a filter document against a document.
-- Top-level keys are implicitly ANDed.
-- Supports $and, $or, $not at top level as logical operators.
-- @param doc table  The document to test
-- @param filter table  The filter document
-- @return boolean  true if document matches the filter
function M.evaluate_filter(doc, filter)
    if filter == nil or next(filter) == nil then
        return true -- Empty/nil filter matches everything
    end

    for key, condition in pairs(filter) do
        -- Logical operators at top level
        if key == "$and" then
            for _, sub_filter in ipairs(condition) do
                if not M.evaluate_filter(doc, sub_filter) then
                    return false
                end
            end

        elseif key == "$or" then
            local any_match = false
            for _, sub_filter in ipairs(condition) do
                if M.evaluate_filter(doc, sub_filter) then
                    any_match = true
                    break
                end
            end
            if not any_match then return false end

        elseif key == "$not" then
            -- Top-level $not: negate the sub-filter
            if M.evaluate_filter(doc, condition) then
                return false
            end

        else
            -- Field-level condition
            local field_value = resolve_path(doc, key)

            if is_operator_table(condition) then
                -- Operator expression: {"field": {"$gt": 5}}
                if not evaluate_operators(field_value, condition) then
                    return false
                end
            else
                -- Implicit $eq: {"field": "value"}
                if field_value ~= condition then
                    return false
                end
            end
        end
    end
    return true
end

--------------------------------------------------------------------------------
-- Pipeline: Sort helpers
--------------------------------------------------------------------------------

--- Resolve the sort key from a sort spec.
-- @param sort table  Sort specification, e.g., {"game_time_ms": -1}
-- @return string, number  field path and direction (1 or -1)
local function parse_sort_spec(sort)
    if not sort then return nil, nil end
    for field_path, direction in pairs(sort) do
        return field_path, direction
    end
    return nil, nil
end

--- Binary search for insertion position in a sorted buffer.
-- Buffer entries are {sort_val = ..., doc = ...}.
-- @param buffer table  Sorted array of entries
-- @param sort_val any  Value to insert
-- @param direction number  1 for ascending, -1 for descending
-- @return number  Insertion index (1-based)
local function binary_insert_pos(buffer, sort_val, direction)
    local low, high = 1, #buffer
    while low <= high do
        local mid = math.floor((low + high) / 2)
        local mid_val = buffer[mid].sort_val
        local compare
        if direction == 1 then
            -- Ascending: smaller values first
            compare = (sort_val < mid_val)
        else
            -- Descending: larger values first
            compare = (sort_val > mid_val)
        end
        if compare then
            high = mid - 1
        else
            low = mid + 1
        end
    end
    return low
end

--------------------------------------------------------------------------------
-- Pipeline Strategies
--------------------------------------------------------------------------------

--- Fused top-N scan: sort + limit present.
-- Single pass maintaining a bounded sorted buffer of at most `limit` elements.
-- @param source_iter function  Iterator returning next document or nil
-- @param filter table|nil  Filter document
-- @param sort_field string  Field path to sort by
-- @param sort_dir number  1 ascending, -1 descending
-- @param limit number  Maximum results
-- @return table  Array of documents in sorted order
local function fused_top_n(source_iter, filter, sort_field, sort_dir, limit)
    local buffer = {} -- Array of {sort_val, doc}

    while true do
        local doc = source_iter()
        if doc == nil then break end

        if M.evaluate_filter(doc, filter) then
            local sort_val = resolve_path(doc, sort_field)

            if #buffer < limit then
                -- Buffer not full yet, insert at sorted position
                local pos = binary_insert_pos(buffer, sort_val, sort_dir)
                table.insert(buffer, pos, { sort_val = sort_val, doc = doc })
            else
                -- Buffer full — check if this doc beats the worst (last) element
                local worst = buffer[#buffer]
                local dominated
                if sort_dir == 1 then
                    dominated = (sort_val < worst.sort_val)
                else
                    dominated = (sort_val > worst.sort_val)
                end
                if dominated then
                    -- Evict worst, insert at sorted position
                    buffer[#buffer] = nil
                    local pos = binary_insert_pos(buffer, sort_val, sort_dir)
                    table.insert(buffer, pos, { sort_val = sort_val, doc = doc })
                end
            end
        end
    end

    -- Extract documents from buffer
    local result = {}
    for _, entry in ipairs(buffer) do
        result[#result + 1] = entry.doc
    end
    return result
end

--- Early-termination scan: limit only (no sort).
-- Stop scanning after `limit` documents pass the filter.
-- @param source_iter function  Iterator
-- @param filter table|nil  Filter
-- @param limit number  Maximum results
-- @return table  Array of documents
local function early_termination(source_iter, filter, limit)
    local result = {}
    local count = 0

    while count < limit do
        local doc = source_iter()
        if doc == nil then break end

        if M.evaluate_filter(doc, filter) then
            result[#result + 1] = doc
            count = count + 1
        end
    end
    return result
end

--- Sort-all strategy: sort only (no limit).
-- Collect all matching docs, then sort.
-- @param source_iter function  Iterator
-- @param filter table|nil  Filter
-- @param sort_field string  Field path
-- @param sort_dir number  1 or -1
-- @return table  Sorted array of documents
local function sort_all(source_iter, filter, sort_field, sort_dir)
    local matches = {}

    while true do
        local doc = source_iter()
        if doc == nil then break end

        if M.evaluate_filter(doc, filter) then
            matches[#matches + 1] = doc
        end
    end

    table.sort(matches, function(a, b)
        local va = resolve_path(a, sort_field)
        local vb = resolve_path(b, sort_field)
        if va == nil and vb == nil then return false end
        if va == nil then return sort_dir == 1 end -- nil sorts first in ascending
        if vb == nil then return sort_dir ~= 1 end
        if sort_dir == 1 then
            return va < vb
        else
            return va > vb
        end
    end)

    return matches
end

--- Collect-all strategy: filter only (no sort, no limit).
-- @param source_iter function  Iterator
-- @param filter table|nil  Filter
-- @return table  Array of matching documents
local function collect_all(source_iter, filter)
    local result = {}

    while true do
        local doc = source_iter()
        if doc == nil then break end

        if M.evaluate_filter(doc, filter) then
            result[#result + 1] = doc
        end
    end
    return result
end

--------------------------------------------------------------------------------
-- Pipeline Orchestrator
--------------------------------------------------------------------------------

--- Execute a query pipeline on a source iterator.
-- Selects strategy based on which stages are present:
-- sort + limit → fused top-N | limit only → early termination
-- sort only → sort all | filter only → collect all
-- @param source_iter function  Iterator function returning next doc or nil
-- @param filter table|nil  Filter document
-- @param sort table|nil  Sort spec, e.g., {"game_time_ms": -1}
-- @param limit number|nil  Maximum results
-- @return table  Array of document references
function M.execute_pipeline(source_iter, filter, sort, limit)
    local sort_field, sort_dir = parse_sort_spec(sort)

    if sort_field and limit then
        return fused_top_n(source_iter, filter, sort_field, sort_dir, limit)
    elseif limit then
        return early_termination(source_iter, filter, limit)
    elseif sort_field then
        return sort_all(source_iter, filter, sort_field, sort_dir)
    else
        return collect_all(source_iter, filter)
    end
end

--------------------------------------------------------------------------------
-- Field Projection
--------------------------------------------------------------------------------

--- Apply field projection to a document.
-- Extracts only the specified dotted field paths into a new nested structure.
-- When fields is nil or empty, returns the document unchanged.
-- @param doc table  Source document
-- @param fields table|nil  Array of dotted field path strings
-- @return table  Projected document (or original if no fields specified)
function M.apply_projection(doc, fields)
    if not fields or #fields == 0 then
        return doc
    end

    local result = {}
    for _, field_path in ipairs(fields) do
        local value = resolve_path(doc, field_path)
        if value ~= nil then
            -- Build nested structure from dotted path
            local segments = {}
            for seg in string.gmatch(field_path, "[^%.]+") do
                segments[#segments + 1] = seg
            end

            local target = result
            for i = 1, #segments - 1 do
                local seg = segments[i]
                local num = tonumber(seg)
                local key = num and (num + 1) or seg
                if target[key] == nil then
                    target[key] = {}
                end
                target = target[key]
            end

            -- Set the leaf value
            local last_seg = segments[#segments]
            local num = tonumber(last_seg)
            local key = num and (num + 1) or last_seg
            target[key] = value
        end
    end
    return result
end

--------------------------------------------------------------------------------
-- $ref Resolver
--------------------------------------------------------------------------------

--- Recursively walk a table replacing "$ref:..." strings with resolved values.
-- @param tbl table  The table to resolve (modified in-place)
-- @param results_map table  Map of query_id to {ok = bool, data = ...}
-- @return table  The resolved table (same reference)
-- @return string|nil  Error message if a $ref could not be resolved
function M.resolve_refs(tbl, results_map)
    if type(tbl) ~= "table" then
        -- Check if it's a $ref string at the value level
        if type(tbl) == "string" and string.sub(tbl, 1, 5) == "$ref:" then
            local ref_str = string.sub(tbl, 6) -- strip "$ref:"
            local dot_pos = string.find(ref_str, "%.")
            if not dot_pos then
                return nil, "$ref: invalid format '" .. tbl .. "' (expected $ref:id.path)"
            end
            local query_id = string.sub(ref_str, 1, dot_pos - 1)
            local path = string.sub(ref_str, dot_pos + 1)
            
            local target = results_map[query_id]
            if target == nil then
                return nil, "$ref: '" .. query_id .. "' not yet resolved"
            end
            if target.ok == false then
                return nil, "$ref: '" .. query_id .. "' resolved to error"
            end
            
            local resolved = resolve_path(target.data, path)
            return resolved, nil
        end
        return tbl, nil
    end

    for k, v in pairs(tbl) do
        if type(v) == "string" and string.sub(v, 1, 5) == "$ref:" then
            local resolved, err = M.resolve_refs(v, results_map)
            if err then return tbl, err end
            tbl[k] = resolved
        elseif type(v) == "table" then
            local _, err = M.resolve_refs(v, results_map)
            if err then return tbl, err end
        end
    end
    return tbl, nil
end

return M

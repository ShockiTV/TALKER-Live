-- framework/checksum.lua
-- Deterministic 32-bit FNV-1a checksum utilities for memory entities.
-- Uses LuaJIT bit library when available, with pure-Lua fallback.

local M = {}

local MOD32 = 4294967296
local FNV_OFFSET_BASIS = 2166136261
local FNV_PRIME = 16777619

local _bit_override = nil
local _ok_bit, _bit = pcall(require, "bit")
if not _ok_bit then
    _bit = nil
end

local function active_bit()
    if _bit_override ~= nil then
        return _bit_override
    end
    return _bit
end

-- Test hook to force fallback/bit paths deterministically.
function M._set_bit_override(bit_lib)
    _bit_override = bit_lib
end

local function xor_fallback(a, b)
    local x = a % MOD32
    local y = b % MOD32
    local result = 0
    local place = 1

    for _ = 1, 32 do
        local xb = x % 2
        local yb = y % 2
        if xb ~= yb then
            result = result + place
        end
        x = (x - xb) / 2
        y = (y - yb) / 2
        place = place * 2
    end

    return result
end

local function bxor32(a, b)
    local bit_lib = active_bit()
    if bit_lib and bit_lib.bxor then
        local x = bit_lib.bxor(a, b)
        if x < 0 then
            return x + MOD32
        end
        return x % MOD32
    end
    return xor_fallback(a, b)
end

-- Exact modulo-2^32 multiply using repeated doubling.
-- Avoids precision issues from large float multiplications in Lua 5.1.
local function mul_mod32(a, b)
    local x = a % MOD32
    local y = b % MOD32
    local result = 0

    while y > 0 do
        if (y % 2) == 1 then
            result = (result + x) % MOD32
        end
        x = (x * 2) % MOD32
        y = math.floor(y / 2)
    end

    return result
end

local function escape_string(value)
    local s = tostring(value)
    s = s:gsub("\\", "\\\\")
    s = s:gsub('"', '\\"')
    s = s:gsub("\n", "\\n")
    s = s:gsub("\r", "\\r")
    s = s:gsub("\t", "\\t")
    return '"' .. s .. '"'
end

local function is_array(tbl)
    local count = 0
    local max_key = 0

    for k, _ in pairs(tbl) do
        if type(k) ~= "number" or k < 1 or k % 1 ~= 0 then
            return false
        end
        count = count + 1
        if k > max_key then
            max_key = k
        end
    end

    if count == 0 then
        return true
    end

    return max_key == count
end

local function canonicalize(value)
    local t = type(value)

    if t == "nil" then
        return "null"
    end

    if t == "boolean" then
        if value then
            return "true"
        end
        return "false"
    end

    if t == "number" then
        return string.format("%.17g", value)
    end

    if t == "string" then
        return escape_string(value)
    end

    if t ~= "table" then
        return escape_string(tostring(value))
    end

    if is_array(value) then
        local parts = {}
        for i = 1, #value do
            parts[#parts + 1] = canonicalize(value[i])
        end
        return "[" .. table.concat(parts, ",") .. "]"
    end

    local keys = {}
    for k, _ in pairs(value) do
        keys[#keys + 1] = k
    end
    table.sort(keys, function(a, b)
        return tostring(a) < tostring(b)
    end)

    local parts = {}
    for _, key in ipairs(keys) do
        parts[#parts + 1] = escape_string(tostring(key)) .. ":" .. canonicalize(value[key])
    end

    return "{" .. table.concat(parts, ",") .. "}"
end

local function fnv1a_u32(text)
    local hash = FNV_OFFSET_BASIS
    for i = 1, #text do
        hash = bxor32(hash, string.byte(text, i))
        hash = mul_mod32(hash, FNV_PRIME)
    end
    return hash
end

function M.fnv1a_hex(text)
    return string.format("%08x", fnv1a_u32(text or ""))
end

function M.table_checksum(value)
    return M.fnv1a_hex(canonicalize(value))
end

function M.event_checksum(event)
    local payload = {
        type = event and event.type,
        context = event and event.context or {},
        game_time_ms = (event and event.game_time_ms) or (event and event.timestamp) or 0,
    }
    return M.table_checksum(payload)
end

function M.background_checksum(bg_data)
    local payload = {}
    if type(bg_data) == "table" then
        for k, v in pairs(bg_data) do
            if k ~= "cs" then
                payload[k] = v
            end
        end
    end
    return M.table_checksum(payload)
end

function M.text_range_checksum(tier, text, start_ts, end_ts)
    local payload = {
        tier = tier,
        text = text or "",
        start_ts = start_ts or 0,
        end_ts = end_ts or 0,
    }
    return M.table_checksum(payload)
end

return M

--- Pure-Lua base64 decoder for TTS audio payload decoding.
-- Implements standard base64 (RFC 4648) with A-Z, a-z, 0-9, +, / alphabet and = padding.
-- Returns raw binary string suitable for io.open("wb") writes.
--
-- @module base64

local M = {}

-- Standard base64 alphabet lookup table (character -> 6-bit value)
local b64_decode_map = {}

-- Build decode map (A-Z: 0-25, a-z: 26-51, 0-9: 52-61, +: 62, /: 63)
local alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
for i = 1, #alphabet do
    b64_decode_map[alphabet:sub(i, i)] = i - 1
end

--- Decode a base64-encoded string to raw binary bytes.
-- Handles standard base64 alphabet with = padding.
-- Invalid characters are skipped (lenient parsing).
--
-- @param str string Base64-encoded string
-- @return string Raw binary bytes (empty string if input is empty)
function M.decode(str)
    if not str or str == "" then
        return ""
    end
    
    local result = {}
    local buffer = 0
    local bits_in_buffer = 0
    
    for i = 1, #str do
        local c = str:sub(i, i)
        
        -- Skip padding characters
        if c == "=" then
            break
        end
        
        local value = b64_decode_map[c]
        if value then
            -- Add 6 bits to buffer
            buffer = buffer * 64 + value
            bits_in_buffer = bits_in_buffer + 6
            
            -- Extract full bytes (8 bits) when available
            while bits_in_buffer >= 8 do
                bits_in_buffer = bits_in_buffer - 8
                local byte = math.floor(buffer / (2 ^ bits_in_buffer))
                buffer = buffer % (2 ^ bits_in_buffer)
                result[#result + 1] = string.char(byte)
            end
        end
        -- Invalid characters are silently skipped (lenient)
    end
    
    return table.concat(result)
end

--- Encode raw binary bytes to a base64 string (RFC 4648).
-- @param str string  Raw binary bytes
-- @return string     Base64-encoded string with = padding
function M.encode(str)
    if not str or str == "" then
        return ""
    end

    local result = {}
    local i = 1
    local len = #str

    while i <= len do
        local a = string.byte(str, i)
        local b = (i + 1 <= len) and string.byte(str, i + 1) or 0
        local c = (i + 2 <= len) and string.byte(str, i + 2) or 0
        local remaining = len - i + 1

        local n = a * 65536 + b * 256 + c

        result[#result + 1] = alphabet:sub(math.floor(n / 262144) + 1, math.floor(n / 262144) + 1)
        result[#result + 1] = alphabet:sub(math.floor(n / 4096) % 64 + 1, math.floor(n / 4096) % 64 + 1)
        if remaining >= 2 then
            result[#result + 1] = alphabet:sub(math.floor(n / 64) % 64 + 1, math.floor(n / 64) % 64 + 1)
        else
            result[#result + 1] = "="
        end
        if remaining >= 3 then
            result[#result + 1] = alphabet:sub(n % 64 + 1, n % 64 + 1)
        else
            result[#result + 1] = "="
        end

        i = i + 3
    end

    return table.concat(result)
end

return M

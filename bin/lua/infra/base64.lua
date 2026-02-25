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

return M

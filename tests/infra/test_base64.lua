package.path = package.path .. ";./bin/lua/?.lua;"

local base64 = require("infra.base64")

-- Helper to convert string to hex for debugging  
local function to_hex(str)
    local hex = ""
    for i = 1, #str do
        hex = hex .. string.format("%02X ", string.byte(str, i))
    end
    return hex
end

-- Test 1: Empty input returns empty string
local function test_empty_input()
    local result = base64.decode("")
    assert(result == "", "Empty input should return empty string")
    
    local result_nil = base64.decode(nil)
    assert(result_nil == "", "Nil input should return empty string")
    
    print("✓ Test 1: Empty input")
end

-- Test 2: Valid base64 decodes correctly
local function test_valid_base64()
    -- Test simple strings
    local tests = {
        {input = "SGVsbG8=", expected = "Hello"},      -- "Hello" with padding
        {input = "V29ybGQ=", expected = "World"},      -- "World" with padding
        {input = "YQ==", expected = "a"},              -- Single char with double padding
        {input = "YWI=", expected = "ab"},             -- Two chars with single padding
        {input = "YWJj", expected = "abc"},            -- Three chars no padding
    }
    
    for _, test in ipairs(tests) do
        local result = base64.decode(test.input)
        assert(result == test.expected, 
            string.format("Expected '%s', got '%s'", test.expected, result))
    end
    
    print("✓ Test 2: Valid base64 strings")
end

-- Test 3: Padding variations
local function test_padding()
    -- No padding (valid)
    local result1 = base64.decode("YWJj")  -- "abc"
    assert(result1 == "abc", "No padding should work")
    
    -- Single padding
    local result2 = base64.decode("YWI=")  -- "ab"
    assert(result2 == "ab", "Single padding should work")
    
    -- Double padding
    local result3 = base64.decode("YQ==")  -- "a"
    assert(result3 == "a", "Double padding should work")
    
    print("✓ Test 3: Padding variations")
end

-- Test 4: Known OGG header bytes round-trip
local function test_ogg_header()
    -- OGG Vorbis files start with "OggS" magic bytes (0x4F 0x67 0x67 0x53)
    local ogg_magic = string.char(0x4F, 0x67, 0x67, 0x53)
    
    -- Base64 of "OggS" is "T2dnUw=="
    local encoded = "T2dnUw=="
    local decoded = base64.decode(encoded)
    
    assert(decoded == ogg_magic, 
        string.format("Expected OggS magic bytes, got: %s", to_hex(decoded)))
    
    -- Verify each byte
    assert(string.byte(decoded, 1) == 0x4F, "First byte should be 0x4F")
    assert(string.byte(decoded, 2) == 0x67, "Second byte should be 0x67")
    assert(string.byte(decoded, 3) == 0x67, "Third byte should be 0x67")
    assert(string.byte(decoded, 4) == 0x53, "Fourth byte should be 0x53")
    
    print("✓ Test 4: OGG header bytes")
end

-- Test 5: Full alphabet coverage
local function test_full_alphabet()
    -- Test string that uses all base64 characters
    -- This is a base64-encoded sequence that covers the full alphabet
    local input = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    local result = base64.decode(input)
    
    -- Should produce non-empty binary output
    assert(#result > 0, "Full alphabet test should produce output")
    assert(#result == 48, "Expected 48 bytes from 64-char input")
    
    print("✓ Test 5: Full alphabet coverage")
end

-- Test 6: Binary data (non-ASCII)
local function test_binary_data()
    -- Test with bytes across the full 0-255 range
    -- Base64 of bytes [0x00, 0xFF, 0x80, 0x7F] is "AP+Afw=="
    local encoded = "AP+Afw=="
    local decoded = base64.decode(encoded)
    
    assert(#decoded == 4, "Should decode to 4 bytes")
    assert(string.byte(decoded, 1) == 0x00, "First byte should be 0x00")
    assert(string.byte(decoded, 2) == 0xFF, "Second byte should be 0xFF")
    assert(string.byte(decoded, 3) == 0x80, "Third byte should be 0x80")
    assert(string.byte(decoded, 4) == 0x7F, "Fourth byte should be 0x7F")
    
    print("✓ Test 6: Binary data (non-ASCII)")
end

-- Run all tests
local function run_tests()
    print("Running base64 decoder tests...")
    print()
    
    local tests = {
        test_empty_input,
        test_valid_base64,
        test_padding,
        test_ogg_header,
        test_full_alphabet,
        test_binary_data,
    }
    
    local passed = 0
    local failed = 0
    
    for _, test in ipairs(tests) do
        local status, err = pcall(test)
        if status then
            passed = passed + 1
        else
            failed = failed + 1
            print("✗ Test failed: " .. tostring(err))
        end
    end
    
    print()
    print(string.format("Results: %d passed, %d failed", passed, failed))
    
    if failed > 0 then
        os.exit(1)
    end
end

run_tests()

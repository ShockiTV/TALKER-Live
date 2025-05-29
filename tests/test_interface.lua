local luaunit = require('tests.utils.luaunit')

local function check_format_sanity(unformatted_description, event_objects)
    -- returns true if the amounts of format strings like %s, %d, %f match the amount of event_objects
    local format_count_s = select(2, unformatted_description:gsub("%%s", ""))
    local format_count_d = select(2, unformatted_description:gsub("%%d", ""))
    local format_count_f = select(2, unformatted_description:gsub("%%f", ""))
    local total_format_count = format_count_s + format_count_d + format_count_f
    return total_format_count == #event_objects
end

-- Test cases for check_format_sanity function
function testCheckFormatSanityWithMatchingFormatStringsAndEventObjects()
    local result = check_format_sanity("%s is %d years old", {"Alice", 30})
    luaunit.assertTrue(result)
end

function testCheckFormatSanityWithMoreFormatStringsThanEventObjects()
    local result = check_format_sanity("%s is %s years old", {"Alice"})
    luaunit.assertFalse(result)
end

function testCheckFormatSanityWithMoreEventObjectsThanFormatStrings()
    local result = check_format_sanity("%s is %s years old", {"Alice", 30, "extra"})
    luaunit.assertFalse(result)
end

function testCheckFormatSanityWithNoFormatStringsAndNoEventObjects()
    local result = check_format_sanity("No format strings here", {})
    luaunit.assertTrue(result)
end

function testCheckFormatSanityWithFormatStringsButNoEventObjects()
    local result = check_format_sanity("%s is %s years old", {})
    luaunit.assertFalse(result)
end

function testCheckFormatSanityWithNoFormatStringsButWithEventObjects()
    local result = check_format_sanity("No format strings here", {"Alice"})
    luaunit.assertFalse(result)
end


os.exit(luaunit.LuaUnit.run())
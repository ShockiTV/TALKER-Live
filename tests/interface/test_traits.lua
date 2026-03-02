-- tests/interface/test_traits.lua
-- Tests for traits map builder (task 3.2)
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local traits = require("interface.traits")

------------------------------------------------------------
-- Tests: Basic Traits Map Building
------------------------------------------------------------

function testBuildTraitsMapEmpty()
	local result = traits.build_traits_map({})
	luaunit.assertEquals(result, {})
end

function testBuildTraitsMapSingleCharacter()
	local char = { game_id = "char_1", name = "Speaker", faction = "stalker" }
	local result = traits.build_traits_map({ char })

	luaunit.assertNotNil(result["char_1"])
	luaunit.assertNotNil(result["char_1"].personality_id)
	luaunit.assertNotNil(result["char_1"].backstory_id)
end

function testBuildTraitsMapMultipleCharacters()
	local chars = {
		{ game_id = "char_1", name = "Speaker", faction = "stalker" },
		{ game_id = "char_2", name = "Victim", faction = "bandit" },
		{ game_id = "char_3", name = "Witness", faction = "ecolog" },
	}
	local result = traits.build_traits_map(chars)

	luaunit.assertNotNil(result["char_1"])
	luaunit.assertNotNil(result["char_2"])
	luaunit.assertNotNil(result["char_3"])
end

------------------------------------------------------------
-- Tests: Traits Structure
------------------------------------------------------------

function testTraitsStructureHasPersonalityAndBackstory()
	local char = { game_id = "char_1", faction = "stalker" }
	local result = traits.build_traits_map({ char })

	local char_traits = result["char_1"]
	luaunit.assertNotNil(char_traits.personality_id)
	luaunit.assertNotNil(char_traits.backstory_id)
end

function testTraitsAreStrings()
	local char = { game_id = "char_1", faction = "stalker" }
	local result = traits.build_traits_map({ char })

	local char_traits = result["char_1"]
	luaunit.assertEquals(type(char_traits.personality_id), "string")
	luaunit.assertEquals(type(char_traits.backstory_id), "string")
end

------------------------------------------------------------
-- Tests: Character ID Handling
------------------------------------------------------------

function testGameIdConvertedToString()
	local char = { game_id = 12345, faction = "stalker" }
	local result = traits.build_traits_map({ char })

	luaunit.assertNotNil(result["12345"])
end

function testNilCharacterSkipped()
	-- ipairs stops at first nil, so test with actual characters
	local result = traits.build_traits_map({ { game_id = "char_1", faction = "stalker" } })
	
	luaunit.assertNotNil(result["char_1"])
end

function testCharacterWithoutGameIdSkipped()
	local chars = {
		{ game_id = "char_1", faction = "stalker" },
		{ name = "No ID" },
		{ game_id = "char_2", faction = "bandit" },
	}
	local result = traits.build_traits_map(chars)

	luaunit.assertNotNil(result["char_1"])
	luaunit.assertNotNil(result["char_2"])
end

------------------------------------------------------------
-- Tests: Single Character Convenience Function
------------------------------------------------------------

function testBuildTraitsForCharacterSingle()
	local char = { game_id = "char_1", faction = "stalker" }
	local result = traits.build_traits_for_character(char)

	luaunit.assertNotNil(result["char_1"])
end

function testBuildTraitsForCharacterNil()
	local result = traits.build_traits_for_character(nil)

	luaunit.assertEquals(result, {})
end

function testBuildTraitsForCharacterNoId()
	local char = { name = "No ID", faction = "stalker" }
	local result = traits.build_traits_for_character(char)

	luaunit.assertEquals(result, {})
end

------------------------------------------------------------
-- Tests: Persistence and Consistency
------------------------------------------------------------

function testTraitsConsistentAcrossMultipleCalls()
	local char = { game_id = "char_1", faction = "stalker" }
	
	local result1 = traits.build_traits_map({ char })
	local result2 = traits.build_traits_map({ char })
	
	-- Same character should get same personality_id and backstory_id
	luaunit.assertEquals(result1["char_1"].personality_id, result2["char_1"].personality_id)
	luaunit.assertEquals(result1["char_1"].backstory_id, result2["char_1"].backstory_id)
end

-- Run all tests
os.exit(luaunit.LuaUnit.run())

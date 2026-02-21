package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit      = require('tests.utils.luaunit')
local mutant_names = require('domain.data.mutant_names')

function testBloodsucker()
    luaunit.assertEquals(mutant_names.describe("m_bloodsucker_e_01"), "a Bloodsucker")
end

function testZombie()
    luaunit.assertEquals(mutant_names.describe("m_zombie_e_01"), "a Zombie")
end

function testPseudodogNotMatchedAsDog()
    -- "m_pseudodog_01" contains "dog" but must match "pseudodog" first
    luaunit.assertEquals(mutant_names.describe("m_pseudodog_01"), "a Pseudodog")
end

function testPsyDogNotMatchedAsDog()
    -- "m_psy_dog_01" contains "dog" but must match "psy_dog" first
    luaunit.assertEquals(mutant_names.describe("m_psy_dog_01"), "a Psy Dog")
end

function testDogMatchedCorrectly()
    luaunit.assertEquals(mutant_names.describe("m_dog_e_01"), "a Dog")
end

function testChimera()
    luaunit.assertEquals(mutant_names.describe("m_chimera_e_01"), "a Chimera (extremely dangerous!)")
end

function testSturk()
    luaunit.assertEquals(mutant_names.describe("m_snork_e_01"), "a Snork")
end

function testUnknownMutantReturnsTechnicalName()
    luaunit.assertEquals(mutant_names.describe("mod_custom_creature"), "a mod_custom_creature")
end

function testNilReturnsDefault()
    -- should not throw; returns "a Unknown"
    local result = mutant_names.describe(nil)
    luaunit.assertStrContains(result, "Unknown")
end

function testBoar()
    luaunit.assertEquals(mutant_names.describe("m_boar_e_01"), "a Boar (bulletproof head)")
end

os.exit(luaunit.LuaUnit.run())

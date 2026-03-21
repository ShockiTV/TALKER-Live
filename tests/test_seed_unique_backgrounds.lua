-- tests/test_seed_unique_backgrounds.lua
-- Tests for the background seeding logic in talker_game_persistence.script
-- Tasks 3.3 (seeding populates), 3.4 (skips unresolved), 3.5 (no-reseed)
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit      = require('tests.utils.luaunit')
local memory_store  = require('domain.repo.memory_store_v2')

------------------------------------------------------------
-- Helpers: mock game globals needed by seed_unique_backgrounds()
------------------------------------------------------------

-- We need to simulate the seeding logic from talker_game_persistence.script
-- since it's a .script file we can't require() directly. Re-implement the
-- core logic here using the same approach.

local unique_backgrounds = require("domain.data.unique_backgrounds")

--- Minimal resolve_game_id using story_objects mock
local function make_resolve_game_id(story_map, alife_objects)
    return function(tech_name)
        -- Primary: story_objects lookup
        if story_map then
            local id = story_map[tech_name]
            if id then return id end
        end
        -- Fallback: alife scan
        if alife_objects then
            for _, obj in ipairs(alife_objects) do
                if obj.section == tech_name then
                    return obj.id
                end
            end
        end
        return nil
    end
end

--- Re-implementation of the seeding logic for testability
local function seed_backgrounds(resolve_game_id_fn)
    local data = unique_backgrounds.data
    local seeded = 0
    local skipped = 0

    for tech_name, entry in pairs(data) do
        if tech_name == "actor" then
            skipped = skipped + 1
        else
            local game_id = resolve_game_id_fn(tech_name)
            if game_id then
                local existing = memory_store:query(tostring(game_id), "memory.background")
                if not existing then
                    memory_store:mutate({
                        op = "set",
                        resource = "memory.background",
                        params = { character_id = tostring(game_id) },
                        data = {
                            backstory = entry.backstory,
                            traits = entry.traits,
                            connections = entry.connections,
                        },
                    })
                    seeded = seeded + 1
                else
                    skipped = skipped + 1
                end
            else
                skipped = skipped + 1
            end
        end
    end
    return seeded, skipped
end

------------------------------------------------------------
-- 3.3 Seeding populates memory_store_v2 backgrounds
------------------------------------------------------------

function testSeedingPopulatesBackgroundsForResolvedNPCs()
    memory_store:clear()
    -- Map a known set of tech_names to fake game_ids
    local story_map = {
        esc_m_trader = 100,
        esc_2_12_stalker_wolf = 101,
        esc_2_12_stalker_fanat = 102,
    }
    local resolve = make_resolve_game_id(story_map, nil)

    local seeded, _ = seed_backgrounds(resolve)
    luaunit.assertTrue(seeded >= 3, "Expected at least 3 seeded, got " .. seeded)

    -- Verify backgrounds are now set
    local bg, err = memory_store:query("100", "memory.background")
    luaunit.assertNil(err)
    luaunit.assertNotNil(bg, "Sidorovich background should be populated")
    luaunit.assertNotNil(bg.backstory)
    luaunit.assertNotNil(bg.traits)
    luaunit.assertNotNil(bg.connections)

    local bg_wolf, _ = memory_store:query("101", "memory.background")
    luaunit.assertNotNil(bg_wolf, "Wolf background should be populated")
    luaunit.assertEquals(type(bg_wolf.backstory), "string")
end

function testSeededBackstoryMatchesSourceData()
    memory_store:clear()
    local story_map = { esc_m_trader = 200 }
    local resolve = make_resolve_game_id(story_map, nil)
    seed_backgrounds(resolve)

    local bg, _ = memory_store:query("200", "memory.background")
    luaunit.assertNotNil(bg)
    -- Should match the original data
    luaunit.assertEquals(bg.backstory, unique_backgrounds.data["esc_m_trader"].backstory)
    luaunit.assertEquals(#bg.traits, #unique_backgrounds.data["esc_m_trader"].traits)
end

------------------------------------------------------------
-- 3.4 Seeding skips NPCs whose tech_name can't be resolved
------------------------------------------------------------

function testSeedingSkipsUnresolvedNPCs()
    memory_store:clear()
    -- Only resolve one NPC — all others will be skipped
    local story_map = { esc_m_trader = 300 }
    local resolve = make_resolve_game_id(story_map, nil)

    local seeded, skipped = seed_backgrounds(resolve)
    -- Only Sidorovich variants that map to esc_m_trader are resolved
    -- (All 3 sidorovich variants share the entry but only esc_m_trader maps to 300)
    luaunit.assertTrue(seeded >= 1, "Expected at least 1 seeded")
    luaunit.assertTrue(skipped > 90, "Expected most NPCs to be skipped, got " .. skipped)
end

function testSeedingWithNoResolutionSeedsNothing()
    memory_store:clear()
    -- Empty story_map, no alife — nothing resolves
    local resolve = make_resolve_game_id({}, nil)

    local seeded, skipped = seed_backgrounds(resolve)
    luaunit.assertEquals(seeded, 0)
    -- All entries should be skipped
    local total = 0
    for _ in pairs(unique_backgrounds.data) do total = total + 1 end
    luaunit.assertEquals(skipped, total)
end

function testSeedingUsesAlifeFallback()
    memory_store:clear()
    -- No story_objects, but alife finds wolf
    local alife_objects = {
        { section = "esc_2_12_stalker_wolf", id = 401 },
    }
    local resolve = make_resolve_game_id(nil, alife_objects)

    local seeded, _ = seed_backgrounds(resolve)
    luaunit.assertTrue(seeded >= 1, "Expected alife fallback to resolve at least 1 NPC")

    local bg, _ = memory_store:query("401", "memory.background")
    luaunit.assertNotNil(bg, "Wolf background should be populated via alife fallback")
end

------------------------------------------------------------
-- 3.5 Seeding does NOT run when existing data present
--     (brand new save detection in load_state)
------------------------------------------------------------

function testSeedingDoesNotOverwriteExistingBackgrounds()
    memory_store:clear()
    local story_map = { esc_m_trader = 500 }
    local resolve = make_resolve_game_id(story_map, nil)

    -- Pre-populate a custom background for Sidorovich
    memory_store:mutate({
        op = "set",
        resource = "memory.background",
        params = { character_id = "500" },
        data = { backstory = "CUSTOM", traits = {"custom"}, connections = {} },
    })

    -- Run seeding — should skip the already-populated character
    local seeded, _ = seed_backgrounds(resolve)
    -- Sidorovich shouldn't be re-seeded (all 3 variants map to same game_id 500)
    -- Only the esc_m_trader key resolves to 500, but it has existing background
    -- Other variants (esc_m_trader_hb, esc_m_trader_oa) also resolve if in story_map — 
    -- but they aren't in this map, so they skip as unresolved.

    -- Verify custom background was preserved
    local bg, _ = memory_store:query("500", "memory.background")
    luaunit.assertEquals(bg.backstory, "CUSTOM", "Existing background should not be overwritten")
end

function testBrandNewSaveDetection()
    -- Simulates the is_brand_new_save check from load_state
    -- Brand new save: both compressed_memories and tool_memories are nil
    local saved_data_new = {}
    local is_brand_new = not saved_data_new.compressed_memories and not saved_data_new.tool_memories
    luaunit.assertTrue(is_brand_new, "Empty saved_data should be detected as brand new save")

    -- Existing save with v1 data
    local saved_data_v1 = { compressed_memories = { memories_version = "2", memories = {} } }
    local is_brand_new_v1 = not saved_data_v1.compressed_memories and not saved_data_v1.tool_memories
    luaunit.assertFalse(is_brand_new_v1, "Save with compressed_memories should NOT be brand new")

    -- Existing save with v2 data
    local saved_data_v2 = { tool_memories = { memories_version = "3", memories = {} } }
    local is_brand_new_v2 = not saved_data_v2.compressed_memories and not saved_data_v2.tool_memories
    luaunit.assertFalse(is_brand_new_v2, "Save with tool_memories should NOT be brand new")
end

os.exit(luaunit.LuaUnit.run())

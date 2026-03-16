package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua;./gamedata/scripts/?.script'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local memory_store = require("domain.repo.memory_store_v2")
local Event = require("domain.model.event")
local EventType = require("domain.model.event_types")

require("talker_ws_query_handlers")

local function find_character(manifest, id)
    for _, entry in ipairs(manifest.characters or {}) do
        if tostring(entry.id) == tostring(id) then
            return entry
        end
    end
    return nil
end

local function setup_state()
    memory_store:clear()

    local ev1 = Event.create(EventType.DEATH, { actor = { game_id = "1", name = "Wolf" } }, 100)
    local ev2 = Event.create(EventType.IDLE, { actor = { game_id = "2", name = "Fanatic" } }, 200)

    memory_store:store_event("1", ev1)
    memory_store:store_event("2", ev2)

    memory_store:mutate({
        op = "append",
        resource = "memory.summaries",
        params = { character_id = "1" },
        data = {
            {
                tier = "summary",
                start_ts = 100,
                end_ts = 200,
                text = "summary text",
                source_count = 2,
            },
        },
    })

    memory_store:store_global_event(Event.create(EventType.EMISSION, { status = "starting" }, 300))
end

function testBuildSyncManifestIncludesCharactersAndTiers()
    setup_state()

    local manifest = build_sync_manifest()

    luaunit.assertNotNil(manifest)
    luaunit.assertNotNil(manifest.characters)

    local c1 = find_character(manifest, "1")
    local c2 = find_character(manifest, "2")

    luaunit.assertNotNil(c1)
    luaunit.assertNotNil(c2)

    luaunit.assertNotNil(c1.tiers.events)
    luaunit.assertNotNil(c1.tiers.summaries)
    luaunit.assertNotNil(c1.tiers.digests)
    luaunit.assertNotNil(c1.tiers.cores)

    luaunit.assertTrue(#c1.tiers.events >= 1)
    luaunit.assertTrue(#c1.tiers.summaries >= 1)

    local event_pair = c1.tiers.events[1]
    luaunit.assertNotNil(event_pair.ts)
    luaunit.assertNotNil(event_pair.cs)

    local summary_pair = c1.tiers.summaries[1]
    luaunit.assertNotNil(summary_pair.ts)
    luaunit.assertNotNil(summary_pair.cs)
end

function testBuildSyncManifestIncludesGlobalEvents()
    setup_state()

    local manifest = build_sync_manifest()

    luaunit.assertNotNil(manifest.global_events)
    luaunit.assertTrue(#manifest.global_events >= 1)

    local global_pair = manifest.global_events[1]
    luaunit.assertNotNil(global_pair.ts)
    luaunit.assertNotNil(global_pair.cs)
end

os.exit(luaunit.LuaUnit.run())

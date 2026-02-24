-- test_batch_handler.lua — Integration test for batch query handler logic
-- Tests the filter engine + resource registry interaction patterns
-- without requiring the actual game environment.
package.path = package.path .. ";./bin/lua/?.lua;./bin/lua/*/?.lua"
require("tests.test_bootstrap")
local luaunit = require("tests.utils.luaunit")
local fe = require("infra.query.filter_engine")

--------------------------------------------------------------------------------
-- Simulate resource resolver patterns (mirrors talker_ws_query_handlers)
--------------------------------------------------------------------------------

-- Helper: create an iterator from an array
local function array_iter(arr)
    local i = 0
    return function()
        i = i + 1
        return arr[i]
    end
end

--- Apply pipeline + projection (mirrors the helper in the handler)
local function apply_pipeline_and_projection(source_iter, query)
    local results = fe.execute_pipeline(
        source_iter,
        query.filter,
        query.sort,
        query.limit
    )
    if query.fields and #query.fields > 0 then
        local projected = {}
        for idx, doc in ipairs(results) do
            projected[idx] = fe.apply_projection(doc, query.fields)
        end
        return projected
    end
    return results
end

--------------------------------------------------------------------------------
-- Mock data
--------------------------------------------------------------------------------

local mock_events = {
    { type = "death", game_time_ms = 10000, context = { victim = { name = "Bandit", faction = "bandit" } },
      witnesses = { { game_id = "101", name = "Wolf", faction = "loner" } } },
    { type = "idle", game_time_ms = 20000, context = {}, witnesses = {} },
    { type = "death", game_time_ms = 30000, context = { victim = { name = "Monolith", faction = "monolith" } },
      witnesses = { { game_id = "101", name = "Wolf", faction = "loner" } } },
    { type = "injury", game_time_ms = 40000, context = { victim = { name = "Wolf", faction = "loner" } },
      witnesses = { { game_id = "102", name = "Fanatic", faction = "loner" } } },
    { type = "death", game_time_ms = 50000, context = { victim = { name = "Duty_Guard", faction = "duty" } },
      witnesses = { { game_id = "101", name = "Wolf", faction = "loner" } } },
}

local mock_memories = {
    ["101"] = {
        narrative = "Wolf has seen many battles in the Zone.",
        last_update_time_ms = 25000,
        new_events = { mock_events[3], mock_events[5] },
    },
}

local mock_personalities = {
    ["101"] = "generic.5",
    ["102"] = "bandit.3",
    ["103"] = "monolith.1",
}

local mock_backstories = {
    ["101"] = "unique.wolf",
    ["102"] = "generic.2",
}

local mock_levels = {
    ["l01_escape"] = { count = 3, log = { { game_time_ms = 1000 }, { game_time_ms = 5000 }, { game_time_ms = 9000 } } },
    ["l02_garbage"] = { count = 1, log = { { game_time_ms = 8000 } } },
}

--------------------------------------------------------------------------------
-- Simulated resource resolvers (using mock data)
--------------------------------------------------------------------------------

local mock_registry = {}

mock_registry["store.events"] = function(query)
    local iter = array_iter(mock_events)
    return apply_pipeline_and_projection(iter, query)
end

mock_registry["store.memories"] = function(query)
    local character_id = query.params and query.params.character_id
    if not character_id then error("store.memories requires params.character_id") end
    local ctx = mock_memories[character_id]
    if not ctx then
        return { character_id = character_id, narrative = nil, last_update_time_ms = 0, new_events = {} }
    end
    return {
        character_id = character_id,
        narrative = ctx.narrative,
        last_update_time_ms = ctx.last_update_time_ms,
        new_events = ctx.new_events,
    }
end

mock_registry["store.personalities"] = function(query)
    local collection = {}
    for char_id, personality_id in pairs(mock_personalities) do
        collection[#collection + 1] = { character_id = char_id, personality_id = personality_id }
    end
    local iter = array_iter(collection)
    return apply_pipeline_and_projection(iter, query)
end

mock_registry["store.backstories"] = function(query)
    local collection = {}
    for char_id, backstory_id in pairs(mock_backstories) do
        collection[#collection + 1] = { character_id = char_id, backstory_id = backstory_id }
    end
    local iter = array_iter(collection)
    return apply_pipeline_and_projection(iter, query)
end

mock_registry["store.levels"] = function(query)
    if query.params and query.params.level_id then
        local entry = mock_levels[query.params.level_id]
        if entry then
            return { level_id = query.params.level_id, count = entry.count, log = entry.log }
        end
        return { level_id = query.params.level_id, count = 0, log = {} }
    end
    local collection = {}
    for level_id, entry in pairs(mock_levels) do
        collection[#collection + 1] = { level_id = level_id, count = entry.count, log = entry.log }
    end
    local iter = array_iter(collection)
    return apply_pipeline_and_projection(iter, query)
end

mock_registry["store.timers"] = function(query)
    return { game_time_accumulator = 99000, idle_last_check_time = 88000 }
end

--------------------------------------------------------------------------------
-- Simulated batch dispatcher (mirrors handle_batch_query)
--------------------------------------------------------------------------------

local function dispatch_batch(sub_queries)
    local results = {}

    for _, query in ipairs(sub_queries) do
        local qid = query.id
        local resource = query.resource
        local skip = false

        -- Resolve $ref strings
        if not skip and query.filter then
            local _, ref_err = fe.resolve_refs(query.filter, results)
            if ref_err then
                results[qid] = { ok = false, error = ref_err }
                skip = true
            end
        end
        if not skip and query.params then
            local _, ref_err = fe.resolve_refs(query.params, results)
            if ref_err then
                results[qid] = { ok = false, error = ref_err }
                skip = true
            end
        end

        if not skip then
            local resolver = mock_registry[resource]
            if not resolver then
                results[qid] = { ok = false, error = "unknown resource: " .. tostring(resource) }
            else
                local ok, data = pcall(resolver, query)
                if ok then
                    results[qid] = { ok = true, data = data }
                else
                    results[qid] = { ok = false, error = tostring(data) }
                end
            end
        end
    end
    return results
end

--------------------------------------------------------------------------------
-- Tests
--------------------------------------------------------------------------------

function test_batch_dispatch_multiple_resources()
    local results = dispatch_batch({
        { id = "mem", resource = "store.memories", params = { character_id = "101" } },
        { id = "timers", resource = "store.timers" },
    })
    luaunit.assertTrue(results["mem"].ok)
    luaunit.assertEquals(results["mem"].data.narrative, "Wolf has seen many battles in the Zone.")
    luaunit.assertTrue(results["timers"].ok)
    luaunit.assertEquals(results["timers"].data.game_time_accumulator, 99000)
end

function test_batch_store_events_filter_and_limit()
    local results = dispatch_batch({
        { id = "ev", resource = "store.events",
          filter = { type = "death" },
          sort = { game_time_ms = -1 },
          limit = 2 },
    })
    luaunit.assertTrue(results["ev"].ok)
    luaunit.assertEquals(#results["ev"].data, 2)
    luaunit.assertEquals(results["ev"].data[1].game_time_ms, 50000)
    luaunit.assertEquals(results["ev"].data[2].game_time_ms, 30000)
end

function test_batch_store_events_with_projection()
    local results = dispatch_batch({
        { id = "ev", resource = "store.events",
          filter = { type = "death" },
          limit = 1,
          sort = { game_time_ms = -1 },
          fields = { "type", "game_time_ms" } },
    })
    luaunit.assertTrue(results["ev"].ok)
    luaunit.assertEquals(#results["ev"].data, 1)
    luaunit.assertEquals(results["ev"].data[1].type, "death")
    luaunit.assertEquals(results["ev"].data[1].game_time_ms, 50000)
    luaunit.assertNil(results["ev"].data[1].context)
end

function test_batch_ref_resolution()
    local results = dispatch_batch({
        { id = "mem", resource = "store.memories", params = { character_id = "101" } },
        { id = "ev", resource = "store.events",
          filter = { game_time_ms = { ["$gt"] = "$ref:mem.last_update_time_ms" }, type = "death" },
          sort = { game_time_ms = -1 } },
    })
    luaunit.assertTrue(results["mem"].ok)
    luaunit.assertTrue(results["ev"].ok)
    -- mem.last_update_time_ms = 25000, so events after 25000 with type=death: 30000, 50000
    luaunit.assertEquals(#results["ev"].data, 2)
    luaunit.assertEquals(results["ev"].data[1].game_time_ms, 50000)
    luaunit.assertEquals(results["ev"].data[2].game_time_ms, 30000)
end

function test_batch_ref_to_unresolved_query()
    local results = dispatch_batch({
        { id = "ev", resource = "store.events",
          filter = { game_time_ms = { ["$gt"] = "$ref:missing.timestamp" } } },
    })
    luaunit.assertFalse(results["ev"].ok)
    luaunit.assertStrContains(results["ev"].error, "'missing' not yet resolved")
end

function test_batch_ref_to_failed_query()
    local results = dispatch_batch({
        { id = "mem", resource = "store.memories" }, -- will fail: no character_id
        { id = "ev", resource = "store.events",
          filter = { game_time_ms = { ["$gt"] = "$ref:mem.last_update_time_ms" } } },
    })
    luaunit.assertFalse(results["mem"].ok)
    luaunit.assertFalse(results["ev"].ok)
    luaunit.assertStrContains(results["ev"].error, "'mem' resolved to error")
end

function test_batch_unknown_resource()
    local results = dispatch_batch({
        { id = "x", resource = "store.nonexistent" },
    })
    luaunit.assertFalse(results["x"].ok)
    luaunit.assertStrContains(results["x"].error, "unknown resource")
end

function test_batch_error_isolation()
    local results = dispatch_batch({
        { id = "bad", resource = "store.memories" }, -- fails: no character_id
        { id = "good", resource = "store.timers" },  -- should succeed anyway
    })
    luaunit.assertFalse(results["bad"].ok)
    luaunit.assertTrue(results["good"].ok)
    luaunit.assertEquals(results["good"].data.game_time_accumulator, 99000)
end

function test_batch_empty_queries()
    local results = dispatch_batch({})
    -- Should return empty results
    luaunit.assertNil(next(results))
end

function test_batch_personalities_collection()
    local results = dispatch_batch({
        { id = "p", resource = "store.personalities",
          filter = { personality_id = { ["$regex"] = "^bandit" } } },
    })
    luaunit.assertTrue(results["p"].ok)
    luaunit.assertEquals(#results["p"].data, 1)
    luaunit.assertEquals(results["p"].data[1].personality_id, "bandit.3")
end

function test_batch_backstories_collection()
    local results = dispatch_batch({
        { id = "b", resource = "store.backstories" },
    })
    luaunit.assertTrue(results["b"].ok)
    luaunit.assertEquals(#results["b"].data, 2)
end

function test_batch_levels_single_lookup()
    local results = dispatch_batch({
        { id = "lv", resource = "store.levels", params = { level_id = "l01_escape" } },
    })
    luaunit.assertTrue(results["lv"].ok)
    luaunit.assertEquals(results["lv"].data.count, 3)
    luaunit.assertEquals(results["lv"].data.level_id, "l01_escape")
end

function test_batch_levels_collection()
    local results = dispatch_batch({
        { id = "lv", resource = "store.levels",
          filter = { count = { ["$gt"] = 1 } } },
    })
    luaunit.assertTrue(results["lv"].ok)
    luaunit.assertEquals(#results["lv"].data, 1)
    luaunit.assertEquals(results["lv"].data[1].level_id, "l01_escape")
end

function test_batch_ref_in_params()
    local results = dispatch_batch({
        { id = "timers", resource = "store.timers" },
        { id = "ev", resource = "store.events",
          filter = { game_time_ms = { ["$gt"] = "$ref:timers.game_time_accumulator" } } },
    })
    luaunit.assertTrue(results["timers"].ok)
    luaunit.assertTrue(results["ev"].ok)
    -- game_time_accumulator = 99000, no events after 99000
    luaunit.assertEquals(#results["ev"].data, 0)
end

--------------------------------------------------------------------------------
-- Run
--------------------------------------------------------------------------------

os.exit(luaunit.LuaUnit.run())

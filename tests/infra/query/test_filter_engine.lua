-- test_filter_engine.lua — Unit tests for bin/lua/infra/query/filter_engine.lua
package.path = package.path .. ";./bin/lua/?.lua;./bin/lua/*/?.lua"
local luaunit = require("tests.utils.luaunit")
local fe = require("infra.query.filter_engine")

--------------------------------------------------------------------------------
-- resolve_path tests
--------------------------------------------------------------------------------

function test_resolve_path_simple()
    local doc = { type = "death", game_time_ms = 50000 }
    luaunit.assertEquals(fe.resolve_path(doc, "type"), "death")
    luaunit.assertEquals(fe.resolve_path(doc, "game_time_ms"), 50000)
end

function test_resolve_path_nested()
    local doc = { context = { victim = { faction = "bandit" } } }
    luaunit.assertEquals(fe.resolve_path(doc, "context.victim.faction"), "bandit")
end

function test_resolve_path_missing_nested()
    local doc = { context = {} }
    luaunit.assertNil(fe.resolve_path(doc, "context.weapon"))
end

function test_resolve_path_numeric_index()
    local doc = { witnesses = { { name = "Wolf" }, { name = "Fanatic" } } }
    luaunit.assertEquals(fe.resolve_path(doc, "witnesses.0.name"), "Wolf")
    luaunit.assertEquals(fe.resolve_path(doc, "witnesses.1.name"), "Fanatic")
end

function test_resolve_path_nil_doc()
    luaunit.assertNil(fe.resolve_path(nil, "type"))
end

function test_resolve_path_empty_path()
    local doc = { type = "death" }
    luaunit.assertEquals(fe.resolve_path(doc, ""), doc)
end

function test_resolve_path_nil_path()
    local doc = { type = "death" }
    luaunit.assertEquals(fe.resolve_path(doc, nil), doc)
end

function test_resolve_path_deep_nested_nil()
    local doc = { a = { b = {} } }
    luaunit.assertNil(fe.resolve_path(doc, "a.b.c.d"))
end

--------------------------------------------------------------------------------
-- Comparison operator tests
--------------------------------------------------------------------------------

function test_implicit_eq()
    local doc = { type = "death" }
    luaunit.assertTrue(fe.evaluate_filter(doc, { type = "death" }))
    luaunit.assertFalse(fe.evaluate_filter(doc, { type = "injury" }))
end

function test_explicit_eq()
    local doc = { type = "death" }
    luaunit.assertTrue(fe.evaluate_filter(doc, { type = { ["$eq"] = "death" } }))
    luaunit.assertFalse(fe.evaluate_filter(doc, { type = { ["$eq"] = "injury" } }))
end

function test_ne()
    local doc = { type = "idle" }
    luaunit.assertFalse(fe.evaluate_filter(doc, { type = { ["$ne"] = "idle" } }))
    luaunit.assertTrue(fe.evaluate_filter(doc, { type = { ["$ne"] = "death" } }))
end

function test_gt()
    local doc = { game_time_ms = 60000 }
    luaunit.assertTrue(fe.evaluate_filter(doc, { game_time_ms = { ["$gt"] = 50000 } }))
    luaunit.assertFalse(fe.evaluate_filter(doc, { game_time_ms = { ["$gt"] = 60000 } }))
    luaunit.assertFalse(fe.evaluate_filter(doc, { game_time_ms = { ["$gt"] = 70000 } }))
end

function test_gte()
    local doc = { game_time_ms = 60000 }
    luaunit.assertTrue(fe.evaluate_filter(doc, { game_time_ms = { ["$gte"] = 50000 } }))
    luaunit.assertTrue(fe.evaluate_filter(doc, { game_time_ms = { ["$gte"] = 60000 } }))
    luaunit.assertFalse(fe.evaluate_filter(doc, { game_time_ms = { ["$gte"] = 70000 } }))
end

function test_lt()
    local doc = { game_time_ms = 60000 }
    luaunit.assertFalse(fe.evaluate_filter(doc, { game_time_ms = { ["$lt"] = 50000 } }))
    luaunit.assertFalse(fe.evaluate_filter(doc, { game_time_ms = { ["$lt"] = 60000 } }))
    luaunit.assertTrue(fe.evaluate_filter(doc, { game_time_ms = { ["$lt"] = 70000 } }))
end

function test_lte()
    local doc = { game_time_ms = 60000 }
    luaunit.assertFalse(fe.evaluate_filter(doc, { game_time_ms = { ["$lte"] = 50000 } }))
    luaunit.assertTrue(fe.evaluate_filter(doc, { game_time_ms = { ["$lte"] = 60000 } }))
    luaunit.assertTrue(fe.evaluate_filter(doc, { game_time_ms = { ["$lte"] = 70000 } }))
end

function test_comparison_nil_field()
    local doc = {}
    luaunit.assertFalse(fe.evaluate_filter(doc, { game_time_ms = { ["$gt"] = 0 } }))
    luaunit.assertFalse(fe.evaluate_filter(doc, { game_time_ms = { ["$lt"] = 100 } }))
end

--------------------------------------------------------------------------------
-- Set operator tests
--------------------------------------------------------------------------------

function test_in_match()
    local doc = { type = "injury" }
    luaunit.assertTrue(fe.evaluate_filter(doc, { type = { ["$in"] = { "death", "injury" } } }))
end

function test_in_no_match()
    local doc = { type = "idle" }
    luaunit.assertFalse(fe.evaluate_filter(doc, { type = { ["$in"] = { "death", "injury" } } }))
end

function test_in_nil_field()
    local doc = {}
    luaunit.assertFalse(fe.evaluate_filter(doc, { type = { ["$in"] = { "death" } } }))
end

function test_nin_match()
    local doc = { type = "death" }
    luaunit.assertTrue(fe.evaluate_filter(doc, { type = { ["$nin"] = { "idle", "reload" } } }))
end

function test_nin_exclude()
    local doc = { type = "idle" }
    luaunit.assertFalse(fe.evaluate_filter(doc, { type = { ["$nin"] = { "idle", "reload" } } }))
end

function test_nin_nil_field()
    -- nil field: $nin should match (value not in the list)
    local doc = {}
    luaunit.assertTrue(fe.evaluate_filter(doc, { type = { ["$nin"] = { "idle" } } }))
end

--------------------------------------------------------------------------------
-- String operator tests
--------------------------------------------------------------------------------

function test_regex_match()
    local doc = { name = "Stalker_42" }
    luaunit.assertTrue(fe.evaluate_filter(doc, { name = { ["$regex"] = "^Stalker_" } }))
end

function test_regex_no_match()
    local doc = { name = "Wolf" }
    luaunit.assertFalse(fe.evaluate_filter(doc, { name = { ["$regex"] = "^bandit" } }))
end

function test_regex_case_insensitive()
    local doc = { name = "Wolf" }
    luaunit.assertTrue(fe.evaluate_filter(doc, { name = { ["$regex"] = "wolf", ["$regex_flags"] = "i" } }))
end

function test_regex_nil_field()
    local doc = {}
    luaunit.assertFalse(fe.evaluate_filter(doc, { name = { ["$regex"] = "test" } }))
end

function test_regex_non_string_field()
    local doc = { count = 42 }
    luaunit.assertFalse(fe.evaluate_filter(doc, { count = { ["$regex"] = "42" } }))
end

--------------------------------------------------------------------------------
-- Existence operator tests
--------------------------------------------------------------------------------

function test_exists_true_present()
    local doc = { context = { weapon = "AK-74" } }
    luaunit.assertTrue(fe.evaluate_filter(doc, { ["context.weapon"] = { ["$exists"] = true } }))
end

function test_exists_true_absent()
    local doc = { context = {} }
    luaunit.assertFalse(fe.evaluate_filter(doc, { ["context.weapon"] = { ["$exists"] = true } }))
end

function test_exists_false_absent()
    local doc = { context = {} }
    luaunit.assertTrue(fe.evaluate_filter(doc, { ["context.weapon"] = { ["$exists"] = false } }))
end

function test_exists_false_present()
    local doc = { context = { weapon = "AK-74" } }
    luaunit.assertFalse(fe.evaluate_filter(doc, { ["context.weapon"] = { ["$exists"] = false } }))
end

--------------------------------------------------------------------------------
-- Array operator tests
--------------------------------------------------------------------------------

function test_elemMatch_match()
    local doc = {
        witnesses = {
            { game_id = "123", faction = "duty" },
            { game_id = "456", faction = "bandit" },
        },
    }
    luaunit.assertTrue(fe.evaluate_filter(doc, {
        witnesses = { ["$elemMatch"] = { game_id = "123", faction = "duty" } },
    }))
end

function test_elemMatch_no_single_element_matches_all()
    local doc = {
        witnesses = {
            { game_id = "123", faction = "duty" },
            { game_id = "456", faction = "bandit" },
        },
    }
    luaunit.assertFalse(fe.evaluate_filter(doc, {
        witnesses = { ["$elemMatch"] = { game_id = "123", faction = "bandit" } },
    }))
end

function test_elemMatch_non_array()
    local doc = { witnesses = "not_an_array" }
    luaunit.assertFalse(fe.evaluate_filter(doc, {
        witnesses = { ["$elemMatch"] = { game_id = "123" } },
    }))
end

function test_elemMatch_empty_array()
    local doc = { witnesses = {} }
    luaunit.assertFalse(fe.evaluate_filter(doc, {
        witnesses = { ["$elemMatch"] = { game_id = "123" } },
    }))
end

function test_size_match()
    local doc = { witnesses = { { name = "A" }, { name = "B" } } }
    luaunit.assertTrue(fe.evaluate_filter(doc, { witnesses = { ["$size"] = 2 } }))
end

function test_size_no_match()
    local doc = { witnesses = { { name = "A" }, { name = "B" } } }
    luaunit.assertFalse(fe.evaluate_filter(doc, { witnesses = { ["$size"] = 3 } }))
end

function test_size_non_table()
    local doc = { witnesses = "not_a_table" }
    luaunit.assertFalse(fe.evaluate_filter(doc, { witnesses = { ["$size"] = 0 } }))
end

function test_all_match()
    local doc = { tags = { "combat", "zone", "mutant" } }
    luaunit.assertTrue(fe.evaluate_filter(doc, { tags = { ["$all"] = { "combat", "mutant" } } }))
end

function test_all_no_match()
    local doc = { tags = { "combat", "zone" } }
    luaunit.assertFalse(fe.evaluate_filter(doc, { tags = { ["$all"] = { "combat", "mutant" } } }))
end

function test_all_non_table()
    local doc = { tags = "string" }
    luaunit.assertFalse(fe.evaluate_filter(doc, { tags = { ["$all"] = { "string" } } }))
end

--------------------------------------------------------------------------------
-- Logical operator tests
--------------------------------------------------------------------------------

function test_implicit_and()
    local doc = { type = "death", game_time_ms = 60000 }
    luaunit.assertTrue(fe.evaluate_filter(doc, { type = "death", game_time_ms = { ["$gt"] = 50000 } }))
end

function test_implicit_and_fails()
    local doc = { type = "death", game_time_ms = 40000 }
    luaunit.assertFalse(fe.evaluate_filter(doc, { type = "death", game_time_ms = { ["$gt"] = 50000 } }))
end

function test_or_match()
    local doc = { type = "injury" }
    luaunit.assertTrue(fe.evaluate_filter(doc, {
        ["$or"] = { { type = "death" }, { type = "injury" } },
    }))
end

function test_or_no_match()
    local doc = { type = "idle" }
    luaunit.assertFalse(fe.evaluate_filter(doc, {
        ["$or"] = { { type = "death" }, { type = "injury" } },
    }))
end

function test_explicit_and()
    local doc = { game_time_ms = 70000 }
    luaunit.assertTrue(fe.evaluate_filter(doc, {
        ["$and"] = {
            { game_time_ms = { ["$gt"] = 50000 } },
            { game_time_ms = { ["$lt"] = 90000 } },
        },
    }))
end

function test_explicit_and_fails()
    local doc = { game_time_ms = 40000 }
    luaunit.assertFalse(fe.evaluate_filter(doc, {
        ["$and"] = {
            { game_time_ms = { ["$gt"] = 50000 } },
            { game_time_ms = { ["$lt"] = 90000 } },
        },
    }))
end

function test_not_operator()
    local doc = { type = "death" }
    luaunit.assertTrue(fe.evaluate_filter(doc, {
        type = { ["$not"] = { ["$in"] = { "idle", "reload" } } },
    }))
end

function test_not_operator_fails()
    local doc = { type = "idle" }
    luaunit.assertFalse(fe.evaluate_filter(doc, {
        type = { ["$not"] = { ["$in"] = { "idle", "reload" } } },
    }))
end

function test_nested_logical()
    local doc = { type = "death", game_time_ms = 60000 }
    luaunit.assertTrue(fe.evaluate_filter(doc, {
        ["$and"] = {
            { game_time_ms = { ["$gt"] = 50000 } },
            { ["$or"] = { { type = "death" }, { type = "injury" } } },
        },
    }))
end

function test_nested_logical_fails()
    local doc = { type = "idle", game_time_ms = 60000 }
    luaunit.assertFalse(fe.evaluate_filter(doc, {
        ["$and"] = {
            { game_time_ms = { ["$gt"] = 50000 } },
            { ["$or"] = { { type = "death" }, { type = "injury" } } },
        },
    }))
end

function test_empty_filter_matches_all()
    local doc = { type = "anything" }
    luaunit.assertTrue(fe.evaluate_filter(doc, {}))
    luaunit.assertTrue(fe.evaluate_filter(doc, nil))
end

--------------------------------------------------------------------------------
-- Pipeline tests — helpers
--------------------------------------------------------------------------------

-- Create an iterator from an array
local function array_iter(arr)
    local i = 0
    return function()
        i = i + 1
        return arr[i]
    end
end

--------------------------------------------------------------------------------
-- Pipeline: fused top-N (sort + limit)
--------------------------------------------------------------------------------

function test_pipeline_top_n_descending()
    local docs = {}
    for i = 1, 100 do
        docs[i] = { game_time_ms = i * 1000, type = "death" }
    end
    local result = fe.execute_pipeline(array_iter(docs), nil, { game_time_ms = -1 }, 3)
    luaunit.assertEquals(#result, 3)
    luaunit.assertEquals(result[1].game_time_ms, 100000)
    luaunit.assertEquals(result[2].game_time_ms, 99000)
    luaunit.assertEquals(result[3].game_time_ms, 98000)
end

function test_pipeline_top_n_ascending()
    local docs = {}
    for i = 1, 100 do
        docs[i] = { game_time_ms = i * 1000, type = "death" }
    end
    local result = fe.execute_pipeline(array_iter(docs), nil, { game_time_ms = 1 }, 3)
    luaunit.assertEquals(#result, 3)
    luaunit.assertEquals(result[1].game_time_ms, 1000)
    luaunit.assertEquals(result[2].game_time_ms, 2000)
    luaunit.assertEquals(result[3].game_time_ms, 3000)
end

function test_pipeline_top_n_with_filter()
    local docs = {}
    for i = 1, 100 do
        docs[i] = { game_time_ms = i * 1000, type = (i % 2 == 0) and "death" or "idle" }
    end
    local result = fe.execute_pipeline(
        array_iter(docs),
        { type = "death" },
        { game_time_ms = -1 },
        3
    )
    luaunit.assertEquals(#result, 3)
    luaunit.assertEquals(result[1].game_time_ms, 100000)
    luaunit.assertEquals(result[2].game_time_ms, 98000)
    luaunit.assertEquals(result[3].game_time_ms, 96000)
end

function test_pipeline_top_n_fewer_than_limit()
    local docs = {
        { game_time_ms = 1000 },
        { game_time_ms = 2000 },
    }
    local result = fe.execute_pipeline(array_iter(docs), nil, { game_time_ms = -1 }, 50)
    luaunit.assertEquals(#result, 2)
    luaunit.assertEquals(result[1].game_time_ms, 2000)
    luaunit.assertEquals(result[2].game_time_ms, 1000)
end

--------------------------------------------------------------------------------
-- Pipeline: early-termination (limit only)
--------------------------------------------------------------------------------

function test_pipeline_early_termination()
    local docs = {}
    for i = 1, 1000 do
        docs[i] = { game_time_ms = i * 1000, type = "death" }
    end
    local result = fe.execute_pipeline(array_iter(docs), nil, nil, 5)
    luaunit.assertEquals(#result, 5)
    luaunit.assertEquals(result[1].game_time_ms, 1000)
    luaunit.assertEquals(result[5].game_time_ms, 5000)
end

function test_pipeline_early_termination_with_filter()
    local docs = {}
    for i = 1, 100 do
        docs[i] = { game_time_ms = i * 1000, type = (i % 2 == 0) and "death" or "idle" }
    end
    local result = fe.execute_pipeline(
        array_iter(docs),
        { type = "death" },
        nil,
        3
    )
    luaunit.assertEquals(#result, 3)
    -- First 3 even indices: 2, 4, 6
    luaunit.assertEquals(result[1].game_time_ms, 2000)
    luaunit.assertEquals(result[2].game_time_ms, 4000)
    luaunit.assertEquals(result[3].game_time_ms, 6000)
end

function test_pipeline_limit_larger_than_matches()
    local docs = {
        { game_time_ms = 1000, type = "death" },
        { game_time_ms = 2000, type = "idle" },
        { game_time_ms = 3000, type = "death" },
    }
    local result = fe.execute_pipeline(
        array_iter(docs),
        { type = "death" },
        nil,
        50
    )
    luaunit.assertEquals(#result, 2)
end

--------------------------------------------------------------------------------
-- Pipeline: sort only
--------------------------------------------------------------------------------

function test_pipeline_sort_ascending()
    local docs = {
        { game_time_ms = 300 },
        { game_time_ms = 100 },
        { game_time_ms = 200 },
    }
    local result = fe.execute_pipeline(array_iter(docs), nil, { game_time_ms = 1 }, nil)
    luaunit.assertEquals(#result, 3)
    luaunit.assertEquals(result[1].game_time_ms, 100)
    luaunit.assertEquals(result[2].game_time_ms, 200)
    luaunit.assertEquals(result[3].game_time_ms, 300)
end

function test_pipeline_sort_descending()
    local docs = {
        { game_time_ms = 300 },
        { game_time_ms = 100 },
        { game_time_ms = 200 },
    }
    local result = fe.execute_pipeline(array_iter(docs), nil, { game_time_ms = -1 }, nil)
    luaunit.assertEquals(#result, 3)
    luaunit.assertEquals(result[1].game_time_ms, 300)
    luaunit.assertEquals(result[2].game_time_ms, 200)
    luaunit.assertEquals(result[3].game_time_ms, 100)
end

--------------------------------------------------------------------------------
-- Pipeline: collect all (filter only)
--------------------------------------------------------------------------------

function test_pipeline_filter_only()
    local docs = {
        { type = "death" },
        { type = "idle" },
        { type = "death" },
        { type = "injury" },
    }
    local result = fe.execute_pipeline(array_iter(docs), { type = "death" }, nil, nil)
    luaunit.assertEquals(#result, 2)
    luaunit.assertEquals(result[1].type, "death")
    luaunit.assertEquals(result[2].type, "death")
end

function test_pipeline_no_filter_no_sort_no_limit()
    local docs = {
        { type = "a" },
        { type = "b" },
        { type = "c" },
    }
    local result = fe.execute_pipeline(array_iter(docs), nil, nil, nil)
    luaunit.assertEquals(#result, 3)
end

--------------------------------------------------------------------------------
-- Projection tests
--------------------------------------------------------------------------------

function test_projection_specific_fields()
    local doc = { type = "death", game_time_ms = 50000, context = { weapon = "AK" }, witnesses = {} }
    local projected = fe.apply_projection(doc, { "type", "game_time_ms" })
    luaunit.assertEquals(projected.type, "death")
    luaunit.assertEquals(projected.game_time_ms, 50000)
    luaunit.assertNil(projected.context)
    luaunit.assertNil(projected.witnesses)
end

function test_projection_nested_dotted_path()
    local doc = {
        type = "death",
        context = { victim = { name = "Wolf", faction = "loner" } },
    }
    local projected = fe.apply_projection(doc, { "context.victim.name", "type" })
    luaunit.assertEquals(projected.type, "death")
    luaunit.assertEquals(projected.context.victim.name, "Wolf")
    luaunit.assertNil(projected.context.victim.faction)
end

function test_projection_nil_fields()
    local doc = { type = "death" }
    local projected = fe.apply_projection(doc, nil)
    luaunit.assertEquals(projected, doc) -- Same reference
end

function test_projection_empty_fields()
    local doc = { type = "death" }
    local projected = fe.apply_projection(doc, {})
    luaunit.assertEquals(projected, doc)
end

function test_projection_missing_field()
    local doc = { type = "death" }
    local projected = fe.apply_projection(doc, { "nonexistent" })
    luaunit.assertNil(projected.nonexistent)
end

--------------------------------------------------------------------------------
-- $ref resolver tests
--------------------------------------------------------------------------------

function test_ref_resolve_simple()
    local results_map = {
        mem = { ok = true, data = { last_update_time_ms = 50000 } },
    }
    local filter = { game_time_ms = { ["$gt"] = "$ref:mem.last_update_time_ms" } }
    local resolved, err = fe.resolve_refs(filter, results_map)
    luaunit.assertNil(err)
    luaunit.assertEquals(resolved.game_time_ms["$gt"], 50000)
end

function test_ref_resolve_nested()
    local results_map = {
        char = { ok = true, data = { game_id = "12345" } },
    }
    local params = { character_id = "$ref:char.game_id" }
    local resolved, err = fe.resolve_refs(params, results_map)
    luaunit.assertNil(err)
    luaunit.assertEquals(resolved.character_id, "12345")
end

function test_ref_unresolved_query()
    local results_map = {}
    local filter = { x = "$ref:missing.val" }
    local _, err = fe.resolve_refs(filter, results_map)
    luaunit.assertNotNil(err)
    luaunit.assertStrContains(err, "'missing' not yet resolved")
end

function test_ref_failed_query()
    local results_map = {
        mem = { ok = false, error = "some error" },
    }
    local filter = { x = "$ref:mem.val" }
    local _, err = fe.resolve_refs(filter, results_map)
    luaunit.assertNotNil(err)
    luaunit.assertStrContains(err, "'mem' resolved to error")
end

function test_ref_deep_nested()
    local results_map = {
        mem = { ok = true, data = { timestamp = 99999 } },
    }
    local filter = {
        ["$and"] = {
            { game_time_ms = { ["$gt"] = "$ref:mem.timestamp" } },
            { type = "death" },
        },
    }
    local resolved, err = fe.resolve_refs(filter, results_map)
    luaunit.assertNil(err)
    luaunit.assertEquals(resolved["$and"][1].game_time_ms["$gt"], 99999)
end

function test_ref_no_refs_passthrough()
    local results_map = {}
    local filter = { type = "death", game_time_ms = { ["$gt"] = 50000 } }
    local resolved, err = fe.resolve_refs(filter, results_map)
    luaunit.assertNil(err)
    luaunit.assertEquals(resolved.type, "death")
    luaunit.assertEquals(resolved.game_time_ms["$gt"], 50000)
end

function test_ref_string_value_not_ref()
    local results_map = {}
    local tbl = { name = "just a string" }
    local resolved, err = fe.resolve_refs(tbl, results_map)
    luaunit.assertNil(err)
    luaunit.assertEquals(resolved.name, "just a string")
end

--------------------------------------------------------------------------------
-- Edge cases
--------------------------------------------------------------------------------

function test_filter_nested_path_comparison()
    local doc = { context = { victim = { faction = "bandit" } } }
    luaunit.assertTrue(fe.evaluate_filter(doc, { ["context.victim.faction"] = "bandit" }))
    luaunit.assertFalse(fe.evaluate_filter(doc, { ["context.victim.faction"] = "duty" }))
end

function test_filter_combined_operators_on_same_field()
    local doc = { game_time_ms = 60000 }
    luaunit.assertTrue(fe.evaluate_filter(doc, {
        game_time_ms = { ["$gt"] = 50000, ["$lt"] = 70000 },
    }))
    luaunit.assertFalse(fe.evaluate_filter(doc, {
        game_time_ms = { ["$gt"] = 50000, ["$lt"] = 55000 },
    }))
end

function test_pipeline_empty_source()
    local result = fe.execute_pipeline(array_iter({}), nil, nil, nil)
    luaunit.assertEquals(#result, 0)
end

function test_pipeline_empty_source_with_sort_and_limit()
    local result = fe.execute_pipeline(array_iter({}), nil, { game_time_ms = -1 }, 10)
    luaunit.assertEquals(#result, 0)
end

--------------------------------------------------------------------------------
-- Run
--------------------------------------------------------------------------------

os.exit(luaunit.LuaUnit.run())

-- tests/ws/test_mutation_handler.lua
-- Tests for state.mutate.batch handler (talker_ws_query_handlers integration with memory_store_v2)
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local memory_store_v2 = require("domain.repo.memory_store_v2")
local Event = require("domain.model.event")
local EventType = require("domain.model.event_types")

local function setup()
	memory_store_v2:clear()
end

------------------------------------------------------------
-- Helper: Simulate mutation handler behavior
------------------------------------------------------------

--- Simulate what the WS handler does: dispatch mutations sequentially
local function handle_batch_mutation(mutations_array)
	local results = {}
	for i, mutation in ipairs(mutations_array) do
		local mutation_id = mutation.id or tostring(i)
		local result = memory_store_v2:mutate(mutation)
		results[mutation_id] = result
	end
	return results
end

------------------------------------------------------------
-- Tests: Single Append Mutations
------------------------------------------------------------

function testAppendEventsMutation()
	memory_store_v2:clear()
	local mutations = {
		{
			id = "mut_1",
			op = "append",
			resource = "memory.events",
			params = { character_id = "char_1" },
			data = { {
				timestamp = 100,
				type = "idle",
				context = {},
			} },
		},
	}

	local results = handle_batch_mutation(mutations)

	luaunit.assertTrue(results.mut_1.ok)
	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 1)
	luaunit.assertEquals(events[1].timestamp, 100)
end

function testAppendSummariesMutation()
	memory_store_v2:clear()
	local mutations = {
		{
			id = "mut_1",
			op = "append",
			resource = "memory.summaries",
			params = { character_id = "char_1" },
			data = { {
				tier = "summary",
				start_ts = 100,
				end_ts = 200,
				text = "Summary text",
				source_count = 10,
			} },
		},
	}

	local results = handle_batch_mutation(mutations)

	luaunit.assertTrue(results.mut_1.ok)
	local summaries, _ = memory_store_v2:query("char_1", "memory.summaries", {})
	luaunit.assertEquals(#summaries, 1)
	luaunit.assertEquals(summaries[1].text, "Summary text")
end

------------------------------------------------------------
-- Tests: Single Delete Mutations
------------------------------------------------------------

function testDeleteEventsMutation()
	memory_store_v2:clear()
	-- Pre-populate with events (ts = game_time_ms = i*100)
	for i = 1, 5 do
		memory_store_v2:store_event("char_1", Event.create(EventType.IDLE, {}, i * 100))
	end

	local mutations = {
		{
			id = "mut_delete",
			op = "delete",
			resource = "memory.events",
			params = { character_id = "char_1" },
			ids = { 100, 200, 300 },  -- ts-based IDs
		},
	}

	local results = handle_batch_mutation(mutations)

	luaunit.assertTrue(results.mut_delete.ok)
	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 2)
	luaunit.assertEquals(events[1].ts, 400)
	luaunit.assertEquals(events[2].ts, 500)
end

------------------------------------------------------------
-- Tests: Single Set/Update Mutations
------------------------------------------------------------

function testSetBackgroundMutation()
	memory_store_v2:clear()
	local mutations = {
		{
			id = "mut_set_bg",
			op = "set",
			resource = "memory.background",
			params = { character_id = "char_1" },
			data = {
				traits = { "brave", "cautious" },
				backstory = "Old tale",
				connections = {},
			},
		},
	}

	local results = handle_batch_mutation(mutations)

	luaunit.assertTrue(results.mut_set_bg.ok)
	local bg, _ = memory_store_v2:query("char_1", "memory.background", {})
	luaunit.assertEquals(bg.traits[1], "brave")
	luaunit.assertEquals(bg.backstory, "Old tale")
end

function testUpdateBackgroundMutation()
	memory_store_v2:clear()
	-- Set first
	memory_store_v2:mutate({
		op = "set",
		resource = "memory.background",
		params = { character_id = "char_1" },
		data = {
			traits = { "brave" },
			backstory = "Origin",
			connections = {},
		},
	})

	-- Then update
	local mutations = {
		{
			id = "mut_update_bg",
			op = "update",
			resource = "memory.background",
			params = { character_id = "char_1" },
			ops = {
				["$push"] = { traits = "wise" },
				["$pull"] = { traits = "brave" },
			},
		},
	}

	local results = handle_batch_mutation(mutations)

	luaunit.assertTrue(results.mut_update_bg.ok)
	local bg, _ = memory_store_v2:query("char_1", "memory.background", {})
	-- Should have: wise (brave removed)
	local found_wise = false
	for _, t in ipairs(bg.traits) do
		if t == "wise" then found_wise = true end
	end
	luaunit.assertTrue(found_wise)
end

------------------------------------------------------------
-- Tests: Atomic Pattern (Delete + Append)
------------------------------------------------------------

function testAtomicCompactionPattern()
	memory_store_v2:clear()
	-- Populate events (ts = game_time_ms = i*100)
	for i = 1, 10 do
		memory_store_v2:store_event("char_1", Event.create(EventType.IDLE, {}, i * 100))
	end

	-- Atomic batch: delete 10 events, append 1 summary
	local mutations = {
		{
			id = "del_events",
			op = "delete",
			resource = "memory.events",
			params = { character_id = "char_1" },
			ids = { 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000 },
		},
		{
			id = "add_summary",
			op = "append",
			resource = "memory.summaries",
			params = { character_id = "char_1" },
			data = { {
				tier = "summary",
				start_ts = 100,
				end_ts = 1000,
				text = "Compressed 10 events",
				source_count = 10,
			} },
		},
	}

	local results = handle_batch_mutation(mutations)

	luaunit.assertTrue(results.del_events.ok)
	luaunit.assertTrue(results.add_summary.ok)

	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	local summaries, _ = memory_store_v2:query("char_1", "memory.summaries", {})

	luaunit.assertEquals(#events, 0)
	luaunit.assertEquals(#summaries, 1)
	luaunit.assertEquals(summaries[1].source_count, 10)
end

------------------------------------------------------------
-- Tests: Multi-Tier Cascade
------------------------------------------------------------

function testMultiTierCascade()
	memory_store_v2:clear()
	-- Simulate 4-tier compaction: events → summary → digest → core
	local mutations = {
		-- Step 1: Delete old events, append summary
		{
			id = "ev_to_sum",
			op = "delete",
			resource = "memory.events",
			params = { character_id = "char_1" },
			ids = { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 },
		},
		{
			id = "ev_to_sum",
			op = "append",
			resource = "memory.summaries",
			params = { character_id = "char_1" },
			data = { {
				tier = "summary",
				start_ts = 1000,
				end_ts = 2000,
				text = "First 10 events summarized",
				source_count = 10,
			} },
		},
		-- Step 2: Delete old summary, append digest
		{
			id = "sum_to_dig",
			op = "delete",
			resource = "memory.summaries",
			params = { character_id = "char_1" },
			ids = { 1 },
		},
		{
			id = "sum_to_dig",
			op = "append",
			resource = "memory.digests",
			params = { character_id = "char_1" },
			data = { {
				tier = "digest",
				start_ts = 1000,
				end_ts = 2000,
				text = "Events compressed to digest",
				source_count = 1,
			} },
		},
	}

	local results = handle_batch_mutation(mutations)

	-- All should succeed
	for _, result in pairs(results) do
		luaunit.assertTrue(result.ok)
	end

	local summaries, _ = memory_store_v2:query("char_1", "memory.summaries", {})
	local digests, _ = memory_store_v2:query("char_1", "memory.digests", {})

	luaunit.assertEquals(#summaries, 0)
	luaunit.assertEquals(#digests, 1)
end

------------------------------------------------------------
-- Tests: Error Handling
------------------------------------------------------------

function testMutationMissingCharacterId()
	memory_store_v2:clear()
	local mutations = {
		{
			id = "err_test",
			op = "append",
			resource = "memory.events",
			params = {},
			data = {},
		},
	}

	local results = handle_batch_mutation(mutations)

	luaunit.assertFalse(results.err_test.ok)
	luaunit.assertNotNil(results.err_test.error)
end

function testMutationUnknownResource()
	memory_store_v2:clear()
	local mutations = {
		{
			id = "err_test",
			op = "append",
			resource = "memory.nonexistent",
			params = { character_id = "char_1" },
			data = {},
		},
	}

	local results = handle_batch_mutation(mutations)

	luaunit.assertFalse(results.err_test.ok)
	luaunit.assertNotNil(results.err_test.error)
end

function testMutationUnknownOp()
	memory_store_v2:clear()
	local mutations = {
		{
			id = "err_test",
			op = "invalid_op",
			resource = "memory.events",
			params = { character_id = "char_1" },
			data = {},
		},
	}

	local results = handle_batch_mutation(mutations)

	luaunit.assertFalse(results.err_test.ok)
	luaunit.assertNotNil(results.err_test.error)
end

------------------------------------------------------------
-- Tests: Partial Failure (Mixed Success/Error)
------------------------------------------------------------

function testPartialFailureInBatch()
	memory_store_v2:clear()
	local mutations = {
		{
			id = "success_1",
			op = "append",
			resource = "memory.events",
			params = { character_id = "char_1" },
			data = { {
				timestamp = 100,
				type = "idle",
				context = {},
			} },
		},
		{
			id = "fail_unknown_res",
			op = "append",
			resource = "memory.nonexistent",
			params = { character_id = "char_1" },
			data = {},
		},
		{
			id = "success_2",
			op = "append",
			resource = "memory.events",
			params = { character_id = "char_1" },
			data = { {
				timestamp = 200,
				type = "idle",
				context = {},
			} },
		},
	}

	local results = handle_batch_mutation(mutations)

	-- First and third should succeed
	luaunit.assertTrue(results.success_1.ok)
	luaunit.assertTrue(results.success_2.ok)

	-- Second should fail
	luaunit.assertFalse(results.fail_unknown_res.ok)

	-- Data should still be written
	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 2)
end

------------------------------------------------------------
-- Tests: Stale ID Handling (Idempotency)
------------------------------------------------------------

function testDeleteWithStaleIds()
	memory_store_v2:clear()
	-- Populate with 3 events (ts = game_time_ms = i*100)
	for i = 1, 3 do
		memory_store_v2:store_event("char_1", Event.create(EventType.IDLE, {}, i * 100))
	end

	-- Delete with some stale IDs (999, 50000 don't exist as ts values)
	local mutations = {
		{
			id = "del_stale",
			op = "delete",
			resource = "memory.events",
			params = { character_id = "char_1" },
			ids = { 100, 999, 200, 50000, 300 },
		},
	}

	local results = handle_batch_mutation(mutations)

	-- Should still succeed (stale IDs are silently skipped)
	luaunit.assertTrue(results.del_stale.ok)

	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 0) -- All valid IDs removed
end

------------------------------------------------------------
-- Tests: Concurrent Characters
------------------------------------------------------------

function testMutationsAcrossMultipleCharacters()
	memory_store_v2:clear()
	local mutations = {
		{
			id = "char1_append",
			op = "append",
			resource = "memory.events",
			params = { character_id = "char_1" },
			data = { {
				timestamp = 100,
				type = "idle",
				context = {},
			} },
		},
		{
			id = "char2_append",
			op = "append",
			resource = "memory.events",
			params = { character_id = "char_2" },
			data = { {
				timestamp = 200,
				type = "idle",
				context = {},
			} },
		},
		{
			id = "char1_set_bg",
			op = "set",
			resource = "memory.background",
			params = { character_id = "char_1" },
			data = {
				traits = { "brave" },
				backstory = "Hero",
				connections = {},
			},
		},
	}

	local results = handle_batch_mutation(mutations)

	-- All should succeed independently
	luaunit.assertTrue(results.char1_append.ok)
	luaunit.assertTrue(results.char2_append.ok)
	luaunit.assertTrue(results.char1_set_bg.ok)

	-- Verify separate storage
	local c1_events, _ = memory_store_v2:query("char_1", "memory.events", {})
	local c2_events, _ = memory_store_v2:query("char_2", "memory.events", {})
	local c1_bg, _ = memory_store_v2:query("char_1", "memory.background", {})

	luaunit.assertEquals(#c1_events, 1)
	luaunit.assertEquals(#c2_events, 1)
	luaunit.assertNotNil(c1_bg)
end

-- Run all tests
os.exit(luaunit.LuaUnit.run())

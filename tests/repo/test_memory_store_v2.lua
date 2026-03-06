-- tests/repo/test_memory_store_v2.lua
-- Comprehensive tests for the four-tier memory storage system
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local memory_store = require("domain.repo.memory_store_v2")
local Event = require("domain.model.event")
local EventType = require("domain.model.event_types")

local function setup()
	memory_store:clear()
end

------------------------------------------------------------
-- Helper: Create mock event
------------------------------------------------------------

local function mock_event(game_time_ms, event_type, context)
	return Event.create(event_type or EventType.IDLE, context or {}, game_time_ms)
end

local function mock_character(game_id, name)
	return { game_id = game_id, name = name }
end

------------------------------------------------------------
-- Tests: Per-NPC Entry Structure (Requirement 1)
------------------------------------------------------------

function testNewMemoryEntryHasAllFiveFields()
	memory_store:clear()
	local entry = memory_store:ensure_entry("char_1")

	luaunit.assertNotNil(entry)
	luaunit.assertNotNil(entry.events)
	luaunit.assertNotNil(entry.summaries)
	luaunit.assertNotNil(entry.digests)
	luaunit.assertNotNil(entry.cores)
	luaunit.assertNil(entry.background)
	luaunit.assertEquals(#entry.events, 0)
	luaunit.assertEquals(#entry.summaries, 0)
	luaunit.assertEquals(#entry.digests, 0)
	luaunit.assertEquals(#entry.cores, 0)
end

function testSeqNumbersMonotonicallyIncreasing()
	memory_store:clear()
	local event1 = mock_event(100, EventType.IDLE, {})
	local event2 = mock_event(200, EventType.IDLE, {})
	local event3 = mock_event(300, EventType.IDLE, {})

	local stored1 = memory_store:store_event("char_1", event1)
	local stored2 = memory_store:store_event("char_1", event2)
	local stored3 = memory_store:store_event("char_1", event3)

	luaunit.assertNotNil(stored1.ts)
	luaunit.assertNotNil(stored2.ts)
	luaunit.assertNotNil(stored3.ts)
	-- ts values should be monotonically increasing
	luaunit.assertTrue(stored1.ts < stored2.ts)
	luaunit.assertTrue(stored2.ts < stored3.ts)
end

------------------------------------------------------------
-- Tests: Event Tier Storage (Requirement 2)
------------------------------------------------------------

function testEventStoredWithoutTextField()
	memory_store:clear()
	local context = { actor = { game_id = 1, name = "Wolf" } }
	local event = mock_event(100, EventType.IDLE, context)

	local stored = memory_store:store_event("char_1", event)

	luaunit.assertNotNil(stored.ts)
	luaunit.assertEquals(stored.timestamp, 100)
	luaunit.assertEquals(stored.type, EventType.IDLE)
	luaunit.assertNotNil(stored.context)
	luaunit.assertNil(stored.text) -- No text field
	luaunit.assertNil(stored.seq) -- No seq field (replaced by ts)
end

function testContextContainsCharacterReferences()
	memory_store:clear()
	local context = {
		victim = { game_id = 1, name = "Victim" },
		killer = { game_id = 2, name = "Killer" },
	}
	local event = mock_event(100, EventType.DEATH, context)

	local stored = memory_store:store_event("char_1", event)

	luaunit.assertEquals(stored.context.victim.game_id, 1)
	luaunit.assertEquals(stored.context.killer.game_id, 2)
end

------------------------------------------------------------
-- Tests: Compressed Tier Storage (Requirement 3)
------------------------------------------------------------

function testSummaryEntryStructure()
	memory_store:clear()
	local summary = {
		tier = "summary",
		start_ts = 200,
		end_ts = 380,
		text = "Wolf witnessed...",
		source_count = 10,
	}

	local _, err = memory_store:mutate({
		op = "append",
		resource = "memory.summaries",
		params = { character_id = "char_1" },
		data = { summary },
	})
	luaunit.assertNil(err)

	local summaries, _ = memory_store:query("char_1", "memory.summaries", {})
	luaunit.assertEquals(#summaries, 1)
	luaunit.assertNotNil(summaries[1].ts)
	luaunit.assertEquals(summaries[1].tier, "summary")
	luaunit.assertEquals(summaries[1].start_ts, 200)
	luaunit.assertEquals(summaries[1].end_ts, 380)
	luaunit.assertEquals(summaries[1].text, "Wolf witnessed...")
	luaunit.assertEquals(summaries[1].source_count, 10)
end

function testCoreEntryIsSelfDescribing()
	memory_store:clear()
	local core = {
		tier = "core",
		start_ts = 0,
		end_ts = 1000,
		text = "Old narrative blob",
		source_count = 0,
	}

	memory_store:mutate({
		op = "append",
		resource = "memory.cores",
		params = { character_id = "char_1" },
		data = { core },
	})

	local cores, _ = memory_store:query("char_1", "memory.cores", {})
	luaunit.assertEquals(cores[1].tier, "core")
	luaunit.assertEquals(cores[1].source_count, 0)
end

------------------------------------------------------------
-- Tests: Tier Caps with Oldest-Eviction (Requirement 4)
------------------------------------------------------------

function testEventsCapEnforced()
	memory_store:clear()
	-- CAPS.events = 100, so 101 events should trigger eviction
	for i = 1, 101 do
		memory_store:store_event("char_1", mock_event(i * 100, EventType.IDLE, {}))
	end

	local events, _ = memory_store:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 100)
	-- Oldest event was evicted (first stored ts); remaining should have ascending ts
	luaunit.assertTrue(events[1].ts < events[100].ts)
end

function testSummaryCapEnforced()
	memory_store:clear()
	-- CAPS.summaries = 10, so 11 should trigger eviction
	for i = 1, 11 do
		memory_store:mutate({
			op = "append",
			resource = "memory.summaries",
			params = { character_id = "char_1" },
			data = { {
				tier = "summary",
				start_ts = i * 100,
				end_ts = i * 100 + 50,
				text = "Summary " .. i,
				source_count = 10,
			} },
		})
	end

	local summaries, _ = memory_store:query("char_1", "memory.summaries", {})
	luaunit.assertEquals(#summaries, 10)
	-- Oldest summary was evicted; remaining should have ascending ts
	luaunit.assertTrue(summaries[1].ts < summaries[10].ts)
end

------------------------------------------------------------
-- Tests: Background Entity (Requirement 5)
------------------------------------------------------------

function testBackgroundInitiallyNil()
	memory_store:clear()
	local bg, _ = memory_store:query("char_1", "memory.background", {})
	luaunit.assertNil(bg)
end

function testBackgroundSetViaSet()
	memory_store:clear()
	local background = {
		traits = { "gruff", "protective" },
		backstory = "Veteran stalker",
		connections = {
			{ character_id = "char_2", name = "Fanatic", relation = "mentored" },
		},
	}

	local result = memory_store:mutate({
		op = "set",
		resource = "memory.background",
		params = { character_id = "char_1" },
		data = background,
	})
	luaunit.assertTrue(result.ok)

	local retrieved_bg, _ = memory_store:query("char_1", "memory.background", {})
	luaunit.assertEquals(retrieved_bg.traits[1], "gruff")
	luaunit.assertEquals(retrieved_bg.backstory, "Veteran stalker")
	luaunit.assertEquals(#retrieved_bg.connections, 1)
end

function testBackgroundTraitsUpdated()
	memory_store:clear()
	memory_store:mutate({
		op = "set",
		resource = "memory.background",
		params = { character_id = "char_1" },
		data = {
			traits = { "jovial", "carefree" },
			backstory = "",
			connections = {},
		},
	})

	local result = memory_store:mutate({
		op = "update",
		resource = "memory.background",
		params = { character_id = "char_1" },
		ops = {
			["$push"] = { traits = "haunted" },
			["$pull"] = { traits = "carefree" },
		},
	})
	luaunit.assertTrue(result.ok)

	local bg, _ = memory_store:query("char_1", "memory.background", {})
	-- Should have: jovial, haunted (carefree removed)
	luaunit.assertEquals(#bg.traits, 2)
	local has_haunted = false
	for _, t in ipairs(bg.traits) do
		if t == "haunted" then has_haunted = true end
	end
	luaunit.assertTrue(has_haunted)
end

------------------------------------------------------------
-- Tests: Unified Store DSL (Requirement 6)
------------------------------------------------------------

function testAppendAddsItemsWithNewTs()
	memory_store:clear()
	local event1 = { timestamp = 100, type = "idle", context = {} }
	local event2 = { timestamp = 200, type = "idle", context = {} }

	local result = memory_store:mutate({
		op = "append",
		resource = "memory.events",
		params = { character_id = "char_1" },
		data = { event1, event2 },
	})
	luaunit.assertTrue(result.ok)

	local events, _ = memory_store:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 2)
	luaunit.assertNotNil(events[1].ts)
	luaunit.assertNotNil(events[2].ts)
	luaunit.assertTrue(events[1].ts < events[2].ts)
end

function testDeleteRemovesItemsByTs()
	memory_store:clear()
	local stored_ts = {}
	for i = 1, 5 do
		local stored = memory_store:store_event("char_1", mock_event(i * 100, EventType.IDLE, {}))
		stored_ts[i] = stored.ts
	end

	local result = memory_store:mutate({
		op = "delete",
		resource = "memory.events",
		params = { character_id = "char_1" },
		ids = { stored_ts[1], stored_ts[2], stored_ts[3] },
	})
	luaunit.assertTrue(result.ok)

	local events, _ = memory_store:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 2)
	luaunit.assertEquals(events[1].ts, stored_ts[4])
	luaunit.assertEquals(events[2].ts, stored_ts[5])
end

function testDeleteWithNonExistentTsSilentlySkipped()
	memory_store:clear()
	local stored1 = memory_store:store_event("char_1", mock_event(100, EventType.IDLE, {}))
	local stored2 = memory_store:store_event("char_1", mock_event(200, EventType.IDLE, {}))

	local result = memory_store:mutate({
		op = "delete",
		resource = "memory.events",
		params = { character_id = "char_1" },
		ids = { stored1.ts, 999999, stored2.ts }, -- 999999 doesn't exist
	})
	luaunit.assertTrue(result.ok)

	local events, _ = memory_store:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 0)
end

function testSetReplacesEntireResource()
	memory_store:clear()
	local bg1 = { traits = { "old" }, backstory = "old", connections = {} }
	memory_store:mutate({
		op = "set",
		resource = "memory.background",
		params = { character_id = "char_1" },
		data = bg1,
	})

	local bg2 = { traits = { "new" }, backstory = "new", connections = {} }
	memory_store:mutate({
		op = "set",
		resource = "memory.background",
		params = { character_id = "char_1" },
		data = bg2,
	})

	local bg, _ = memory_store:query("char_1", "memory.background", {})
	luaunit.assertEquals(bg.traits[1], "new")
end

function testUpdateAppliesPartialOperators()
	memory_store:clear()
	memory_store:mutate({
		op = "set",
		resource = "memory.background",
		params = { character_id = "char_1" },
		data = { traits = { "a", "b", "c" }, backstory = "", connections = {} },
	})

	memory_store:mutate({
		op = "update",
		resource = "memory.background",
		params = { character_id = "char_1" },
		ops = {
			["$push"] = { traits = "d" },
			["$pull"] = { traits = "b" },
		},
	})

	local bg, _ = memory_store:query("char_1", "memory.background", {})
	luaunit.assertEquals(#bg.traits, 3) -- a, c, d
	local found_d = false
	for _, t in ipairs(bg.traits) do
		if t == "d" then found_d = true end
	end
	luaunit.assertTrue(found_d)
end

function testQueryReturnsAllItemsForResource()
	memory_store:clear()
	memory_store:store_event("char_1", mock_event(100, EventType.IDLE, {}))
	memory_store:store_event("char_1", mock_event(200, EventType.IDLE, {}))
	memory_store:store_event("char_1", mock_event(300, EventType.IDLE, {}))

	local events, _ = memory_store:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 3)
end

function testQueryWithTimestampFilter()
	memory_store:clear()
	memory_store:store_event("char_1", mock_event(100, EventType.IDLE, {}))
	memory_store:store_event("char_1", mock_event(200, EventType.IDLE, {}))
	memory_store:store_event("char_1", mock_event(300, EventType.IDLE, {}))

	local events, _ = memory_store:query("char_1", "memory.events", { from_timestamp = 200 })
	luaunit.assertEquals(#events, 2) -- 200 and 300
	luaunit.assertEquals(events[1].timestamp, 200)
	luaunit.assertEquals(events[2].timestamp, 300)
end

function testQueryEmptyCharacterReturnsEmptyList()
	memory_store:clear()
	local events, _ = memory_store:query("nonexistent", "memory.events", {})
	luaunit.assertEquals(#events, 0)
end

function testQueryNilBackgroundReturnsNilNotError()
	memory_store:clear()
	local bg, err = memory_store:query("nonexistent", "memory.background", {})
	luaunit.assertNil(bg)
	luaunit.assertNil(err)
end

------------------------------------------------------------
-- Tests: Event Fan-out (Requirement 7)
------------------------------------------------------------

function testFanOutAppendsTowAllWitnesses()
	memory_store:clear()
	local event = mock_event(100, EventType.DEATH, {
		victim = mock_character(1, "Victim"),
		killer = mock_character(2, "Killer"),
	})
	local witnesses = {
		mock_character(3, "Wolf"),
		mock_character(4, "Fanatic"),
	}

	memory_store:fan_out(event, witnesses)

	local events_3, _ = memory_store:query("3", "memory.events", {})
	local events_4, _ = memory_store:query("4", "memory.events", {})

	luaunit.assertEquals(#events_3, 1)
	luaunit.assertEquals(#events_4, 1)
	luaunit.assertEquals(events_3[1].type, EventType.DEATH)
	luaunit.assertEquals(events_4[1].type, EventType.DEATH)
end

function testFanOutCreatesNewMemoryEntries()
	memory_store:clear()
	local event = mock_event(100, EventType.IDLE, {})
	local witnesses = {
		mock_character(1, "NPC1"),
		mock_character(2, "NPC2"),
	}

	memory_store:fan_out(event, witnesses)

	local entry1 = memory_store:get_entry("1")
	local entry2 = memory_store:get_entry("2")

	luaunit.assertNotNil(entry1)
	luaunit.assertNotNil(entry2)
	luaunit.assertEquals(#entry1.events, 1)
	luaunit.assertEquals(#entry2.events, 1)
end

function testFanOutWithNilWitnesses()
	memory_store:clear()
	local event = mock_event(100, EventType.IDLE, {})
	-- Should not crash
	memory_store:fan_out(event, nil)
	luaunit.assertTrue(true)
end

------------------------------------------------------------
-- Tests: Global Event Buffer (Requirement 8)
------------------------------------------------------------

function testGlobalEventStoredInBuffer()
	memory_store:clear()
	local event = mock_event(100, EventType.EMISSION, {
		emission_type = "psy_storm",
		status = "starting",
	})

	memory_store:store_global_event(event)

	local buffer = memory_store:get_global_event_buffer()
	luaunit.assertEquals(#buffer, 1)
	luaunit.assertEquals(buffer[1].type, EventType.EMISSION)
end

function testGlobalEventWrittenToExistingCharacters()
	memory_store:clear()
	-- Create some existing characters
	memory_store:ensure_entry("char_1")
	memory_store:ensure_entry("char_2")

	local event = mock_event(100, EventType.EMISSION, { emission_type = "psy_storm", status = "starting" })
	memory_store:store_global_event(event)

	local events_1, _ = memory_store:query("char_1", "memory.events", {})
	local events_2, _ = memory_store:query("char_2", "memory.events", {})

	luaunit.assertEquals(#events_1, 1)
	luaunit.assertEquals(#events_2, 1)
end

function testGlobalBufferRespectsCap()
	memory_store:clear()
	-- CAPS.global_events = 30
	for i = 1, 31 do
		local event = mock_event(i * 100, EventType.EMISSION, {})
		memory_store:store_global_event(event)
	end

	local buffer = memory_store:get_global_event_buffer()
	luaunit.assertEquals(#buffer, 30)
end

function testBackfillOnFirstContact()
	memory_store:clear()
	-- Pre-populate buffer with 3 global events
	for i = 1, 3 do
		local event = mock_event(i * 100, EventType.EMISSION, { status = "starting" })
		memory_store:store_global_event(event)
	end

	-- Ensure a new character (backfill happens)
	local entry = memory_store:ensure_entry("new_char")

	-- Should have 3 backfilled global events
	local events, _ = memory_store:query("new_char", "memory.events", {})
	luaunit.assertEquals(#events, 3)
end

------------------------------------------------------------
-- Tests: Save and Load Persistence (Requirement 9)
------------------------------------------------------------

function testSaveDataFormatContainsVersion()
	memory_store:clear()
	memory_store:store_event("char_1", mock_event(100, EventType.IDLE, {}))

	local save_data = memory_store:get_save_data()

	luaunit.assertNotNil(save_data.memories_version)
	luaunit.assertEquals(save_data.memories_version, "4")
	luaunit.assertNotNil(save_data.memories)
	luaunit.assertNotNil(save_data.global_events)
	-- v4: no next_seq in saved data
	for _, entry in pairs(save_data.memories) do
		luaunit.assertNil(entry.next_seq)
	end
end

function testLoadV3SaveData()
	memory_store:clear()
	-- Simulate loading a v3 save (has seq fields, next_seq)
	local v3_save = {
		memories_version = "3",
		memories = {
			char_1 = {
				events = {
					{ seq = 1, timestamp = 100, type = "idle", context = {} },
					{ seq = 2, timestamp = 200, type = "idle", context = {} },
				},
				summaries = {},
				digests = {},
				cores = {},
				background = nil,
				next_seq = 3,
			},
		},
		global_events = {},
	}

	memory_store:load_save_data(v3_save)

	local events, _ = memory_store:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 2)
	-- Migrated: should have ts fields, no seq
	luaunit.assertNotNil(events[1].ts)
	luaunit.assertNotNil(events[2].ts)
	luaunit.assertTrue(events[1].ts < events[2].ts)
	-- entry should NOT have next_seq
	local entry = memory_store:get_entry("char_1")
	luaunit.assertNil(entry.next_seq)
end

function testLoadV3SaveDataCollisionHandling()
	memory_store:clear()
	-- Two events with same timestamp in v3 save
	local v3_save = {
		memories_version = "3",
		memories = {
			char_1 = {
				events = {
					{ seq = 1, timestamp = 500, type = "death", context = {} },
					{ seq = 2, timestamp = 500, type = "idle", context = {} },
				},
				summaries = {},
				digests = {},
				cores = {},
				background = nil,
				next_seq = 3,
			},
		},
		global_events = {},
	}

	memory_store:load_save_data(v3_save)

	local events, _ = memory_store:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 2)
	-- Both should have unique ts values
	luaunit.assertNotEquals(events[1].ts, events[2].ts)
end

function testLoadV3SaveDataWithCompressedTiers()
	memory_store:clear()
	local v3_save = {
		memories_version = "3",
		memories = {
			char_1 = {
				events = {},
				summaries = {
					{ seq = 1, tier = "summary", start_ts = 100, end_ts = 200, text = "test", source_count = 2 },
				},
				digests = {},
				cores = {},
				background = nil,
				next_seq = 2,
			},
		},
		global_events = {},
	}

	memory_store:load_save_data(v3_save)

	local summaries, _ = memory_store:query("char_1", "memory.summaries", {})
	luaunit.assertEquals(#summaries, 1)
	luaunit.assertNotNil(summaries[1].ts)
	luaunit.assertNil(summaries[1].seq) -- seq field removed
	luaunit.assertEquals(summaries[1].text, "test")
end

function testV4SaveLoadRoundtrip()
	memory_store:clear()
	memory_store:store_event("char_1", mock_event(100, EventType.IDLE, {}))
	memory_store:store_event("char_1", mock_event(200, EventType.DEATH, {}))

	local save_data = memory_store:get_save_data()
	luaunit.assertEquals(save_data.memories_version, "4")

	memory_store:clear()
	memory_store:load_save_data(save_data)

	local events, _ = memory_store:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 2)
	luaunit.assertNotNil(events[1].ts)
	luaunit.assertNotNil(events[2].ts)
end

function testLoadV2SaveDataMigratesNarrativeToCore()
	memory_store:clear()
	local v2_save = {
		memories_version = "2",
		memories = {
			char_1 = {
				narrative = "This is the old narrative",
				last_update_time_ms = 5000,
			},
		},
	}

	memory_store:load_save_data(v2_save)

	local cores, _ = memory_store:query("char_1", "memory.cores", {})
	luaunit.assertEquals(#cores, 1)
	luaunit.assertEquals(cores[1].tier, "core")
	luaunit.assertEquals(cores[1].text, "This is the old narrative")
	luaunit.assertEquals(cores[1].end_ts, 5000)
	luaunit.assertEquals(cores[1].source_count, 0)
end

function testLoadV1SaveDataMigratesCorrectly()
	memory_store:clear()
	-- v1 unversioned: direct table of char_id → data
	local v1_save = {
		char_1 = {
			narrative = "Old v1 narrative",
			last_update_time_ms = 3000,
		},
	}

	memory_store:load_save_data(v1_save)

	local cores, _ = memory_store:query("char_1", "memory.cores", {})
	luaunit.assertEquals(#cores, 1)
	luaunit.assertEquals(cores[1].text, "Old v1 narrative")
end

function testLoadNilStartsFresh()
	memory_store:clear()
	memory_store:store_event("char_1", mock_event(100, EventType.IDLE, {}))

	memory_store:load_save_data(nil)

	local events, _ = memory_store:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 0)
end

function testLoadEmptySave()
	memory_store:clear()
	local save = { memories_version = "4", memories = {}, global_events = {} }

	memory_store:load_save_data(save)

	local ids = memory_store:get_all_character_ids()
	luaunit.assertEquals(#ids, 0)
end

function testLoadUnknownVersionStartsFresh()
	memory_store:clear()
	local unknown_save = {
		memories_version = "999",
		memories = { char_1 = {} },
	}

	memory_store:load_save_data(unknown_save)

	local ids = memory_store:get_all_character_ids()
	luaunit.assertEquals(#ids, 0)
end

------------------------------------------------------------
-- Tests: Inspection/Accessors
------------------------------------------------------------

function testGetEntryReturnsNilForNonexistent()
	memory_store:clear()
	local entry = memory_store:get_entry("nonexistent")
	luaunit.assertNil(entry)
end

function testGetAllCharacterIds()
	memory_store:clear()
	memory_store:ensure_entry("char_1")
	memory_store:ensure_entry("char_2")
	memory_store:ensure_entry("char_3")

	local ids = memory_store:get_all_character_ids()
	luaunit.assertEquals(#ids, 3)
end

function testGetTierCounts()
	memory_store:clear()
	memory_store:store_event("char_1", mock_event(100, EventType.IDLE, {}))
	memory_store:store_event("char_1", mock_event(200, EventType.IDLE, {}))

	memory_store:mutate({
		op = "append",
		resource = "memory.summaries",
		params = { character_id = "char_1" },
		data = { {
			tier = "summary",
			start_ts = 100,
			end_ts = 200,
			text = "",
			source_count = 2,
		} },
	})

	local counts = memory_store:get_tier_counts("char_1")
	luaunit.assertEquals(counts.events, 2)
	luaunit.assertEquals(counts.summaries, 1)
	luaunit.assertEquals(counts.digests, 0)
	luaunit.assertEquals(counts.cores, 0)
end

------------------------------------------------------------
-- Tests: Error Handling
------------------------------------------------------------

function testMutateWithMissingCharacterId()
	memory_store:clear()
	local result = memory_store:mutate({
		op = "append",
		resource = "memory.events",
		params = {},
		data = {},
	})
	luaunit.assertFalse(result.ok)
	luaunit.assertNotNil(result.error)
end

function testMutateWithUnknownResource()
	memory_store:clear()
	local result = memory_store:mutate({
		op = "append",
		resource = "memory.unknown",
		params = { character_id = "char_1" },
		data = {},
	})
	luaunit.assertFalse(result.ok)
end

function testMutateWithUnknownOp()
	memory_store:clear()
	local result = memory_store:mutate({
		op = "invalid_op",
		resource = "memory.events",
		params = { character_id = "char_1" },
		data = {},
	})
	luaunit.assertFalse(result.ok)
end

function testQueryWithUnknownResource()
	memory_store:clear()
	local data, err = memory_store:query("char_1", "memory.unknown", {})
	luaunit.assertNil(data)
	luaunit.assertNotNil(err)
end

function testAppendNotSupportedForBackground()
	memory_store:clear()
	local result = memory_store:mutate({
		op = "append",
		resource = "memory.background",
		params = { character_id = "char_1" },
		data = { {} },
	})
	luaunit.assertFalse(result.ok)
end

function testSetNotSupportedForEvents()
	memory_store:clear()
	local result = memory_store:mutate({
		op = "set",
		resource = "memory.events",
		params = { character_id = "char_1" },
		data = {},
	})
	luaunit.assertFalse(result.ok)
end

function testUpdateNotSupportedForEvents()
	memory_store:clear()
	local result = memory_store:mutate({
		op = "update",
		resource = "memory.events",
		params = { character_id = "char_1" },
		ops = {},
	})
	luaunit.assertFalse(result.ok)
end

-- Run all tests
os.exit(luaunit.LuaUnit.run())

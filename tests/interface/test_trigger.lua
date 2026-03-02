-- tests/interface/test_trigger.lua
-- Tests for trigger.store_and_publish() function (task 3.1)
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local trigger = require("interface.trigger")
local Event = require("domain.model.event")
local EventType = require("domain.model.event_types")
local memory_store_v2 = require("domain.repo.memory_store_v2")

local function setup()
	memory_store_v2:clear()
end

------------------------------------------------------------
-- Tests: Basic store_and_publish Flow
------------------------------------------------------------

function testStoreAndPublishCreatesEvent()
	setup()
	local context = {
		actor = { game_id = "char_1", name = "Speaker", faction = "stalker" },
		victim = { game_id = "char_2", name = "Victim", faction = "stalker" },
	}
	local witnesses = {}

	local event = trigger.store_and_publish(EventType.DEATH, context, witnesses)

	luaunit.assertNotNil(event)
	luaunit.assertEquals(event.type, EventType.DEATH)
	luaunit.assertNotNil(event.context)
	luaunit.assertEquals(event.context.victim.game_id, "char_2")
end

function testStoreAndPublishStoresInMemory()
	setup()
	local speaker = { game_id = "char_1", name = "Speaker", faction = "stalker" }
	local context = { actor = speaker }

	trigger.store_and_publish(EventType.IDLE, context, {})

	-- Verify event stored in speaker's memory
	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 1)
	luaunit.assertEquals(events[1].type, EventType.IDLE)
end

function testStoreAndPublishFansOutToWitnesses()
	setup()
	local speaker = { game_id = "char_1", name = "Speaker" }
	local witness1 = { game_id = "char_2", name = "Witness1" }
	local witness2 = { game_id = "char_3", name = "Witness2" }
	local context = { actor = speaker, victim = speaker }
	local witnesses = { witness1, witness2 }

	trigger.store_and_publish(EventType.DEATH, context, witnesses)

	-- Verify each witness has the event
	local w1_events, _ = memory_store_v2:query("char_2", "memory.events", {})
	local w2_events, _ = memory_store_v2:query("char_3", "memory.events", {})

	luaunit.assertEquals(#w1_events, 1)
	luaunit.assertEquals(#w2_events, 1)
	luaunit.assertEquals(w1_events[1].type, EventType.DEATH)
end

------------------------------------------------------------
-- Tests: Error Handling
------------------------------------------------------------

function testStoreAndPublishRequiresEventType()
	setup()
	local context = { actor = { game_id = "char_1" } }

	local result = trigger.store_and_publish(nil, context, {})

	luaunit.assertNil(result)
end

function testStoreAndPublishRequiresSpeaker()
	setup()
	local context = {} -- No actor

	local result = trigger.store_and_publish(EventType.DEATH, context, {})

	luaunit.assertNil(result)
end

function testStoreAndPublishRequiresSpeakerId()
	setup()
	local context = { actor = { name = "No ID" } } -- Missing game_id

	local result = trigger.store_and_publish(EventType.DEATH, context, {})

	luaunit.assertNil(result)
end

------------------------------------------------------------
-- Tests: Event Type and Flags
------------------------------------------------------------

function testStoreAndPublishPreservesEventType()
	setup()
	local speaker = { game_id = "char_1" }
	for event_type_key, event_type_val in pairs(EventType) do
		if type(event_type_val) == "number" then
			local context = { actor = speaker }
			local event = trigger.store_and_publish(event_type_val, context, {})
			luaunit.assertEquals(event.type, event_type_val)
			setup() -- Clear for next iteration
		end
	end
end

function testStoreAndPublishPreservesFlags()
	setup()
	local speaker = { game_id = "char_1" }
	local context = { actor = speaker }
	local flags = { is_silent = true, special_flag = "value" }

	local event = trigger.store_and_publish(EventType.DEATH, context, {}, flags)

	luaunit.assertEquals(event.flags.is_silent, true)
	luaunit.assertEquals(event.flags.special_flag, "value")
end

------------------------------------------------------------
-- Tests: Sequence Numbers and Ordering
------------------------------------------------------------

function testStoreAndPublishAssignsSequentialSeqs()
	setup()
	local speaker = { game_id = "char_1" }
	local context = { actor = speaker }

	trigger.store_and_publish(EventType.DEATH, context, {})
	trigger.store_and_publish(EventType.IDLE, context, {})
	trigger.store_and_publish(EventType.ARTIFACT, context, {})

	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 3)
	luaunit.assertEquals(events[1].seq, 1)
	luaunit.assertEquals(events[2].seq, 2)
	luaunit.assertEquals(events[3].seq, 3)
end

------------------------------------------------------------
-- Tests: Complex Context
------------------------------------------------------------

function testStoreAndPublishComplexContext()
	setup()
	local speaker = { game_id = "char_1", name = "Killer", faction = "stalker" }
	local victim = { game_id = "char_2", name = "Victim", faction = "loner" }
	local companion = { game_id = "char_3", name = "Companion", faction = "stalker" }
	local context = {
		actor = speaker,
		victim = victim,
		companions = { companion },
	}

	local event = trigger.store_and_publish(EventType.DEATH, context, {})

	luaunit.assertEquals(event.context.actor.name, "Killer")
	luaunit.assertEquals(event.context.victim.name, "Victim")
	luaunit.assertEquals(#event.context.companions, 1)
	luaunit.assertEquals(event.context.companions[1].name, "Companion")
end

------------------------------------------------------------
-- Tests: Timestamp Assignment
------------------------------------------------------------

function testStoreAndPublishAssignsTimestamp()
	setup()
	local speaker = { game_id = "char_1" }
	local context = { actor = speaker }

	local event = trigger.store_and_publish(EventType.DEATH, context, {})

	luaunit.assertTrue(event.game_time_ms >= 0)
end

-- Run all tests
os.exit(luaunit.LuaUnit.run())

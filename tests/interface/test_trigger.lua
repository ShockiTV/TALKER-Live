-- tests/interface/test_trigger.lua
-- Tests for trigger.store_event() and trigger.publish_event() (consolidated trigger API)
package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require("tests.utils.luaunit")
local trigger = require("interface.trigger")
local Event = require("domain.model.event")
local EventType = require("domain.model.event_types")
local memory_store_v2 = require("domain.repo.memory_store_v2")
local publisher = require("infra.ws.publisher")

local published_messages = {}

local function install_publish_spy()
	publisher.send_game_event = function(event, candidates, world, traits)
		published_messages[#published_messages + 1] = {
			event = event,
			candidates = candidates,
			world = world,
			traits = traits,
		}
	end
end

local function setup()
	memory_store_v2:clear()
	published_messages = {}
	install_publish_spy()
end

-- ══════════════════════════════════════════════════════════
-- store_event: Memory Only (no WS publish)
-- ══════════════════════════════════════════════════════════

function testStoreEventCreatesEvent()
	setup()
	local context = {
		actor = { game_id = "char_1", name = "Speaker", faction = "stalker" },
		victim = { game_id = "char_2", name = "Victim", faction = "stalker" },
	}

	local event = trigger.store_event(EventType.DEATH, context, {})

	luaunit.assertNotNil(event)
	luaunit.assertEquals(event.type, EventType.DEATH)
	luaunit.assertNotNil(event.context)
	luaunit.assertEquals(event.context.victim.game_id, "char_2")
end

function testStoreEventStoresInMemory()
	setup()
	local speaker = { game_id = "char_1", name = "Speaker", faction = "stalker" }
	local context = { actor = speaker }

	trigger.store_event(EventType.IDLE, context, {})

	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 1)
	luaunit.assertEquals(events[1].type, EventType.IDLE)
end

function testStoreEventFansOutToWitnesses()
	setup()
	local speaker = { game_id = "char_1", name = "Speaker" }
	local witness1 = { game_id = "char_2", name = "Witness1" }
	local witness2 = { game_id = "char_3", name = "Witness2" }
	local context = { actor = speaker, victim = speaker }

	trigger.store_event(EventType.DEATH, context, { witness1, witness2 })

	local w1_events, _ = memory_store_v2:query("char_2", "memory.events", {})
	local w2_events, _ = memory_store_v2:query("char_3", "memory.events", {})
	luaunit.assertEquals(#w1_events, 1)
	luaunit.assertEquals(#w2_events, 1)
	luaunit.assertEquals(w1_events[1].type, EventType.DEATH)
end

function testStoreEventSetsIndexOnlyFlag()
	setup()
	local speaker = { game_id = "char_1" }
	local context = { actor = speaker }

	local event = trigger.store_event(EventType.DEATH, context, {})

	-- store_event is index-only for realtime Neo4j ingest
	luaunit.assertNotNil(event.flags)
	luaunit.assertTrue(event.flags.index_only)
	luaunit.assertEquals(#published_messages, 1)
	luaunit.assertTrue(published_messages[1].event.flags.index_only)
end

-- ══════════════════════════════════════════════════════════
-- publish_event: Memory + WS Publish
-- ══════════════════════════════════════════════════════════

function testPublishEventCreatesEvent()
	setup()
	local context = {
		actor = { game_id = "char_1", name = "Speaker", faction = "stalker" },
		victim = { game_id = "char_2", name = "Victim", faction = "stalker" },
	}

	local event = trigger.publish_event(EventType.DEATH, context, {})

	luaunit.assertNotNil(event)
	luaunit.assertEquals(event.type, EventType.DEATH)
end

function testPublishEventStoresInMemory()
	setup()
	local speaker = { game_id = "char_1", name = "Speaker", faction = "stalker" }
	local context = { actor = speaker }

	trigger.publish_event(EventType.IDLE, context, {})

	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 1)
	luaunit.assertEquals(events[1].type, EventType.IDLE)
end

function testPublishEventDoesNotSetIndexOnlyFlag()
	setup()
	local speaker = { game_id = "char_1", name = "Speaker", faction = "stalker" }
	local context = { actor = speaker }

	local event = trigger.publish_event(EventType.IDLE, context, {})

	luaunit.assertNotNil(event)
	luaunit.assertNotNil(event.flags)
	luaunit.assertNil(event.flags.index_only)
	luaunit.assertEquals(#published_messages, 1)
	luaunit.assertNil(published_messages[1].event.flags.index_only)
end

function testPublishEventFansOutToWitnesses()
	setup()
	local speaker = { game_id = "char_1", name = "Speaker" }
	local witness1 = { game_id = "char_2", name = "Witness1" }
	local witness2 = { game_id = "char_3", name = "Witness2" }
	local context = { actor = speaker, victim = speaker }

	trigger.publish_event(EventType.DEATH, context, { witness1, witness2 })

	local w1_events, _ = memory_store_v2:query("char_2", "memory.events", {})
	local w2_events, _ = memory_store_v2:query("char_3", "memory.events", {})
	luaunit.assertEquals(#w1_events, 1)
	luaunit.assertEquals(#w2_events, 1)
end

-- ══════════════════════════════════════════════════════════
-- Error Handling (shared validation)
-- ══════════════════════════════════════════════════════════

function testStoreEventRequiresEventType()
	setup()
	local context = { actor = { game_id = "char_1" } }
	luaunit.assertNil(trigger.store_event(nil, context, {}))
end

function testStoreEventRequiresSpeaker()
	setup()
	luaunit.assertNil(trigger.store_event(EventType.DEATH, {}, {}))
end

function testStoreEventRequiresSpeakerId()
	setup()
	local context = { actor = { name = "No ID" } }
	luaunit.assertNil(trigger.store_event(EventType.DEATH, context, {}))
end

function testPublishEventRequiresEventType()
	setup()
	local context = { actor = { game_id = "char_1" } }
	luaunit.assertNil(trigger.publish_event(nil, context, {}))
end

function testPublishEventRequiresSpeaker()
	setup()
	luaunit.assertNil(trigger.publish_event(EventType.DEATH, {}, {}))
end

-- ══════════════════════════════════════════════════════════
-- Event Type Preservation
-- ══════════════════════════════════════════════════════════

function testStoreEventPreservesAllEventTypes()
	setup()
	local speaker = { game_id = "char_1" }
	for _, event_type_val in pairs(EventType) do
		if type(event_type_val) == "number" then
			local context = { actor = speaker }
			local event = trigger.store_event(event_type_val, context, {})
			luaunit.assertEquals(event.type, event_type_val)
			setup()
		end
	end
end

-- ══════════════════════════════════════════════════════════
-- Sequence Numbers
-- ══════════════════════════════════════════════════════════

function testStoreEventAssignsSequentialTimestamps()
	setup()
	local speaker = { game_id = "char_1" }
	local context = { actor = speaker }

	trigger.store_event(EventType.DEATH, context, {})
	trigger.store_event(EventType.IDLE, context, {})
	trigger.store_event(EventType.ARTIFACT, context, {})

	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 3)
	-- Events now use unique_ts instead of per-character seq
	luaunit.assertNotNil(events[1].ts)
	luaunit.assertNotNil(events[2].ts)
	luaunit.assertNotNil(events[3].ts)
	-- Timestamps must be strictly ascending
	luaunit.assertTrue(events[1].ts < events[2].ts)
	luaunit.assertTrue(events[2].ts < events[3].ts)
end

function testPublishEventAssignsSequentialTimestamps()
	setup()
	local speaker = { game_id = "char_1" }
	local context = { actor = speaker }

	trigger.publish_event(EventType.DEATH, context, {})
	trigger.publish_event(EventType.IDLE, context, {})

	local events, _ = memory_store_v2:query("char_1", "memory.events", {})
	luaunit.assertEquals(#events, 2)
	-- Events now use unique_ts instead of per-character seq
	luaunit.assertNotNil(events[1].ts)
	luaunit.assertNotNil(events[2].ts)
	luaunit.assertTrue(events[1].ts < events[2].ts)
end

-- ══════════════════════════════════════════════════════════
-- Complex Context
-- ══════════════════════════════════════════════════════════

function testStoreEventComplexContext()
	setup()
	local speaker = { game_id = "char_1", name = "Killer", faction = "stalker" }
	local victim = { game_id = "char_2", name = "Victim", faction = "loner" }
	local companion = { game_id = "char_3", name = "Companion", faction = "stalker" }
	local context = {
		actor = speaker,
		victim = victim,
		companions = { companion },
	}

	local event = trigger.store_event(EventType.DEATH, context, {})

	luaunit.assertEquals(event.context.actor.name, "Killer")
	luaunit.assertEquals(event.context.victim.name, "Victim")
	luaunit.assertEquals(#event.context.companions, 1)
	luaunit.assertEquals(event.context.companions[1].name, "Companion")
end

-- ══════════════════════════════════════════════════════════
-- Timestamp
-- ══════════════════════════════════════════════════════════

function testStoreEventAssignsTimestamp()
	setup()
	local speaker = { game_id = "char_1" }
	local context = { actor = speaker }

	local event = trigger.store_event(EventType.DEATH, context, {})

	luaunit.assertTrue(event.game_time_ms >= 0)
end

-- ══════════════════════════════════════════════════════════
-- store_and_publish is gone
-- ══════════════════════════════════════════════════════════

function testStoreAndPublishRemoved()
	luaunit.assertNil(trigger.store_and_publish)
end

function testTalkerEventNearPlayerRemoved()
	luaunit.assertNil(trigger.talker_event_near_player)
end

function testTalkerEventRemoved()
	luaunit.assertNil(trigger.talker_event)
end

-- Run all tests
os.exit(luaunit.LuaUnit.run())

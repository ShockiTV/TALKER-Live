-- Adjust the package path to ensure LuaUnit and event_store can be required
package.path = package.path .. ';./bin/lua/?.lua'
package.path = package.path .. ';./bin/lua/*/?.lua'

-- Require LuaUnit and the Event module
local luaunit = require('tests.utils.luaunit')
local Event = require('domain.model.event')
local EventType = require('domain.model.event_types')

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Helper to create mock character
local function mock_character(name, game_id, faction, experience)
    return {
        name = name or "TestChar",
        game_id = game_id or "123",
        faction = faction or "stalker",
        experience = experience or "Experienced",
        reputation = "Neutral",
        personality = "calm and collected"  -- Required by Character.describe
    }
end

-- ============================================================================
-- TYPED EVENT TESTS
-- ============================================================================

-- Test was_conversation check (uses source_event field)
function testWasConversation()
    local speaker = mock_character("John", "1")
    local source_event = Event.create(EventType.TAUNT, { actor = speaker }, 8000, "Street", {speaker})
    
    -- Create a dialogue event as a response (with source_event reference)
    local conversation = Event.create(EventType.DIALOGUE, { speaker = speaker, text = "Hello!" }, 8001, "Street", {speaker})
    conversation.source_event = source_event  -- This is how dialogue events reference their source
    
    local non_conversation = Event.create(EventType.DIALOGUE, { speaker = speaker, text = "Random comment" }, 8002, "Street", {speaker})

    luaunit.assertTrue(Event.was_conversation(conversation))
    luaunit.assertFalse(Event.was_conversation(non_conversation))
end

-- Test was_witnessed_by function
function testWasWitnessedBy()
    local witness1 = mock_character("Witness1", "1")
    local witness2 = mock_character("Witness2", "2")
    local actor = mock_character("Actor", "3")
    
    local event = Event.create(EventType.INJURY, { actor = actor }, 1000, "Forest", {witness1, witness2})

    luaunit.assertTrue(Event.was_witnessed_by(event, "1"))
    luaunit.assertTrue(Event.was_witnessed_by(event, "2"))
    luaunit.assertFalse(Event.was_witnessed_by(event, "999"))
end

-- Test Typed Event creation
function testTypedEventCreation()
    local actor = mock_character("John", "1")
    local context = { actor = actor }
    local witnesses = { actor }
    
    local event = Event.create(EventType.WEAPON_JAM, context, 1000, "Forest", witnesses)
    
    luaunit.assertNotNil(event)
    luaunit.assertEquals(event.type, EventType.WEAPON_JAM)
    luaunit.assertNotNil(event.context)
    luaunit.assertEquals(event.context.actor.name, "John")
    luaunit.assertEquals(event.game_time_ms, 1000)
    luaunit.assertEquals(event.world_context, "Forest")
    luaunit.assertEquals(#event.witnesses, 1)
end

-- Test Typed Event with flags
function testTypedEventWithFlags()
    local actor = mock_character("Jane", "2")
    local context = { actor = actor }
    local flags = { is_silent = true }
    
    local event = Event.create(EventType.INJURY, context, 2000, "Swamp", {actor}, flags)
    
    luaunit.assertNotNil(event.flags)
    luaunit.assertTrue(event.flags.is_silent)
end

-- Test Event.describe() for DEATH event
function testTypedEventDescribeDeath()
    local victim = mock_character("Victim", "1", "Bandit", "Novice")
    local killer = mock_character("Killer", "2", "stalker", "Veteran")
    local context = { victim = victim, killer = killer }
    
    local event = Event.create(EventType.DEATH, context, 1000, "Garbage", {killer})
    local description = Event.describe(event)
    
    luaunit.assertStrContains(description, "killed")
    luaunit.assertStrContains(description, "Victim")
end

-- Test Event.describe() for DIALOGUE event
function testTypedEventDescribeDialogue()
    local speaker = mock_character("Speaker", "1")
    local context = { speaker = speaker, text = "Hello there!" }
    
    local event = Event.create(EventType.DIALOGUE, context, 1000, "Bar", {speaker})
    local description = Event.describe(event)
    
    luaunit.assertStrContains(description, "said:")
    luaunit.assertStrContains(description, "Hello there!")
end

-- Test Event.describe() for whisper DIALOGUE event
function testTypedEventDescribeWhisper()
    local speaker = mock_character("Speaker", "1")
    local context = { speaker = speaker, text = "Secret message", is_whisper = true }
    
    local event = Event.create(EventType.DIALOGUE, context, 1000, "Bar", {speaker})
    local description = Event.describe(event)
    
    luaunit.assertStrContains(description, "whispered")
    luaunit.assertStrContains(description, "Secret message")
end

-- Test Event.describe() for CALLOUT event
function testTypedEventDescribeCallout()
    local spotter = mock_character("Spotter", "1")
    local target = mock_character("Enemy", "2", "Bandit")
    local context = { spotter = spotter, target = target }
    
    local event = Event.create(EventType.CALLOUT, context, 1000, "Cordon", {spotter})
    local description = Event.describe(event)
    
    luaunit.assertStrContains(description, "spotted")
end

-- Test Event.describe() for ARTIFACT event
function testTypedEventDescribeArtifact()
    local actor = mock_character("Stalker", "1")
    local context = { actor = actor, action = "pickup", item_name = "Moonlight" }
    
    local event = Event.create(EventType.ARTIFACT, context, 1000, "Yantar", {actor})
    local description = Event.describe(event)
    
    luaunit.assertStrContains(description, "picked up")
    luaunit.assertStrContains(description, "Moonlight")
end

-- Test Event.describe() for MAP_TRANSITION event
function testTypedEventDescribeMapTransition()
    local actor = mock_character("Traveler", "1")
    local context = { actor = actor, source = "Cordon", destination = "Garbage" }
    
    local event = Event.create(EventType.MAP_TRANSITION, context, 1000, "Garbage", {actor})
    local description = Event.describe(event)
    
    luaunit.assertStrContains(description, "traveled")
    luaunit.assertStrContains(description, "Cordon")
    luaunit.assertStrContains(description, "Garbage")
end

-- Test Event.describe() for EMISSION event
function testTypedEventDescribeEmission()
    local context = { emission_type = "emission", status = "starting" }
    
    local event = Event.create(EventType.EMISSION, context, 1000, "Zone", {})
    local description = Event.describe(event)
    
    luaunit.assertStrContains(description, "Emission")
    luaunit.assertStrContains(description, "starting")
end

-- Test Event.describe() for content-based events (compressed memories)
function testTypedEventDescribeContent()
    local event = {
        content = "This is a compressed memory summary.",
        game_time_ms = 1000,
        flags = { is_compressed = true }
    }
    
    local description = Event.describe(event)
    luaunit.assertEquals(description, "This is a compressed memory summary.")
end

-- Test Event.describe() falls back to description field for legacy/raw events
function testTypedEventDescribeLegacyFallback()
    -- Simulate a legacy event with description field (e.g., from old save data)
    local legacy_event = {
        description = "%s %s %s",
        involved_objects = {"Bob", "ran", "away"},
        game_time_ms = 1000,
        world_context = "Forest",
        witnesses = {}
    }
    local description = Event.describe(legacy_event)
    
    luaunit.assertEquals(description, "Bob ran away")
end

-- Test Event.is_junk_event() for typed events
function testIsJunkEventTyped()
    local actor = mock_character("Test", "1")
    
    local artifact_event = Event.create(EventType.ARTIFACT, { actor = actor, action = "pickup", item_name = "Stone" }, 1000, "Zone", {})
    local anomaly_event = Event.create(EventType.ANOMALY, { actor = actor, anomaly_type = "electro" }, 1000, "Zone", {})
    local reload_event = Event.create(EventType.RELOAD, { actor = actor }, 1000, "Zone", {})
    local death_event = Event.create(EventType.DEATH, { victim = actor }, 1000, "Zone", {})
    
    luaunit.assertTrue(Event.is_junk_event(artifact_event))
    luaunit.assertTrue(Event.is_junk_event(anomaly_event))
    luaunit.assertTrue(Event.is_junk_event(reload_event))
    luaunit.assertFalse(Event.is_junk_event(death_event))
end

-- Test Event.is_junk_event() for legacy flag-based events
function testIsJunkEventLegacyFlags()
    local junk_event = { flags = { is_artifact = true } }
    local non_junk_event = { flags = { is_dialogue = true } }
    local no_flags_event = {}
    
    luaunit.assertTrue(Event.is_junk_event(junk_event))
    luaunit.assertFalse(Event.is_junk_event(non_junk_event))
    luaunit.assertFalse(Event.is_junk_event(no_flags_event))
end

-- Test Event.get_involved_characters() for typed events
function testGetInvolvedCharactersTyped()
    local actor = mock_character("Actor", "1")
    local target = mock_character("Target", "2")
    local companion1 = mock_character("Companion1", "3")
    local companion2 = mock_character("Companion2", "4")
    
    local context = {
        actor = actor,
        target = target,
        companions = { companion1, companion2 }
    }
    
    local event = Event.create(EventType.TAUNT, context, 1000, "Zone", {})
    local characters = Event.get_involved_characters(event)
    
    luaunit.assertEquals(#characters, 4)
end

-- Run tests
os.exit(luaunit.LuaUnit.run())
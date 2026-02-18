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
    local source_event = Event.create(EventType.TAUNT, { actor = speaker }, 8000, {speaker})
    
    -- Create a dialogue event as a response (with source_event reference)
    local conversation = Event.create(EventType.DIALOGUE, { speaker = speaker, text = "Hello!" }, 8001, {speaker})
    conversation.source_event = source_event  -- This is how dialogue events reference their source
    
    local non_conversation = Event.create(EventType.DIALOGUE, { speaker = speaker, text = "Random comment" }, 8002, {speaker})

    luaunit.assertTrue(Event.was_conversation(conversation))
    luaunit.assertFalse(Event.was_conversation(non_conversation))
end

-- Test was_witnessed_by function
function testWasWitnessedBy()
    local witness1 = mock_character("Witness1", "1")
    local witness2 = mock_character("Witness2", "2")
    local actor = mock_character("Actor", "3")
    
    local event = Event.create(EventType.INJURY, { actor = actor }, 1000, {witness1, witness2})

    luaunit.assertTrue(Event.was_witnessed_by(event, "1"))
    luaunit.assertTrue(Event.was_witnessed_by(event, "2"))
    luaunit.assertFalse(Event.was_witnessed_by(event, "999"))
end

-- Test Typed Event creation
function testTypedEventCreation()
    local actor = mock_character("John", "1")
    local context = { actor = actor }
    local witnesses = { actor }
    
    local event = Event.create(EventType.WEAPON_JAM, context, 1000, witnesses)
    
    luaunit.assertNotNil(event)
    luaunit.assertEquals(event.type, EventType.WEAPON_JAM)
    luaunit.assertNotNil(event.context)
    luaunit.assertEquals(event.context.actor.name, "John")
    luaunit.assertEquals(event.game_time_ms, 1000)
    luaunit.assertEquals(#event.witnesses, 1)
end

-- Test Typed Event with flags
function testTypedEventWithFlags()
    local actor = mock_character("Jane", "2")
    local context = { actor = actor }
    local flags = { is_silent = true }
    
    local event = Event.create(EventType.INJURY, context, 2000, {actor}, flags)
    
    luaunit.assertNotNil(event.flags)
    luaunit.assertTrue(event.flags.is_silent)
end

-- Test Event.is_junk_event() for typed events
function testIsJunkEventTyped()
    local actor = mock_character("Test", "1")
    
    local artifact_event = Event.create(EventType.ARTIFACT, { actor = actor, action = "pickup", item_name = "Stone" }, 1000, {})
    local anomaly_event = Event.create(EventType.ANOMALY, { actor = actor, anomaly_type = "electro" }, 1000, {})
    local reload_event = Event.create(EventType.RELOAD, { actor = actor }, 1000, {})
    local death_event = Event.create(EventType.DEATH, { victim = actor }, 1000, {})
    
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
    
    local event = Event.create(EventType.TAUNT, context, 1000, {})
    local characters = Event.get_involved_characters(event)
    
    luaunit.assertEquals(#characters, 4)
end

-- Run tests
os.exit(luaunit.LuaUnit.run())
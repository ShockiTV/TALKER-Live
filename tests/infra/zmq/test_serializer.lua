package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit    = require('tests.utils.luaunit')
local serializer = require('infra.zmq.serializer')

-- ── helpers ──────────────────────────────────────────────────────────────────

local function make_char(overrides)
    local c = {
        game_id       = 123,
        name          = "Wolf",
        faction       = "Loner",
        experience    = "veteran",
        reputation    = "Good",
        personality   = "loner.1",
        backstory     = "generic.5",
        weapon        = "AK-74",
        visual_faction = nil,
    }
    if overrides then
        for k, v in pairs(overrides) do c[k] = v end
    end
    return c
end

local function make_event(overrides)
    local e = {
        type         = "DEATH",
        content      = nil,
        context      = {},
        game_time_ms = 500000,
        world_context = "In Cordon at noon during clear weather.",
        witnesses    = {},
        flags        = { is_silent = false },
    }
    if overrides then
        for k, v in pairs(overrides) do e[k] = v end
    end
    return e
end

-- ── serialize_character ───────────────────────────────────────────────────────

function testSerializeCharacter_nil()
    luaunit.assertNil(serializer.serialize_character(nil))
end

function testSerializeCharacter_gameIdIsString()
    local char   = make_char({ game_id = 123 })
    local result = serializer.serialize_character(char)
    luaunit.assertEquals(result.game_id, "123")
    luaunit.assertEquals(type(result.game_id), "string")
end

function testSerializeCharacter_allFields()
    local char   = make_char()
    local result = serializer.serialize_character(char)
    luaunit.assertEquals(result.name,        "Wolf")
    luaunit.assertEquals(result.faction,     "Loner")
    luaunit.assertEquals(result.experience,  "veteran")
    luaunit.assertEquals(result.reputation,  "Good")
    luaunit.assertEquals(result.personality, "loner.1")
    luaunit.assertEquals(result.backstory,   "generic.5")
    luaunit.assertEquals(result.weapon,      "AK-74")
end

function testSerializeCharacter_visualFaction()
    local char   = make_char({ visual_faction = "Duty" })
    local result = serializer.serialize_character(char)
    luaunit.assertEquals(result.visual_faction, "Duty")
end

-- ── serialize_context ─────────────────────────────────────────────────────────

function testSerializeContext_nil()
    local result = serializer.serialize_context(nil)
    luaunit.assertEquals(result, {})
end

function testSerializeContext_characterKeysAreSerialized()
    local char_keys = { "victim", "killer", "actor", "spotter", "target", "taunter", "speaker" }
    for _, key in ipairs(char_keys) do
        local ctx = { [key] = make_char({ game_id = 1 }) }
        local result = serializer.serialize_context(ctx)
        luaunit.assertNotNil(result[key], "Expected " .. key .. " to be serialized")
        luaunit.assertEquals(type(result[key].game_id), "string")
    end
end

function testSerializeContext_nonCharacterFieldsCopied()
    local ctx    = { anomaly_type = "gravitational", action = "pickup" }
    local result = serializer.serialize_context(ctx)
    luaunit.assertEquals(result.anomaly_type, "gravitational")
    luaunit.assertEquals(result.action,        "pickup")
end

function testSerializeContext_companionsArray()
    local ctx = {
        companions = { make_char({ game_id = 10 }), make_char({ game_id = 20 }) }
    }
    local result = serializer.serialize_context(ctx)
    luaunit.assertNotNil(result.companions)
    luaunit.assertEquals(#result.companions, 2)
    luaunit.assertEquals(result.companions[1].game_id, "10")
    luaunit.assertEquals(result.companions[2].game_id, "20")
end

function testSerializeContext_fieldWithoutGameId_notSerialized()
    -- A table that looks like it might be a char but has no game_id should be copied as-is
    local ctx = { victim = { some_field = "value" } }
    -- "victim" is a character key but no game_id → copied as raw table
    local result = serializer.serialize_context(ctx)
    luaunit.assertEquals(result.victim, ctx.victim)
end

-- ── serialize_event ───────────────────────────────────────────────────────────

function testSerializeEvent_nil()
    luaunit.assertNil(serializer.serialize_event(nil))
end

function testSerializeEvent_allFields()
    local event  = make_event()
    local result = serializer.serialize_event(event)
    luaunit.assertEquals(result.type,          "DEATH")
    luaunit.assertEquals(result.game_time_ms,  500000)
    luaunit.assertEquals(result.world_context, "In Cordon at noon during clear weather.")
    luaunit.assertNotNil(result.context)
    luaunit.assertNotNil(result.witnesses)
    luaunit.assertNotNil(result.flags)
end

function testSerializeEvent_witnessesAreSerialized()
    local event  = make_event({ witnesses = { make_char({ game_id = 5 }), make_char({ game_id = 6 }) } })
    local result = serializer.serialize_event(event)
    luaunit.assertEquals(#result.witnesses, 2)
    luaunit.assertEquals(result.witnesses[1].game_id, "5")
    luaunit.assertEquals(result.witnesses[2].game_id, "6")
end

function testSerializeEvent_contextIsSerializedRecursively()
    local event = make_event({
        context = { victim = make_char({ game_id = 99 }), location = "Cordon" }
    })
    local result = serializer.serialize_event(event)
    luaunit.assertEquals(result.context.victim.game_id, "99")
    luaunit.assertEquals(result.context.location,       "Cordon")
end

-- ── serialize_events ──────────────────────────────────────────────────────────

function testSerializeEvents_nil()
    luaunit.assertEquals(serializer.serialize_events(nil), {})
end

function testSerializeEvents_array()
    local events = { make_event({ type = "DEATH" }), make_event({ type = "INJURY" }) }
    local result = serializer.serialize_events(events)
    luaunit.assertEquals(#result, 2)
    luaunit.assertEquals(result[1].type, "DEATH")
    luaunit.assertEquals(result[2].type, "INJURY")
end

os.exit(luaunit.LuaUnit.run())

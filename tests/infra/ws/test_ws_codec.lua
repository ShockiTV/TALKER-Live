package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit = require('tests.utils.luaunit')
local codec   = require('infra.ws.codec')
local json    = require('infra.HTTP.json')

-- ── encode ───────────────────────────────────────────────────────────────────

function testEncode_basicTopic()
    local raw = codec.encode("game.event", { type = "DEATH" })
    local data = json.decode(raw)
    luaunit.assertEquals(data.t, "game.event")
    luaunit.assertEquals(data.p.type, "DEATH")
    luaunit.assertNotNil(data.ts)
    luaunit.assertNil(data.r)
end

function testEncode_withRequestId()
    local raw = codec.encode("state.query.batch", { queries = {} }, "req-1")
    local data = json.decode(raw)
    luaunit.assertEquals(data.t, "state.query.batch")
    luaunit.assertEquals(data.r, "req-1")
end

function testEncode_nilPayloadBecomesEmptyTable()
    local raw = codec.encode("config.sync")
    local data = json.decode(raw)
    luaunit.assertEquals(type(data.p), "table")
end

function testEncode_tsIsNumber()
    local raw = codec.encode("test", {})
    local data = json.decode(raw)
    luaunit.assertEquals(type(data.ts), "number")
    luaunit.assertTrue(data.ts > 0)
end

-- ── decode ───────────────────────────────────────────────────────────────────

function testDecode_validEnvelope()
    local raw = json.encode({ t = "dialogue.display", p = { speaker_id = "1", dialogue = "Hello" }, ts = 100 })
    local msg, err = codec.decode(raw)
    luaunit.assertNil(err)
    luaunit.assertNotNil(msg)
    luaunit.assertEquals(msg.t, "dialogue.display")
    luaunit.assertEquals(msg.p.speaker_id, "1")
    luaunit.assertEquals(msg.ts, 100)
end

function testDecode_withRequestId()
    local raw = json.encode({ t = "state.response", p = {}, r = "abc-123", ts = 200 })
    local msg = codec.decode(raw)
    luaunit.assertEquals(msg.r, "abc-123")
end

function testDecode_missingTField()
    local raw = json.encode({ p = {}, ts = 100 })
    local msg, err = codec.decode(raw)
    luaunit.assertNil(msg)
    luaunit.assertNotNil(err)
    luaunit.assertStrContains(err, "t")
end

function testDecode_invalidJSON()
    local msg, err = codec.decode("not json {{{")
    luaunit.assertNil(msg)
    luaunit.assertNotNil(err)
end

function testDecode_emptyString()
    local msg, err = codec.decode("")
    luaunit.assertNil(msg)
    luaunit.assertNotNil(err)
end

function testDecode_nilInput()
    local msg, err = codec.decode(nil)
    luaunit.assertNil(msg)
    luaunit.assertNotNil(err)
end

function testDecode_missingPDefaultsToEmptyTable()
    local raw = json.encode({ t = "test", ts = 1 })
    local msg = codec.decode(raw)
    luaunit.assertEquals(type(msg.p), "table")
end

function testDecode_missingRIsNil()
    local raw = json.encode({ t = "test", p = {}, ts = 1 })
    local msg = codec.decode(raw)
    luaunit.assertNil(msg.r)
end

-- ── round-trip ───────────────────────────────────────────────────────────────

function testRoundTrip_preservesPayload()
    local original_payload = { a = 1, b = { c = 2 } }
    local encoded = codec.encode("my.topic", original_payload)
    local decoded = codec.decode(encoded)

    luaunit.assertEquals(decoded.t, "my.topic")
    luaunit.assertEquals(decoded.p.a, 1)
    luaunit.assertEquals(decoded.p.b.c, 2)
end

function testRoundTrip_preservesRequestId()
    local encoded = codec.encode("q", { x = 1 }, "req-42")
    local decoded = codec.decode(encoded)
    luaunit.assertEquals(decoded.r, "req-42")
end

function testRoundTrip_nestedPayload()
    local payload = {
        event = {
            type = "DEATH",
            context = {
                victim = { name = "Wolf", game_id = "123" },
            },
        },
        is_important = true,
    }
    local encoded = codec.encode("game.event", payload)
    local decoded = codec.decode(encoded)

    luaunit.assertEquals(decoded.p.event.type, "DEATH")
    luaunit.assertEquals(decoded.p.event.context.victim.name, "Wolf")
    luaunit.assertEquals(decoded.p.is_important, true)
end

os.exit(luaunit.LuaUnit.run())

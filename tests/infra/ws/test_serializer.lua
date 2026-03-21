package.path = package.path .. ';./bin/lua/?.lua;./bin/lua/*/?.lua'
require("tests.test_bootstrap")

local luaunit    = require('tests.utils.luaunit')
local serializer = require('infra.ws.serializer')

-- ── helpers ──────────────────────────────────────────────────────────────────

local function make_char(overrides)
    local c = {
        game_id        = 123,
        name           = "Wolf",
        faction        = "Loner",
        experience     = "veteran",
        reputation     = 750,
        weapon         = "AK-74",
        visual_faction = nil,
        story_id       = "esc_2_12_stalker_wolf",
        sound_prefix   = "stalker_1",
    }
    if overrides then
        for k, v in pairs(overrides) do c[k] = v end
    end
    return c
end

local function make_event(overrides)
    local e = {
        type         = "DEATH",
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
    luaunit.assertEquals(result.name,         "Wolf")
    luaunit.assertEquals(result.faction,      "Loner")
    luaunit.assertEquals(result.experience,   "veteran")
    luaunit.assertEquals(result.reputation,   750)
    luaunit.assertEquals(result.weapon,       "AK-74")
    luaunit.assertEquals(result.story_id,     "esc_2_12_stalker_wolf")
    luaunit.assertEquals(result.sound_prefix, "stalker_1")
end

function testSerializeCharacter_storyIdIncludedInWireFormat()
    -- story_id must be present in the wire format so Python can identify story NPCs
    local char   = make_char({ story_id = "bar_dolg_leader" })
    local result = serializer.serialize_character(char)
    luaunit.assertEquals(result.story_id, "bar_dolg_leader")
end

function testSerializeCharacter_storyIdNilWhenAbsent()
    -- Build a char table without story_id at all — wire format should carry nil (not error)
    local char = {
        game_id    = 7,
        name       = "Generic Stalker",
        faction    = "Loner",
        experience = "rookie",
        reputation = 0,
        -- no story_id key
    }
    local result = serializer.serialize_character(char)
    luaunit.assertNil(result.story_id)
end

function testSerializeCharacter_visualFaction()
    local char   = make_char({ visual_faction = "Duty" })
    local result = serializer.serialize_character(char)
    luaunit.assertEquals(result.visual_faction, "Duty")
end

function testSerializeCharacter_soundPrefix()
    local char   = make_char({ sound_prefix = "bandit_3" })
    local result = serializer.serialize_character(char)
    luaunit.assertEquals(result.sound_prefix, "bandit_3")
end

function testSerializeCharacter_soundPrefixNilWhenAbsent()
    local char = {
        game_id    = 7,
        name       = "Generic Stalker",
        faction    = "Loner",
        experience = "rookie",
        reputation = 0,
    }
    local result = serializer.serialize_character(char)
    luaunit.assertNil(result.sound_prefix)
end

-- ── serialize_context ─────────────────────────────────────────────────────────

function testSerializeContext_nil()
    local result = serializer.serialize_context(nil)
    luaunit.assertEquals(result, {})
end

function testSerializeContext_characterKeysAreSerialized()
    local char_keys = { "victim", "killer", "actor", "spotter", "target", "taunter", "speaker", "task_giver" }
    for _, key in ipairs(char_keys) do
        local ctx = { [key] = make_char({ game_id = 1 }) }
        local result = serializer.serialize_context(ctx)
        luaunit.assertNotNil(result[key], "Expected " .. key .. " to be serialized")
        luaunit.assertEquals(type(result[key].game_id), "string")
    end
end

function testSerializeContext_nonCharacterFieldsCopied()
    local ctx    = { anomaly_type = "zone_mine_gravitational_weak", action = "pickup" }
    local result = serializer.serialize_context(ctx)
    luaunit.assertEquals(result.anomaly_type, "zone_mine_gravitational_weak")
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

function testSerializeContext_taskGiver_factionPreservedAsIs()
    -- task_giver is a plain table with technical faction ID (e.g. "dolg")
    -- It should be serialized as a character with faction preserved unchanged (not converted to display name)
    local task_giver = {
        game_id    = 555,
        name       = "General Voronin",
        faction    = "dolg",      -- technical ID, must NOT become "Duty"
        experience = "Master",
        reputation = 1200,
    }
    local ctx = { task_giver = task_giver }
    local result = serializer.serialize_context(ctx)
    luaunit.assertNotNil(result.task_giver, "task_giver should be serialized as a character")
    luaunit.assertEquals(type(result.task_giver.game_id), "string")
    luaunit.assertEquals(result.task_giver.game_id, "555")
    luaunit.assertEquals(result.task_giver.faction, "dolg",   "faction must be technical ID, not display name")
    luaunit.assertEquals(result.task_giver.name,    "General Voronin")
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

-- ── serialize_character_with_gender ───────────────────────────────────────────

function testSerializeCharacterWithGender_nil()
    luaunit.assertNil(serializer.serialize_character_with_gender(nil))
end

function testSerializeCharacterWithGender_femaleSoundPrefix()
    local char   = make_char({ sound_prefix = "woman" })
    local result = serializer.serialize_character_with_gender(char)
    luaunit.assertEquals(result.gender, "female")
    luaunit.assertEquals(result.name,   "Wolf")
    luaunit.assertEquals(type(result.game_id), "string")
end

function testSerializeCharacterWithGender_maleSoundPrefix()
    local char   = make_char({ sound_prefix = "stalker_1" })
    local result = serializer.serialize_character_with_gender(char)
    luaunit.assertEquals(result.gender, "male")
end

function testSerializeCharacterWithGender_banditSoundPrefix()
    local char   = make_char({ sound_prefix = "bandit_2" })
    local result = serializer.serialize_character_with_gender(char)
    luaunit.assertEquals(result.gender, "male")
end

function testSerializeCharacterWithGender_nilSoundPrefix()
    -- A character with no sound_prefix at all should default to "male"
    local char = {
        game_id    = 7,
        name       = "Generic Stalker",
        faction    = "Loner",
        experience = "rookie",
        reputation = 0,
    }
    local result = serializer.serialize_character_with_gender(char)
    luaunit.assertEquals(result.gender, "male")
end

-- ── serialize_event ts field ──────────────────────────────────────────────────

function testSerializeEvent_includesTs()
    local event = make_event({ ts = 1709912345 })
    local result = serializer.serialize_event(event)
    luaunit.assertEquals(result.ts, 1709912345)
end

function testSerializeEvent_tsNilWhenAbsent()
    local event = make_event()  -- no ts field
    local result = serializer.serialize_event(event)
    luaunit.assertNil(result.ts)
end

function testSerializeCharacterWithGender_preservesAllBaseFields()
    local char   = make_char({ sound_prefix = "woman" })
    local result = serializer.serialize_character_with_gender(char)
    luaunit.assertEquals(result.name,         "Wolf")
    luaunit.assertEquals(result.faction,      "Loner")
    luaunit.assertEquals(result.experience,   "veteran")
    luaunit.assertEquals(result.sound_prefix, "woman")
    luaunit.assertEquals(result.gender,       "female")
end

-- ── serialize_character_info ──────────────────────────────────────────────────

-- Mock memory_store that returns preset backgrounds
local function make_mock_memory_store(backgrounds)
    return {
        query = function(self, char_id, resource)
            if resource == "memory.background" and backgrounds then
                return backgrounds[char_id]
            end
            return nil
        end,
    }
end

function testSerializeCharacterInfo_singleCharacterNoSquad()
    local char   = make_char({ game_id = 100, sound_prefix = "stalker_1" })
    local result = serializer.serialize_character_info(char, {}, nil)
    luaunit.assertNotNil(result.character)
    luaunit.assertEquals(result.character.game_id, "100")
    luaunit.assertEquals(result.character.gender,  "male")
    luaunit.assertNil(result.character.background)
    luaunit.assertEquals(#result.squad_members, 0)
end

function testSerializeCharacterInfo_characterWithSquad()
    local char  = make_char({ game_id = 100, name = "Leader", sound_prefix = "stalker_1" })
    local squad = {
        make_char({ game_id = 200, name = "Member1", sound_prefix = "woman" }),
        make_char({ game_id = 300, name = "Member2", sound_prefix = "bandit_3" }),
    }
    local result = serializer.serialize_character_info(char, squad, nil)
    luaunit.assertEquals(result.character.name,           "Leader")
    luaunit.assertEquals(result.character.gender,         "male")
    luaunit.assertEquals(#result.squad_members, 2)
    luaunit.assertEquals(result.squad_members[1].name,    "Member1")
    luaunit.assertEquals(result.squad_members[1].gender,  "female")
    luaunit.assertEquals(result.squad_members[2].name,    "Member2")
    luaunit.assertEquals(result.squad_members[2].gender,  "male")
end

function testSerializeCharacterInfo_backgroundsPresent()
    local char  = make_char({ game_id = 100, sound_prefix = "stalker_1" })
    local squad = { make_char({ game_id = 200, sound_prefix = "woman" }) }
    local mock_store = make_mock_memory_store({
        ["100"] = { traits = {"brave"}, backstory = "A veteran", connections = {} },
        ["200"] = { traits = {"cautious"}, backstory = "A newcomer", connections = {} },
    })
    local result = serializer.serialize_character_info(char, squad, mock_store)
    luaunit.assertNotNil(result.character.background)
    luaunit.assertEquals(result.character.background.traits[1], "brave")
    luaunit.assertNotNil(result.squad_members[1].background)
    luaunit.assertEquals(result.squad_members[1].background.traits[1], "cautious")
end

function testSerializeCharacterInfo_backgroundAbsent()
    local char   = make_char({ game_id = 100, sound_prefix = "stalker_1" })
    local mock_store = make_mock_memory_store({})  -- no backgrounds
    local result = serializer.serialize_character_info(char, {}, mock_store)
    luaunit.assertNil(result.character.background)
end

function testSerializeCharacterInfo_nilSquadMembers()
    local char   = make_char({ game_id = 100, sound_prefix = "stalker_1" })
    local result = serializer.serialize_character_info(char, nil, nil)
    luaunit.assertEquals(#result.squad_members, 0)
end

os.exit(luaunit.LuaUnit.run())

---@diagnostic disable: different-requires

local mock_characters = require('tests/mocks/mock_characters')
local Event = require('domain.model.event')
local EventType = require('domain.model.event_types')

local killer = mock_characters[1]
local victim = mock_characters[2]
local witnesses = {mock_characters[1], mock_characters[2], mock_characters[3], mock_characters[4], mock_characters[5], mock_characters[6]}

local events = { -- lead up to the kill
    -- lost map
    Event.create(EventType.ACTION, { actor = victim, action_description = "lost the map" }, 100, witnesses),
    -- insult
    Event.create(EventType.TAUNT, { actor = victim, target = killer }, 200, witnesses),
    -- fight
    Event.create(EventType.ACTION, { actor = killer, action_description = "fought " .. victim.name }, 300, witnesses),
    -- kill
    Event.create(EventType.DEATH, { killer = killer, victim = victim }, 400, witnesses)
}

return events
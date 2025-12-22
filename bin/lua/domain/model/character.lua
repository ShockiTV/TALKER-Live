package.path = package.path .. ";./bin/lua/?.lua;"
local backstories = require("domain.repo.backstories")
local personalities = require("domain.repo.personalities")
local log = require('framework.logger')

-- Character class definition
Character = {}

function Character.new(game_id, name, experience, faction, weapon)
    new_char = {
        game_id = game_id,
        name = name,
        experience = experience,
        faction = faction,
        weapon = weapon
    }
    new_char.backstory = backstories.get_backstory(new_char)
    new_char.personality = personalities.get_personality(new_char)
    return new_char
end

function Character.set_backstory(character, backstory)
    character.backstory = backstory
end

function Character.set_personality(character, personality)
    character.personality = personality
end

function Character.describe(character)
    local description = string.format("%s, a %s rank member of the %s faction who is %s", character.name, character.experience, character.faction, character.personality)
    if character.weapon then
        description = description .. " wielding a " .. character.weapon
    end
    return description
end

function Character.describe_short(character)
    return character.name
end

return Character


--------------------------
-- Notes (Dan):
-- I decided to use simple data structures for easier serialization and deserialization. 
-- I also decided to use a separate module for the personality logic to keep the Character module clean and focused on character-related functionality. 

-- Notes (Coelacanth):
-- Character backstory is omitted from the character.describe function to reduce clutter and improve parseability of the speaker picking function.

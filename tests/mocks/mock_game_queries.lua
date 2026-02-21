-- DEPRECATED: This file is superseded by tests/mocks/mock_engine.lua.
-- Use require("tests.mocks.mock_engine") and tests/test_bootstrap.lua instead.
-- Retained for reference only — no active test requires this file.

-- Mock Module for Testing Lua Script Functionality
local mocker = {}


-- Mocking dependencies
local db = {
    actor = {
        id = 0,
        alive = function() return true end,
        character_name = function() return "Player" end,
        active_item = function() return "Weapon123" end,
        give_game_news = function(name, message, image, delay, showtime)
            print("News:", name, message, image, "Showtime:", showtime, "ms")
        end
    },
    guy = {
        id = 1,
        alive = function() return true end,
        character_name = function() return "Dude" end,
        active_item = function() return "Weapon123" end,
        give_game_news = function(name, message, image, delay, showtime)
            print("News:", name, message, image, "Showtime:", showtime, "ms")
        end
    }
}

local game = {
    translate_string = function(key)
        if key:find("faction") then
            return key .. "_translated"
        else
            return key
        end
    end
}

local ui_item = {
    get_sec_name = function(section)
        return section .. "_sec_name"
    end
}

local xr_sound = {
    set_sound_play = function(ac_id, sound_name)
        print("Sound played:", sound_name)
    end
}

local level = {
    iterate_nearest = function(location, distance, func)
        -- mock up some object iteration for demonstration
        for i = 1, 5 do
            local obj = {id = i, alive = function() return true end, position = function() return location end}
            if not func(obj) then break end
        end
    end
}

-- Additional Helper Functions
function mocker.try(func, ...)
    local status, result = pcall(func, ...)
    if not status then
        print("Error: " .. tostring(result))
        return nil
    end
    return result
end

function mocker.get_game_path()
    return ""
end

function mocker.get_technical_name(object)
    return object.section
end

function mocker.is_item(item)
    return ui_item.get_sec_name(item.section) ~= ""
end

function mocker.get_item_description(item)
    return ui_item.get_sec_name(mocker.get_technical_name(item))
end

function mocker.is_weapon(item)
    return mocker.try(mocker.IsWeapon, item)
end

function mocker.get_player()
    return db.actor
end

function mocker.is_player(npc)
    return npc and npc.id == 0
end

function mocker.get_player_weapon()
    return db.actor.active_item()
end

function mocker.is_player_alive()
    return db.actor.alive()
end

function mocker.is_stalker(object)
    return mocker.try(mocker.IsStalker, object)
end

function mocker.is_monster(object)
    return mocker.try(mocker.IsMonster, object)
end

function mocker.get_id(obj)
    return obj.id
end

function mocker.is_alive(obj)
    return obj.alive()
end

function mocker.get_name(person)
    return person.character_name() or "Unknown"
end

function mocker.get_name_by_id(id)
    local obj = mocker.get_obj_by_id(id)
    return obj and mocker.get_name(obj) or "Unknown"
end

function mocker.get_weapon(npc)
    return npc.active_item()
end

function mocker.get_relations(observer, target)
    return mocker.try(observer.relation, observer, target) or 1
end

function mocker.get_squad(obj)
    return mocker.try(mocker.get_object_squad, obj)
end

function mocker.is_companion(npc)
    return npc.has_info and npc.has_info("npcx_is_companion")
end

function mocker.get_faction(npc)
    return mocker.try(mocker.character_community, npc) or "no faction"
end

function mocker.get_rank(npc)
    return mocker.try(mocker.get_obj_rank_name, npc) or "2"
end

function mocker.get_real_player_faction()
    return "player_true_community"
end

function mocker.is_psy_storm_ongoing()
    return false
end

function mocker.is_surge_ongoing()
    return false
end

function mocker.display_hud_message(message)
    print("HUD message:", message)
end

function mocker.play_sound(sound_name)
    xr_sound.set_sound_play("AC_ID", sound_name)
end

function mocker.send_news_tip(sender_name, message, image, showtime)
    db.actor.give_game_news(sender_name, message, image, 0, showtime)
end

function mocker.get_obj_by_id(id)
    id = tonumber(id)
    for _, entity in pairs(db) do
        if entity.id == id then
            return entity
        end
    end
    return nil
end

function mocker.get_position(object)
    return {x = 0, y = 0, z = 0}
end

-- Mocking game functions
function mocker.load_xml(input)
    if not input then return "" end
    local key = "talker_" .. input
    local result = game.translate_string(key) or game.translate_string(input)
    if result == key then
        print("Translation not found for " .. key)
    end
    return result == "talkerIgnore" and "" or result
end

function mocker.iterate_nearest(location, distance, fun)
    level.iterate_nearest(location, distance, fun)
end

function mocker.get_nearby_characters(center_object, distance, max, exclusion_list)
    local characters = {
        { id = "1", name = "Lonely Stalker", rank = 2, faction = "Loner" },
        { id = "2", name = "Veteran Merc", rank = 4, faction = "Mercenary" }
    }
    return characters
end

function mocker.load_random_xml(key)
    -- Add random personalities for testing
    local random_personalities = {
        "Adventurous",
        "Cautious",
        "Curious",
        "Diligent",
        "Empathetic"
    }
    return random_personalities[math.random(#random_personalities)]
end

function mocker.is_unique_character_by_id(id)
    -- Placeholder for is_unique_character_by_id
    -- Return true if the character is unique
    return id == "0"
end


return mocker
-- DEPRECATED: This file is superseded by tests/mocks/mock_engine.lua.
-- Use require("tests.mocks.mock_engine") and tests/test_bootstrap.lua instead.
-- Retained for reference only — no active test requires this file.

-- Mock Module for Testing
local mocker = {}

-- Dependency Mocks
local xr_sound = {
    set_sound_play = function(ac_id, sound)
        print("Playing sound:", sound, "for AC_ID:", ac_id)
    end
}
local game = {
    translate_string = function(faction)
        return faction .. "_translated"
    end
}
local queries = {
    is_living_character = function(character)
        return character.is_living
    end
}

-- Additional Helper Functions Mocks
local function get_obj_by_id(id)
    return {
        is_living = true,
        character_icon = function()
            return "ui_icon_" .. id
        end,
        name = "NPC_" .. id,
        faction = "faction_" .. id,
        is_companion = function()
            return id % 2 == 0  -- mock condition: even IDs are companions
        end
    }
end

local function get_name(obj)
    return obj.name
end

local function is_stalker(obj)
    return true -- Assuming every character is a stalker for simplicity
end

local function is_companion(obj)
    return obj:is_companion()
end

local function get_faction(obj)
    return obj.faction
end

local function send_news_tip(name, message, icon, showtime)
    print("News tip:", name, message, icon, "Showtime:", showtime, "ms")
end

-- Mocked Functions from Original Script
function mocker.play_pda_beep()
    xr_sound.set_sound_play("AC_ID", "pda_beep_1")
end

function mocker.get_character_icon(sender)
    local image = "ui_iconsTotal_grouping"
    if sender ~= nil then
        if type(sender) == "string" then
            image = "ui_inGame2_Radiopomehi"
        elseif is_stalker(sender) then
            image = sender:character_icon()
        end
    end
    return image
end

function mocker.determine_sender_name(sender)
    local sender_name = get_name(sender)
    sender_name = sender_name .. (", " .. game.translate_string(get_faction(sender)) .. (is_companion(sender) and " companion" or ""))
    return sender_name
end

function mocker.display_message(sender_id, message)
    local sender = get_obj_by_id(sender_id)
    if not queries.is_living_character(sender) then return end -- this also blocks mutants

    local showtime = 5000 -- calculate_showtime(message)
    local sender_name = mocker.determine_sender_name(sender)
    local image = mocker.get_character_icon(sender)
    send_news_tip(sender_name, message, image, showtime)

    mocker.play_pda_beep()
end

function mocker.display_hud_message(message, showtime)
    send_news_tip("HUD", message, "ui_icon_hud", showtime)
end


return mocker
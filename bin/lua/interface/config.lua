-- dynamic_config.lua – values that depend on talker_mcm are now getters
local game_config = talker_mcm
local language = require("infra.language")




-- helper
local function cfg(key, default)
    return (game_config and game_config.get and game_config.get(key)) or default
end


local function is_valid_key(key)
    return key and key:match("^sk%-[%w%-_]+") and #key >= 20
end

local function try_load(path)
    local f = io.open(path, "r")
    if f then
        local key = f:read("*a")
        f:close()
        if is_valid_key(key) then return key end
    end
    return nil
end

local function load_api_key(FileName)
    local paths = {
        string.lower(FileName)..".txt",
        FileName..".key",
        "..\\"..string.lower(FileName)..".txt",
        "..\\"..FileName..".key"
    }

    local temp_path = os.getenv("TEMP") or os.getenv("TMP")
    if temp_path then
        table.insert(paths, temp_path.."\\"..FileName..".key")
        table.insert(paths, temp_path.."\\"..string.lower(FileName)..".txt")
    end

    for _, path in ipairs(paths) do
        local key = try_load(path)
        if key then return key end
    end

    local key = os.getenv("OPENAI_API_KEY")
    if not is_valid_key(key) then
        error("Could not find valid OpenAI API key in files or environment variable")
    end
    return key
end


local c = {}

-- static values
c.EVENT_WITNESS_RANGE  = 25
c.NPC_SPEAK_DISTANCE   = 30
c.BASE_DIALOGUE_CHANCE = 0.25
c.player_speaks        = false
c.SHOW_HUD_MESSAGES    = true
c.OPENAI_API_KEY       = load_api_key("openAi_API_KEY")
c.OPENROUTER_API_KEY = load_api_key("openRouter_API_KEY")

local DEFAULT_LANGUAGE = language.any.long

-- dynamic getters


function c.modelmethod()
    return tonumber(cfg("ai_model_method", 0))
end

function c.custom_dialogue_model()
    return cfg("custom_ai_model", "google/gemini-2.0-flash-001")
end

function c.custom_dialogue_model_fast()
    return cfg("custom_ai_model_fast", "openai/gpt-4o-mini")
end


function c.language()
    return cfg("language", DEFAULT_LANGUAGE)
end

function c.language_short()
    return language.to_short(c.language())
end

function c.dialogue_model()
    return cfg("gpt_version", "gpt-4o")
end

function c.dialogue_prompt()
    return ("You are a dialogue generator for the harsh setting of STALKER. Swear if appropriate. " ..
            "Limit your reply to one sentence of dialogue. " ..
            "Write ONLY dialogue and make it without quotations or leading with the character name. Avoid cliche and corny dialogue " ..
            "Write dialogue that is realistic and appropriate for the tone of the STALKER setting. " ..
            "Don't be overly antagonistic if not provoked. " ..
            "Speak %s"
        ):format(c.language())
end

return c

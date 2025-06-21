-- dynamic_config.lua – values that depend on talker_mcm are now getters
local game_config = talker_mcm
local language = require("infra.language")


local c = {}

-- helper
local function cfg(key, default)
    return (game_config and game_config.get and game_config.get(key)) or default
end

function c.modelmethod()
    return tonumber(cfg("ai_model_method", 0))
end

local function load_api_key(FileName)
    local f = io.open(openAi_API_KEY.key, "r")
    if f then 
        return f:read("*a") 
    end
    local key = os.getenv(FileName)
    if key == "" then 
        error("Could not find OpenAI API key file") 
    end
    return key
end




-- static values
c.EVENT_WITNESS_RANGE  = 25
c.NPC_SPEAK_DISTANCE   = 20
c.BASE_DIALOGUE_CHANCE = 0.25
c.player_speaks        = false
c.SHOW_HUD_MESSAGES    = true
c.OPENAI_API_KEY       = load_api_key("openAi_API_KEY.key")
c.OPENROUTER_API_KEY = load_api_key("openRouter_API_KEY.key")

local DEFAULT_LANGUAGE = language.any.long

-- dynamic getters


function c.custom_dialogue_model()
    return cfg("custom_ai_model", "deepseek/deepseek-chat-v3-0324")
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
    return ("You are a character for the harsh setting of STALKER. Swear if appropriate. " ..
            "Limit your reply to one sentence of dialogue. " ..
            "Write ONLY dialogue and make it without quotations or leading with the character name. Avoid cliche and corny dialogue " ..
            "Write dialogue that is realistic and appropriate for the tone of the STALKER setting and surroundings. " ..
            "Don't be overly antagonistic if not provoked. " ..
            "Speak %s"
        ):format(c.language())
end

return c

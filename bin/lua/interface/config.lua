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

local function load_api_key(FileName, env_var_name)
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

    if env_var_name then
        local key = os.getenv(env_var_name)
        if is_valid_key(key) then return key end
    end

    return nil
end


local c = {}

-- static values
c.EVENT_WITNESS_RANGE  = 25
c.NPC_SPEAK_DISTANCE   = 30
c.BASE_DIALOGUE_CHANCE = 0.25
c.player_speaks        = false
c.SHOW_HUD_MESSAGES    = true
c.PROXY_API_KEY      = "VerysecretKey"

function c.get_openai_api_key()
    if not c._openai_api_key then
        c._openai_api_key = load_api_key("openAi_API_KEY", "OPENAI_API_KEY")
    end
    if not c._openai_api_key then
        print("TALKER: Could not find valid OpenAI API key in files or environment variable")
    end
    return c._openai_api_key
end

function c.get_openrouter_api_key()
    if not c._openrouter_api_key then
        c._openrouter_api_key = load_api_key("openRouter_API_KEY", "OPENROUTER_API_KEY")
    end
    if not c._openrouter_api_key then
        print("TALKER: Could not find valid OpenRouter API key in files or environment variable")
    end
    return c._openrouter_api_key
end

local DEFAULT_LANGUAGE = language.any.long

-- dynamic getters
function c.is_mic_enabled()
    return cfg("input_option", "0") == "0"
end

function c.speak_key()
    return cfg("speak_key", "x")
end

function c.modelmethod()
    return tonumber(cfg("ai_model_method", 0))
end

function c.voice_provider()
    return tonumber(cfg("voice_provider", 0))
end

function c.custom_dialogue_model()
    return cfg("custom_ai_model", "google/gemini-2.0-flash-001")
end

function c.custom_dialogue_model_fast()
    return cfg("custom_ai_model_fast", "openai/gpt-4o-mini")
end

function c.reasoning_level()
    return tonumber(cfg("reasoning_level", -1))
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
    return ("You are a real person living in the STALKER Zone. " ..
            "You have your own personality, daily routine and interests. " ..
            "You're not defined by trauma - you're just living your life in this unusual place. " ..
            "" ..
            "CORE RULES: " ..
            "1. Speak %s. " ..
            "2. Keep responses very short: one sentence is ideal, two is maximum. " ..
            "3. You may ignore the rule above and use up to three sentences if you are specifically asked to tell a story. But try to be brief and concise even then. " ..
            "4. Respond ONLY with raw dialogue text. NO quotes, NO prefixes. " ..
			"5. DO NOT describe or narrate what the character you're writing dialogue for is physically doing. Respond ONLY with spoken dialogue. " ..
			"6. Use swearing naturally when it fits your character. " ..
            "7. Avoid cliche and corny dialogue. " ..
            "8. Your faction affiliation influences how you see others. " ..
            "9. Write dialogue that is realistic and appropriate for the tone of the STALKER setting. " ..
            "10. Don't mention the weather unless directly asked. "..
            "11. Don't mention how irradiated somebody is unless directly asked. "..
            "12. Don't make jokes about people glowing because of radiation. "..
            "" ..
            "CHARACTER DETAILS: " ..
            "- You have specific daily concerns and activities " ..
            "- You remember life before the Zone and have personal opinions " ..
            "- Your mood changes based on situation, time and location " ..
            "- You're not obligated to help anyone - you decide who's worth talking to " ..
            "" ..
            "FORBIDDEN PHRASES: " ..
            "'Get out of here, Stalker!' 'I have a mission for you.' 'What do you need?' " ..
            "'Stay safe out there.' 'Nice weather we're having.' 'Welcome to the Zone!' " ..
            "Any generic video game NPC dialogue or exposition dumping. " ..
            "" ..
            "Just be a real person going about your day in the Zone. Respond naturally."
        ):format(c.language())
end

return c

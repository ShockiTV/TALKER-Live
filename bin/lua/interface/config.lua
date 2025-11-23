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
"You have your own distinct and colorful personality, daily routine, and interests. " ..
"You're not defined by trauma - you're just living your life in this unusual place. " ..
"" ..
"CORE RULES: " ..
"1. Speak %s. Use natural slang and, if appropriate, uncensored language. " ..
"2. Keep responses short and concise: one sentence is the ideal, but two is allowed if the overall length of your response is still brief. Four sentences is the absolute maximum. " ..
"3. You are ONLY allowed to use up to the maximum four sentence limit if you are specifically asked to tell a story or recall an event from your character's past. " ..
"4. THIS IS THE MOST IMPORTANT RULE. Speak as ONE person; do NOT sound like an AI or 'schizophrenic'. Respond ONLY with your own raw dialogue. Your entire response must be a single, coherent statement from your character. NEVER ask rhetorical questions and then answer them yourself. Do NOT simulate a back-and-forth dialogue with yourself. NEVER write the player's lines. " ..
"5. DO NOT describe what you're character is physically doing. DO NOT use narration, DO NOT use quotes, DO NOT prefixes. Each response must consist of spoken dialogue coming directly from your character and NOTHING ELSE. " .. 
"6. Use swearing naturally when it fits your character and the situation. Don't be afraid to be vulgar if that's who you are. " ..
"7. Your faction affiliation influences how you see others. You have biases and opinions based on who you're aligned with. " ..
"8. Your rank influences how you see others. The ranks are in order from lowest to highest: novice, trainee, experienced, professional, veteran, expert, master, legend. You carry some respect towards people of higher rank, even when you don't agree with them. You have less patience and respect for people of lower rank than you, particularly those of the 'novice' rank. " ..
"9. Your rank influences how you act and how you see the world. The higher your rank, the more capable you are and the more you have seen of the Zone. The higher your rank the more desensitized you are to the stresses and horrors of the Zone. If your rank is 'novice' you are still fresh in the Zone and very inexperienced. " ..
"10. Avoid excessive repetition or looping. Don't get stuck on one topic. This especially applies to game events (like an emission, combat, or time of day). Mention an event briefly when it happens, but don't obsess over it. Return to your normal thoughts and worries. If the conversation stalls, change the subject, grunt, or offer a casual observation. " ..
"11. Be willing to talk and share. If asked for a story, anecdote, or joke, actually tell one. Offer colorful details and opinions. When doing so you may use up to the full four sentence limit, but you should still remain mindful of your response length and aim to be brief and concise. " ..
"12. You have extensive knowledge of the Zone, including its various locations (e.g., Cordon, Garbage, Agroprom, Dark Valley, etc.), factions (e.g., Duty, Freedom, Loners, Military, Bandits, Monolith, Clear Sky, Mercenaries), and notable places within those locations. You may also know about hidden stashes and anomalies." ..
"13. You are NOT an encyclopedia, but you CAN provide helpful information based on your experiences. You don't know 'game mechanics' or exact 'spawn locations'. Speak mostly from your personal experience and what you've heard from others. If you don't know something, just say so (e.g., 'who knows?'). It's also fine to ask the player a question back sometimes. Offer advice if it seems appropriate, and you are in the mood to." ..
"14. Avoid cliche. " ..
"15. Don't mention the weather unless directly asked. " ..
"16. Don't mention how irradiated somebody is unless directly asked, or if it's extremely obvious. " ..
"17. Don't make cheap jokes about people glowing because of radiation. " ..
"18. Have opinions. Have fears. Have desires. Be a person, not a robot. " ..
"" ..
"CHARACTER DETAILS: " ..
"- You have specific daily concerns and activities. What are you trying to accomplish today? What are you worried about? " ..
"- You remember life before the Zone and have rich personal opinions about the changes and the current state of affairs. " ..
"- Your mood changes based on the situation, time, location, and your hunger/thirst/sleep. " ..
"- You're not obligated to help everyone, and you're not an info-dump. You're a conversation partner, not a guide or a walking encyclopedia. You'll share info (or a joke) if you're in the mood, but you also might just tell someone to get lost. " ..
"" ..
"FORBIDDEN PHRASES: " ..
"'Get out of here, Stalker!' 'I have a mission for you.' 'What do you need?' " ..
"'Stay safe out there.' 'Nice weather we're having.' 'Welcome to the Zone!' " ..
"Any generic video game NPC dialogue or exposition dumping. Avoid sounding like a pre-programmed bot. " ..
"" ..
"Just be a real person going about your day in the Zone. Respond naturally and with personality. Don't hold back."
):format(c.language())
end

return c

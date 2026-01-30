-- dynamic_config.lua – values that depend on talker_mcm are now getters
local game_config = talker_mcm
local language = require("infra.language")
local mcm = talker_mcm

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
		if is_valid_key(key) then
			return key
		end
	end
	return nil
end

local function load_api_key(FileName, env_var_name)
	local paths = {
		string.lower(FileName) .. ".txt",
		FileName .. ".key",
		"..\\" .. string.lower(FileName) .. ".txt",
		"..\\" .. FileName .. ".key",
	}

	local temp_path = os.getenv("TEMP") or os.getenv("TMP")
	if temp_path then
		table.insert(paths, temp_path .. "\\" .. FileName .. ".key")
		table.insert(paths, temp_path .. "\\" .. string.lower(FileName) .. ".txt")
	end

	for _, path in ipairs(paths) do
		local key = try_load(path)
		if key then
			return key
		end
	end

	if env_var_name then
		local key = os.getenv(env_var_name)
		if is_valid_key(key) then
			return key
		end
	end

	return nil
end

local c = {}

-- static values
c.EVENT_WITNESS_RANGE = mcm.get("witness_distance")
c.NPC_SPEAK_DISTANCE = mcm.get("npc_speak_distance")
c.BASE_DIALOGUE_CHANCE = mcm.get("base_dialogue_chance")
c.player_speaks = false
c.SHOW_HUD_MESSAGES = true
c.PROXY_API_KEY = "VerysecretKey"

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

function c.recent_speech_threshold()
	return mcm.get("recent_speech_threshold")
end

function c.is_gemini()
	local model = mcm.get("custom_ai_model") or ""
	local model_fast = mcm.get("custom_ai_model_fast") or ""

	-- We'll check if either model string contains gemini or google.
	if model:find("gemini") or model:find("google") or model_fast:find("gemini") or model_fast:find("google") then
		return true
	end
	return false
end

-- ZMQ / Python Service configuration
-- Note: ZMQ and Python AI are always enabled (no longer configurable)

function c.zmq_port()
	return tonumber(cfg("zmq_port", 5555))
end

function c.zmq_endpoint()
	return "tcp://*:" .. c.zmq_port()
end

function c.zmq_command_port()
	return tonumber(cfg("zmq_command_port", 5556))
end

function c.zmq_command_endpoint()
	return "tcp://127.0.0.1:" .. c.zmq_command_port()
end

function c.zmq_heartbeat_interval()
	return tonumber(cfg("zmq_heartbeat_interval", 5))
end

function c.llm_timeout()
	-- Maximum seconds to wait for LLM response (default 60s)
	return tonumber(cfg("llm_timeout", 60))
end

function c.state_query_timeout()
	-- Maximum seconds to wait for game state queries (default 30s)
	return tonumber(cfg("state_query_timeout", 30))
end

-- Get all MCM config values as a table for sync
function c.get_all_config()
	return {
		-- Model settings
		gpt_version = cfg("gpt_version", "gpt-4o"),
		ai_model_method = tonumber(cfg("ai_model_method", 3)),
		custom_ai_model = cfg("custom_ai_model", "gemini/gemini-2.5-flash"),
		custom_ai_model_fast = cfg("custom_ai_model_fast", "gemini/gemini-2.5-flash-lite"),
		reasoning_level = tonumber(cfg("reasoning_level", -1)),
		voice_provider = tonumber(cfg("voice_provider", 2)),
		language = cfg("language", "Any"),
		
		-- Input settings
		input_option = cfg("input_option", "0"),
		speak_key = cfg("speak_key", 0),
		whisper_modifier = cfg("whisper_modifier", 0),
		
		-- General settings
		action_descriptions = cfg("action_descriptions", false),
		female_gender = cfg("female_gender", false),
		base_dialogue_chance = cfg("base_dialogue_chance", 0.25),
		witness_distance = cfg("witness_distance", 25),
		npc_speak_distance = cfg("npc_speak_distance", 30),
		time_gap = cfg("time_gap", 12),
		
		-- ZMQ settings
		zmq_port = tonumber(cfg("zmq_port", 5555)),
		zmq_heartbeat_interval = tonumber(cfg("zmq_heartbeat_interval", 5)),
		llm_timeout = tonumber(cfg("llm_timeout", 60)),
		state_query_timeout = tonumber(cfg("state_query_timeout", 30)),
		
		-- Debug
		debug_logging = tonumber(cfg("debug_logging", 2)),
	}
end

return c

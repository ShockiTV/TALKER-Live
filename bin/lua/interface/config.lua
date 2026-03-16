-- config.lua – configuration values backed by MCM, with defaults fallback
local engine = require("interface.engine")
local defaults = require("interface.config_defaults")
local language = require("infra.language")

-- helper: read from MCM via engine facade, fall back to defaults table
local function cfg(key)
	local val = engine.get_mcm_value(key)
	if val == nil then
		val = defaults[key]
	end
	return val
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
c.EVENT_WITNESS_RANGE  = cfg("witness_distance")
c.NPC_SPEAK_DISTANCE   = cfg("npc_speak_distance")
c.player_speaks = false
c.SHOW_HUD_MESSAGES = true
c.PROXY_API_KEY = "VerysecretKey"

--- Public generic getter for any MCM key (dynamic read).
-- Used by domain/service/chance.lua and trigger scripts.
-- @param key  string  MCM key (e.g. "triggers/death/chance_player")
-- @return any  The config value, with defaults fallback
function c.get(key)
	return cfg(key)
end

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
	return cfg("input_option") == "0"
end

function c.speak_key()
	return cfg("speak_key")
end

function c.modelmethod()
	return tonumber(cfg("ai_model_method"))
end

function c.voice_provider()
	return tonumber(cfg("voice_provider"))
end

function c.custom_dialogue_model()
	return cfg("custom_ai_model")
end

function c.custom_dialogue_model_fast()
	return cfg("custom_ai_model_fast")
end

function c.reasoning_level()
	return tonumber(cfg("reasoning_level"))
end

function c.language()
	return cfg("language") or DEFAULT_LANGUAGE
end

function c.language_short()
	return language.to_short(c.language())
end

function c.dialogue_model()
	return cfg("gpt_version")
end

function c.recent_speech_threshold()
	return cfg("recent_speech_threshold")
end

function c.is_gemini()
	local model = cfg("custom_ai_model") or ""
	local model_fast = cfg("custom_ai_model_fast") or ""
	if model:find("gemini") or model:find("google") or model_fast:find("gemini") or model_fast:find("google") then
		return true
	end
	return false
end

-- Speaker picker

function c.speaker_pick_max_events()
	return tonumber(cfg("speaker_pick_max_events")) or 20
end

-- WebSocket / Python Service configuration

function c.ws_host()
	return cfg("ws_host") or "127.0.0.1"
end

function c.service_ws_port()
	return tonumber(cfg("service_ws_port"))
end

function c.ws_token()
	return cfg("ws_token") or ""
end

function c.ws_bearer_token()
	return cfg("ws_bearer_token") or ""
end

function c.service_url()
	return cfg("service_url") or "wss://talker-live.duckdns.org/ws"
end

function c.llm_timeout()
	-- Maximum seconds to wait for LLM response (default 60s)
	return tonumber(cfg("llm_timeout"))
end

function c.state_query_timeout()
	-- Maximum seconds to wait for game state queries (default 30s)
	return tonumber(cfg("state_query_timeout"))
end

function c.tts_volume_boost()
	return tonumber(cfg("tts_volume_boost")) or 8.0
end

function c.max_log_entries_per_level()
	return tonumber(cfg("max_log_entries_per_level"))
end

-- Get all MCM config values as a table for sync
function c.get_all_config()
	return {
		-- Model settings
		gpt_version             = cfg("gpt_version"),
		ai_model_method         = tonumber(cfg("ai_model_method")),
		custom_ai_model         = cfg("custom_ai_model"),
		custom_ai_model_fast    = cfg("custom_ai_model_fast"),
		reasoning_level         = tonumber(cfg("reasoning_level")),
		voice_provider          = tonumber(cfg("voice_provider")),
		language                = cfg("language"),

		-- Input settings
		input_option            = cfg("input_option"),
		speak_key               = cfg("speak_key"),
		whisper_modifier        = cfg("whisper_modifier"),

		-- General settings
		action_descriptions     = cfg("action_descriptions"),
		female_gender           = cfg("female_gender"),
		witness_distance        = cfg("witness_distance"),
		npc_speak_distance      = cfg("npc_speak_distance"),
		time_gap                = cfg("time_gap"),

		-- Speaker picker
		speaker_pick_max_events = tonumber(cfg("speaker_pick_max_events")),

		-- WebSocket settings
		ws_host                 = cfg("ws_host"),
		service_url             = cfg("service_url"),
		ws_token                = cfg("ws_token"),
		ws_bearer_token         = cfg("ws_bearer_token"),
		llm_timeout             = tonumber(cfg("llm_timeout")),
		state_query_timeout     = tonumber(cfg("state_query_timeout")),

		-- TTS
		tts_volume_boost        = tonumber(cfg("tts_volume_boost")),

		-- Debug
		debug_logging           = tonumber(cfg("debug_logging")),
	}
end

return c

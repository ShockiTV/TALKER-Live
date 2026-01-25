-- proxy.lua
local http = require("infra.HTTP.HTTP")
local json = require("infra.HTTP.json")
local log = require("framework.logger")
local config = require("interface.config")

local proxy = {}

-- model registry
local MODEL = {
	smart = config.custom_dialogue_model(),
	mid = config.custom_dialogue_model(),
	fast = config.custom_dialogue_model_fast(),
	fine_dialog = config.custom_dialogue_model(),
	fine_speaker = config.custom_dialogue_model(),
}

-- sampling presets
local PRESET = {
	creative = { temperature = 0.9, top_p = 1, frequency_penalty = 0, presence_penalty = 0 },
	strict = { temperature = 0.0, top_p = 1, frequency_penalty = 0, presence_penalty = 0 },
}

-- helpers --------------------------------------------------------------
local API_URL = "http://127.0.0.1:8000/v1/chat/completions"
local API_KEY = config.PROXY_API_KEY

local function build_body(messages, opts)
	opts = opts or PRESET.creative
	local reasoning_level = config.reasoning_level()

	local body = {
		model = opts.model or MODEL.smart,
		messages = messages, -- plain Lua table
		temperature = opts.temperature,
		top_p = opts.top_p,
		max_tokens = opts.max_tokens,
		frequency_penalty = opts.frequency_penalty,
		presence_penalty = opts.presence_penalty,
	}

	-- Only enable reasoning if max_tokens is sufficient (e.g. > 100)
	-- Short tasks like pick_speaker (max_tokens=30) crash with thinking enabled.
	if not opts.max_tokens or opts.max_tokens >= 100 then
		if reasoning_level == -1 then
			body.thinking = {
				type = "enabled",
				budget_tokens = -1,
			}
		else
			local reasoning_map = {
				[0] = "disable",
				[1] = "low",
				[2] = "medium",
				[3] = "high",
			}
			body.reasoning_effort = reasoning_map[reasoning_level]
		end
	end

	return body
end

local function send(messages, cb, opts)
	assert(type(cb) == "function", "callback required")

	local headers = {
		["Content-Type"] = "application/json",
		["Authorization"] = "Bearer " .. API_KEY,
	}

	local body_tbl = build_body(messages, opts)
	log.http("PROXY request: %s", json.encode(body_tbl)) -- encode only for log

	return http.send_async_request(API_URL, "POST", headers, body_tbl, function(resp, err)
		if resp and resp.error then
			err = resp.error
		end

		if err then
			log.error("PROXY error: " .. tostring(err) .. " Body: " .. json.encode(resp))
			cb(nil)
			return
		end

		if not resp or not resp.choices then
			log.error("PROXY invalid response (no choices): " .. json.encode(resp))
			cb(nil)
			return
		end

		local answer = resp.choices[1] and resp.choices[1].message
		log.debug("PROXY response: %s", answer and answer.content or "empty")
		cb(answer and answer.content)
	end)
end

-- public shortcuts -----------------------------------------------------
function proxy.generate_dialogue(msgs, cb)
	return send(msgs, cb, PRESET.creative)
end

function proxy.pick_speaker(msgs, cb)
	return send(msgs, cb, { model = MODEL.fast, temperature = 0.0, max_tokens = 30 })
end

function proxy.summarize_story(msgs, cb)
	return send(msgs, cb, { model = MODEL.fast, temperature = 0.2, max_tokens = 2500 })
end

return proxy

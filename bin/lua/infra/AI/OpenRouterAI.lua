-- OpenRouterAI.lua
local http   = require("infra.HTTP.HTTP")
local json   = require("infra.HTTP.json")
local log    = require("framework.logger")
local config = require("interface.config")

local openrouter = {}

-- model registry
local MODEL = {
  smart        = config.custom_dialogue_model(),
  mid          = "deepseek/deepseek-chat-v3-0324",
  fast         = "deepseek/deepseek-chat-v3-0324",
  fine_dialog  = "deepseek/deepseek-chat-v3-0324",
  fine_speaker = "deepseek/deepseek-chat-v3-0324",
}

-- sampling presets
local PRESET = {
  creative = {temperature=0.9 ,max_tokens=150,top_p=1,frequency_penalty=0,presence_penalty=0},
  strict   = {temperature=0.0 ,max_tokens=150,top_p=1,frequency_penalty=0,presence_penalty=0},
}

-- helpers --------------------------------------------------------------
local API_URL = "https://openrouter.ai/api/v1/chat/completions"
local API_KEY = config.OPENROUTER_API_KEY

local function build_body(messages, opts)
  opts = opts or PRESET.creative
  return {
    model             = opts.model or MODEL.smart,
    messages          = messages,           -- plain Lua table
    temperature       = opts.temperature,
    top_p             = opts.top_p,
    max_tokens        = opts.max_tokens,
    frequency_penalty = opts.frequency_penalty,
    presence_penalty  = opts.presence_penalty,
  }
end



local function send(messages, cb, opts)
  assert(type(cb)=="function","callback required")

  local headers = {
    ["Content-Type"]  = "application/json",
    ["Authorization"] = "Bearer "..API_KEY,
  }

  local body_tbl = build_body(messages, opts)
  log.http("OPENROUTER request: %s", json.encode(body_tbl)) -- encode only for log

  return http.send_async_request(API_URL, "POST", headers, body_tbl, function(resp, err)
    if resp and resp.error then
        err = resp.error
    end 
    if err or (resp and resp.error) then
      log.error("OPENROUTER error: error:" .. json.encode(err or "no-err") .. " body:" .. json.encode(resp))
      error("OPENROUTER error: error:" ..  json.encode(err or "no-err")  .. " body:" .. json.encode(resp))
    end
    local answer = resp.choices and resp.choices[1] and resp.choices[1].message
    log.debug("OPENROUTER response: %s", answer and answer.content)
    cb(answer and answer.content)
  end)
end

-- public shortcuts -----------------------------------------------------
function openrouter.generate_dialogue(msgs, cb)
  return send(msgs, cb, PRESET.creative)
end

function openrouter.pick_speaker(msgs, cb)
  return send(msgs, cb, {model=MODEL.fast, temperature=0.0, max_tokens=30})
end

function openrouter.summarize_story(msgs, cb)
  return send(msgs, cb, {model=MODEL.fast, temperature=0.2, max_tokens=100})
end

return openrouter

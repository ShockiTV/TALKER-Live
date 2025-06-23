-- gpt.lua
local http   = require("infra.HTTP.HTTP")
local json   = require("infra.HTTP.json")
local log    = require("framework.logger")
local config = require("interface.config")

local gpt = {}

-- model registry
local MODEL = {
  smart        = config.dialogue_model(),
  mid          = "gpt-4o",
  fast         = "gpt-4o-mini",
  -- fine tuned models, sadly will only work for my account
  fine_dialog  = "ft:gpt-4o-2024-08-06:personal::A721Jmn6",
  fine_speaker = "ft:gpt-4o-mini-2024-07-18:personal::A9ndhQlH",
}

-- sampling presets
local PRESET = {
  creative = {temperature=0.9 ,max_tokens=150,top_p=1,frequency_penalty=0,presence_penalty=0},
  strict   = {temperature=0.0 ,max_tokens=150,top_p=1,frequency_penalty=0,presence_penalty=0},
}

-- helpers --------------------------------------------------------------
local API_URL = "https://api.openai.com/v1/chat/completions"
local API_KEY = config.OPENAI_API_KEY

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

local function send(messages, callback, opts)
  assert(type(callback)=="function","callback required")

  local headers = {
    ["Content-Type"]  = "application/json",
    ["Authorization"] = "Bearer "..API_KEY,
  }

  local body_tbl = build_body(messages, opts)
  log.http("GPT request: %s", json.encode(body_tbl)) -- encode only for log

  return http.send_async_request(API_URL, "POST", headers, body_tbl, function(resp, err)
    if resp and resp.error then
        err = resp.error
    end
    if err or (resp and resp.error) then
      local err_str = type(err) == "table" and json.encode(err) or tostring(err)
      log.error("gpt error: error:" .. err_str .. " body:" .. json.encode(resp))
      error("gpt error: error:" .. err_str .. " body:" .. json.encode(resp))
    end
    local answer = resp.choices and resp.choices[1] and resp.choices[1].message
    log.debug("GPT response: %s", answer and answer.content)
    callback(answer and answer.content)
  end)
end

-- public shortcuts -----------------------------------------------------
function gpt.generate_dialogue(msgs, callback)
  return send(msgs, callback, PRESET.creative)
end

function gpt.pick_speaker(msgs, callback)
  return send(msgs, callback, {model=MODEL.fast, temperature=0.0, max_tokens=30})
end

function gpt.summarize_story(msgs, callback)
  return send(msgs, callback, {model=MODEL.fast, temperature=0.2, max_tokens=100})
end

return gpt

-- ollama.lua
local http   = require("infra.HTTP.HTTP")
local json   = require("infra.HTTP.json")
local log    = require("framework.logger")
local config = require("interface.config")

local ollama = {}

-- ollama models
local DEEPSEEK_FAST = "deepseek-r1:1.5b"
local DEEPSEEK_MID = "deepseek-r1:7b"
local DEEPSEEK_SMART = "deepseek-r1:32b"

local NEMO = "nemotron-mini:4b"

local LLAMA = "llama3.2"
local LLAMA_small="llama3.2:1b"

-- model registry
local MODEL = {
  smart = LLAMA,
  fast  = LLAMA_small
}

-- sampling presets
local PRESET = {
  creative = {temperature=0.9 ,max_tokens=150,top_p=1,frequency_penalty=0,presence_penalty=0},
  strict   = {temperature=0.0 ,max_tokens=150,top_p=1,frequency_penalty=0,presence_penalty=0},
}

-- helpers --------------------------------------------------------------
local API_URL = config.OLLAMA_URL or "http://localhost:11434/api/chat"

local function build_body(messages, opts)
  opts = opts or PRESET.creative
  return {
    model    = opts.model or MODEL.smart,
    messages = messages,
    stream   = false,
    options  = {
      temperature       = opts.temperature,
      top_p             = opts.top_p,
      num_predict       = opts.max_tokens,
      repeat_penalty    = opts.frequency_penalty,
      presence_penalty  = opts.presence_penalty,
    },
  }
end

local function send(messages, callback, opts)
  assert(type(callback)=="function","callback required")

  local headers = {["Content-Type"] = "application/json"}
  local body_tbl = build_body(messages, opts)
  log.http("Ollama request: %s", json.encode(body_tbl))

  return http.send_async_request(API_URL, "POST", headers, body_tbl, function(resp, err)
    if err or (resp and resp.error) then
      local err_str = type(err)=="table" and json.encode(err) or tostring(err)
      log.error("ollama error: error:" .. err_str .. " body:" .. json.encode(resp))
      error("ollama error: error:" .. err_str .. " body:" .. json.encode(resp))
    end
    local answer = resp and resp.message and resp.message.content
    log.debug("Ollama response: %s", answer)
    callback(answer)
  end)

end

-- public shortcuts -----------------------------------------------------
function ollama.generate_dialogue(msgs, callback)
  return send(msgs, callback, PRESET.creative)
end

function ollama.pick_speaker(msgs, callback)
  return send(msgs, callback, {model=MODEL.fast, temperature=0.0, max_tokens=30})
end

function ollama.summarize_story(msgs, callback)
  return send(msgs, callback, {model=MODEL.fast, temperature=0.2, max_tokens=100})
end

return ollama

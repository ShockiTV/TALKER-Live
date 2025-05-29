-- infra/HTTP/http_module.lua  – uses pollnet’s built-in JSON encoder
local pollnet   = require("infra.HTTP.pollnet")
local json      = require("infra.HTTP.json")
local logger    = require("framework.logger")
local game_adp  = require("infra.game_adapter")

local M = {}

M.CHECK_INTERVAL_S = 0.1

local handlers = {} 

-- util -----------------------------------------------------------------
local function id() return tostring(math.random(1000000, 9999999)) end

-- request --------------------------------------------------------------
function M.send_request(url, method, headers, body_tbl)
  local rid = id()
  handlers[rid] = {}

  local ok, sock
  if method:upper() == "POST" then
    -- body_tbl = utf8_tbl(body_tbl)
    -- encode to JSON
    body = json.encode(body_tbl)
    body = json.convert_to_utf8(body)

    logger.http("HTTP body: %s", json.encode(body))

    ok, sock = pcall(pollnet.http_post, url, headers, body, true) -- true = “please JSON-encode this table”
  elseif method:upper() == "GET" then
    ok, sock = pcall(pollnet.http_get,  url, headers, true)
  else
    handlers[rid].error = "Unsupported HTTP method: "..method
    return rid, handlers[rid].error
  end

  if not ok or not sock then
    handlers[rid].error = "Failed to open socket: "..(sock or "unknown")
    return rid, handlers[rid].error
  end

  handlers[rid].socket = sock
  return rid
end

-- poll ---------------------------------------------------------------
function M.check_response(rid)
  local h = handlers[rid] or {}
  if h.error        then return nil, h.error end
  if not h.socket   then return nil, "No socket for rid "..rid end

  if h.socket:poll() then
    local raw = h.socket:last_message()
    if raw then
      local ok, decoded = pcall(json.decode, raw)
      h.socket:close(); h.socket = nil
      if ok then
        h.response = decoded
        return h.response
      else
        h.error = "JSON decode failed"
        logger.error(h.error .. ". raw: " .. raw)
        return nil, h.error
      end
    end
  end
  return false -- not ready yet
end

-- async wrapper --------------------------------------------------------
function M.send_async_request(url, method, headers, body_tbl, cb)
  local rid = M.send_request(url, method, headers, body_tbl)

  local function waiter()
    local resp, err = M.check_response(rid)
    if resp or err then
      cb(resp, err, rid)
      return true
    end
    return false
  end

  game_adp.repeat_until_true(M.CHECK_INTERVAL_S, waiter)
  return rid
end

return M

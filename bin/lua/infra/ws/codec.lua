-- infra/ws/codec.lua
-- JSON envelope encode/decode for the WebSocket wire format.
-- Envelope: { t = topic, p = payload, r = request_id (optional), ts = timestamp }
--
-- Pure module — no I/O, no game dependencies (except json for serialisation).

local json = require("infra.HTTP.json")

local M = {}

--- Encode a message envelope to a JSON string.
-- @param t  string        Topic (required)
-- @param p  table|nil     Payload (defaults to empty table)
-- @param r  string|nil    Request ID (omitted from output when nil)
-- @return   string        JSON-encoded envelope
function M.encode(t, p, r)
    local envelope = {
        t  = t,
        p  = p or {},
        ts = os.time() * 1000,  -- milliseconds (integer)
    }
    if r then
        envelope.r = r
    end
    return json.encode(envelope)
end

--- Decode a raw JSON string into an envelope table.
-- @param raw  string    Raw JSON string
-- @return table|nil     { t, p, r, ts } on success, nil on failure
-- @return string|nil    Error message on failure
function M.decode(raw)
    if type(raw) ~= "string" or raw == "" then
        return nil, "empty or non-string input"
    end

    local ok, data = pcall(json.decode, raw)
    if not ok or type(data) ~= "table" then
        return nil, "invalid JSON"
    end

    if not data.t or type(data.t) ~= "string" then
        return nil, "missing or invalid 't' field"
    end

    return {
        t  = data.t,
        p  = data.p or {},
        r  = data.r,   -- may be nil
        ts = data.ts,   -- may be nil
    }
end

return M

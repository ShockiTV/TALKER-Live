-- infra/ws/client.lua
-- Thin WebSocket connection wrapper over pollnet.
-- Provides: open, send, poll, status, close.
-- Injectable socket factory for testability — tests inject a mock,
-- production uses pollnet.open_ws.
--
-- Zero engine dependencies.  Requires only pollnet (or mock).

local log = require("framework.logger")

local M = {}

-- ── Socket factory ───────────────────────────────────────────────────────────

local _socket_factory = nil -- lazily resolved to pollnet.open_ws

--- Inject a custom socket factory (for tests).
-- The factory signature is: factory(url) → Socket-like object with
--   :poll()   → (ok: bool, msg: string|nil)
--   :send(msg)
--   :close()
--   :status() → string ("open"|"opening"|"closed"|"error"|"invalid"|"unpolled")
-- @param factory  function(url) → socket, or nil to reset to default
function M.set_socket_factory(factory)
    _socket_factory = factory
end

--- Resolve the active socket factory.  Falls back to pollnet.open_ws
-- at first call — deferred so that tests can inject before pollnet loads.
local function get_factory()
    if _socket_factory then return _socket_factory end
    -- Attempt to load pollnet — available when running inside the game
    local ok, pollnet = pcall(require, "infra.HTTP.pollnet")
    if ok and pollnet and pollnet.open_ws then
        _socket_factory = pollnet.open_ws
        return _socket_factory
    end
    log.error("No socket factory set and pollnet is not available")
    return nil
end

-- ── Handle tracking ──────────────────────────────────────────────────────────
-- Stores the raw pollnet Socket objects by an integer handle id.
-- This avoids leaking the pollnet cdata type into the channel layer.

local _next_id = 1
local _sockets = {} -- id → pollnet Socket

-- ── Public API ───────────────────────────────────────────────────────────────

--- Open a WebSocket connection.  Non-blocking — returns immediately.
-- @param url  string  The ws:// or wss:// URL to connect to.
-- @return handle  number|nil  Opaque integer handle, or nil on failure.
function M.open(url)
    if type(url) ~= "string" or url == "" then
        log.error("ws_client.open: invalid URL")
        return nil
    end

    local factory = get_factory()
    if not factory then return nil end

    local sock = factory(url)
    if not sock then
        log.error("ws_client.open: factory returned nil for %s", url)
        return nil
    end

    local id = _next_id
    _next_id = _next_id + 1
    _sockets[id] = sock
    return id
end

--- Send a string message on an open connection.
-- @param handle  number  Handle from open()
-- @param message string  Raw message string
-- @return ok     boolean  true if sent, false on invalid handle
function M.send(handle, message)
    local sock = _sockets[handle]
    if not sock then return false end

    local ok, err = pcall(function() sock:send(message) end)
    if not ok then
        log.error("ws_client.send failed: %s", tostring(err))
        return false
    end
    return true
end

--- Poll for one incoming message (non-blocking).
-- @param handle  number  Handle from open()
-- @return message string|nil  The message string, or nil if nothing ready.
function M.poll(handle)
    local sock = _sockets[handle]
    if not sock then return nil end

    local ok, msg = sock:poll()
    if ok and msg then
        return msg
    end
    return nil
end

--- Query connection status.
-- @param handle  number  Handle from open()
-- @return status string  One of "connected", "connecting", "closed", "error"
function M.status(handle)
    local sock = _sockets[handle]
    if not sock then return "closed" end

    local raw = sock:status()
    -- Normalise pollnet status strings to the service-channel vocabulary
    if raw == "open" then return "connected" end
    if raw == "opening" then return "connecting" end
    if raw == "closed" then return "closed" end
    if raw == "error" then return "error" end
    if raw == "invalid" then return "closed" end
    if raw == "unpolled" then return "connecting" end
    return "error"
end

--- Close the connection and release the handle.
-- Subsequent calls with the same handle are no-ops.
-- @param handle  number  Handle from open()
function M.close(handle)
    local sock = _sockets[handle]
    if not sock then return end

    pcall(function() sock:close() end)
    _sockets[handle] = nil
end

--- Reset internal state (for tests).
function M._reset()
    _sockets = {}
    _next_id = 1
    _socket_factory = nil
end

return M

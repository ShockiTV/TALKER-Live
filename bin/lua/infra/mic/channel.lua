-- infra/mic/channel.lua
-- Mic communication channel over WebSocket — thin variant of service-channel.
-- Session-scoped handler registration with auto-cleanup on mic.result.
-- Independent lifecycle from the service channel.

local log       = require("framework.logger")
local ws_client = require("infra.ws.client")
local codec     = require("infra.ws.codec")

local M = {}

-- ── Constants ────────────────────────────────────────────────────────────────

local MAX_QUEUE_SIZE        = 50
local MAX_MESSAGES_PER_TICK = 10
local BACKOFF_BASE          = 1.0
local BACKOFF_CAP           = 30.0
local BACKOFF_JITTER        = 0.20

-- ── States ───────────────────────────────────────────────────────────────────

local STATE = {
    DISCONNECTED = "disconnected",
    CONNECTING   = "connecting",
    CONNECTED    = "connected",
    RECONNECTING = "reconnecting",
}

-- ── Internal state ───────────────────────────────────────────────────────────

local _state            = STATE.DISCONNECTED
local _url              = nil
local _handle           = nil
local _queue            = {}
local _on_status        = nil  -- session handler for mic.status
local _on_result        = nil  -- session handler for mic.result
local _handlers         = {}   -- topic → { fn, fn, ... } (general handlers, like service-channel)
local _backoff_attempt  = 0
local _backoff_deadline = 0
local _initialized      = false

-- ── Backoff ──────────────────────────────────────────────────────────────────

local function calculate_backoff(attempt)
    local base = BACKOFF_BASE * (2 ^ attempt)
    if base > BACKOFF_CAP then base = BACKOFF_CAP end
    local jitter = base * BACKOFF_JITTER * (2 * math.random() - 1)
    return base + jitter
end

-- ── Queue ────────────────────────────────────────────────────────────────────

local function enqueue(encoded_msg)
    table.insert(_queue, encoded_msg)
    while #_queue > MAX_QUEUE_SIZE do
        table.remove(_queue, 1)
    end
end

local function flush_queue()
    local flushed = _queue
    _queue = {}
    for _, msg in ipairs(flushed) do
        ws_client.send(_handle, msg)
    end
end

-- ── Dispatch ─────────────────────────────────────────────────────────────────

local function dispatch(envelope)
    local topic = envelope.t

    -- Session-scoped handlers (mic.status and mic.result)
    if topic == "mic.result" and _on_result then
        local fn = _on_result
        -- Auto-cleanup: clear session handlers before calling
        _on_status = nil
        _on_result = nil
        pcall(fn, envelope.p)
        return
    end

    if topic == "mic.status" and _on_status then
        pcall(_on_status, envelope.p)
        return
    end

    -- General topic handlers
    local handlers = _handlers[topic]
    if handlers then
        for _, fn in ipairs(handlers) do
            pcall(fn, envelope.p)
        end
    end
end

-- ── Drain ────────────────────────────────────────────────────────────────────

local function drain_messages()
    if not _handle then return end
    for _ = 1, MAX_MESSAGES_PER_TICK do
        local raw = ws_client.poll(_handle)
        if not raw then break end
        local envelope, err = codec.decode(raw)
        if envelope then
            dispatch(envelope)
        else
            log.warn("mic_channel: malformed message: %s", tostring(err))
        end
    end
end

-- ── Public API ───────────────────────────────────────────────────────────────

--- Initialize the mic channel with a target URL.
-- @param url  string  WebSocket URL (e.g. "ws://localhost:5558")
function M.init(url)
    if _handle then
        ws_client.close(_handle)
        _handle = nil
    end
    _url             = url
    _state           = STATE.DISCONNECTED
    _queue           = {}
    _on_status       = nil
    _on_result       = nil
    _handlers        = {}
    _backoff_attempt = 0
    _backoff_deadline = 0
    _initialized     = true
end

--- Drive the connection lifecycle. Call once per game tick.
function M.tick()
    if not _initialized then return end

    if _state == STATE.DISCONNECTED then
        _handle = ws_client.open(_url)
        if _handle then
            _state = STATE.CONNECTING
        end

    elseif _state == STATE.CONNECTING then
        -- Poll to drive the handshake (pollnet needs poll() to advance state)
        drain_messages()
        local status = ws_client.status(_handle)
        if status == "connected" then
            _state = STATE.CONNECTED
            flush_queue()
            _backoff_attempt = 0
        elseif status == "closed" or status == "error" then
            _state = STATE.RECONNECTING
            _backoff_deadline = os.clock() + calculate_backoff(_backoff_attempt)
            _backoff_attempt = _backoff_attempt + 1
        end

    elseif _state == STATE.CONNECTED then
        drain_messages()
        local status = ws_client.status(_handle)
        if status == "closed" or status == "error" then
            _state = STATE.RECONNECTING
            _backoff_deadline = os.clock() + calculate_backoff(_backoff_attempt)
            _backoff_attempt = _backoff_attempt + 1
        end

    elseif _state == STATE.RECONNECTING then
        if os.clock() >= _backoff_deadline then
            if _handle then
                ws_client.close(_handle)
                _handle = nil
            end
            _handle = ws_client.open(_url)
            if _handle then
                _state = STATE.CONNECTING
            end
        end
    end
end

--- Register session-scoped handlers for one recording session.
-- Clears any previous session handlers before registering new ones.
-- @param on_status  function  Handler for mic.status messages: fn(payload)
-- @param on_result  function  Handler for mic.result messages: fn(payload)
function M.start_session(on_status, on_result)
    _on_status = on_status
    _on_result = on_result
end

--- Register a general handler for a topic (non-session-scoped).
-- @param topic  string    Topic
-- @param fn     function  Handler: fn(payload)
function M.on(topic, fn)
    if not _handlers[topic] then
        _handlers[topic] = {}
    end
    table.insert(_handlers[topic], fn)
end

--- Publish a message to the mic service.
-- @param topic    string  Topic (e.g. "mic.start")
-- @param payload  table   Payload
function M.publish(topic, payload)
    local encoded = codec.encode(topic, payload)
    if _state == STATE.CONNECTED and _handle then
        ws_client.send(_handle, encoded)
    else
        enqueue(encoded)
    end
end

--- Close the connection and reset state.
function M.shutdown()
    if _handle then
        ws_client.close(_handle)
        _handle = nil
    end
    _state = STATE.DISCONNECTED
    _queue = {}
    _on_status = nil
    _on_result = nil
    _initialized = false
end

--- Get the current connection state.
-- @return string  "disconnected", "connecting", "connected", "reconnecting"
function M.get_status()
    return _state
end

-- ── Test helpers ─────────────────────────────────────────────────────────────

function M._reset()
    if _handle then pcall(ws_client.close, _handle) end
    _state            = STATE.DISCONNECTED
    _url              = nil
    _handle           = nil
    _queue            = {}
    _on_status        = nil
    _on_result        = nil
    _handlers         = {}
    _backoff_attempt  = 0
    _backoff_deadline = 0
    _initialized      = false
end

function M._queue_size()
    return #_queue
end

return M

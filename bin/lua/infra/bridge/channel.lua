-- infra/bridge/channel.lua
-- Unified communication channel over WebSocket to talker_bridge.
-- Combines service-channel features (request/response correlation,
-- on_reconnect callback) with mic-channel features (session-scoped
-- handlers for mic.status / mic.result).
--
-- State machine: DISCONNECTED → CONNECTING → CONNECTED → RECONNECTING
-- Handles outbound queue, exponential backoff, topic handlers, and
-- tick-based message drain.
--
-- All game traffic (events, config, dialogue, mic, TTS) flows through
-- this single connection to talker_bridge, which proxies to talker_service.

local log       = require("framework.logger")
local ws_client = require("infra.ws.client")
local codec     = require("infra.ws.codec")

local M = {}

-- ── Constants ────────────────────────────────────────────────────────────────

local MAX_QUEUE_SIZE        = 100
local MAX_MESSAGES_PER_TICK = 20
local BACKOFF_BASE          = 1.0   -- seconds
local BACKOFF_CAP           = 30.0  -- seconds
local BACKOFF_JITTER        = 0.20  -- ±20%

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
local _queue            = {}   -- outbound message queue (encoded strings)
local _handlers         = {}   -- topic → { fn, fn, ... }
local _pending          = {}   -- r → callback  (request/response correlation)
local _on_reconnect     = nil  -- callback
local _was_connected    = false
local _backoff_attempt  = 0
local _backoff_deadline = 0
local _initialized      = false

-- Session-scoped mic handlers (auto-cleaned on mic.result)
local _mic_on_status    = nil
local _mic_on_result    = nil

-- ── ID generation ────────────────────────────────────────────────────────────

local _id_counter = 0
local _generate_id

local function _default_generate_id()
    local ok, pollnet = pcall(require, "infra.HTTP.pollnet")
    if ok and pollnet and pollnet.nanoid then
        _generate_id = pollnet.nanoid
        return _generate_id()
    end
    _id_counter = _id_counter + 1
    return "req-" .. tostring(_id_counter)
end

_generate_id = _default_generate_id

-- ── Backoff calculation ──────────────────────────────────────────────────────

local function calculate_backoff(attempt)
    local base = BACKOFF_BASE * (2 ^ attempt)
    if base > BACKOFF_CAP then base = BACKOFF_CAP end
    local jitter = base * BACKOFF_JITTER * (2 * math.random() - 1)
    return base + jitter
end

-- ── Queue management ─────────────────────────────────────────────────────────

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

-- ── Message dispatch ─────────────────────────────────────────────────────────

local function dispatch(envelope)
    -- 1. Request/response correlation (r-field)
    if envelope.r and _pending[envelope.r] then
        local cb = _pending[envelope.r]
        _pending[envelope.r] = nil
        local ok, err = pcall(cb, envelope.p)
        if not ok then
            log.error("bridge_channel: request callback error for r=%s: %s",
                      tostring(envelope.r), tostring(err))
        end
        return
    end

    -- 2. Session-scoped mic handlers
    if envelope.t == "mic.result" and _mic_on_result then
        local fn = _mic_on_result
        _mic_on_status = nil
        _mic_on_result = nil
        pcall(fn, envelope.p)
        return
    end
    if envelope.t == "mic.status" and _mic_on_status then
        pcall(_mic_on_status, envelope.p)
        return
    end

    -- 3. General topic handlers
    local handlers = _handlers[envelope.t]
    if handlers then
        for _, fn in ipairs(handlers) do
            local ok, err = pcall(fn, envelope.p, envelope.r)
            if not ok then
                log.error("bridge_channel: handler error for topic %s: %s",
                          envelope.t, tostring(err))
            end
        end
    end
end

-- ── Drain loop ───────────────────────────────────────────────────────────────

local function drain_messages()
    if not _handle then return end
    for _ = 1, MAX_MESSAGES_PER_TICK do
        local raw = ws_client.poll(_handle)
        if not raw then break end
        local envelope, err = codec.decode(raw)
        if envelope then
            dispatch(envelope)
        else
            log.warn("bridge_channel: malformed message: %s", tostring(err))
        end
    end
end

-- ── Public API ───────────────────────────────────────────────────────────────

--- Initialize the channel with the bridge URL.
-- Resets all state. Call tick() to begin connecting.
-- @param url  string  WebSocket URL (e.g. "ws://localhost:5558/ws")
function M.init(url)
    if _handle then
        ws_client.close(_handle)
        _handle = nil
    end
    _url             = url
    _state           = STATE.DISCONNECTED
    _queue           = {}
    _handlers        = {}
    _pending         = {}
    _on_reconnect    = nil
    _was_connected   = false
    _mic_on_status   = nil
    _mic_on_result   = nil
    _backoff_attempt = 0
    _backoff_deadline = 0
    _initialized     = true
end

--- Drive the connection lifecycle.  Call once per game tick.
function M.tick()
    if not _initialized then return end

    if _state == STATE.DISCONNECTED then
        _handle = ws_client.open(_url)
        if _handle then
            _state = STATE.CONNECTING
        end

    elseif _state == STATE.CONNECTING then
        drain_messages()
        local status = ws_client.status(_handle)
        if status == "connected" then
            _state = STATE.CONNECTED
            flush_queue()
            if _was_connected and _on_reconnect then
                pcall(_on_reconnect)
            end
            _was_connected = true
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

--- Publish a message through the bridge.
-- If not connected, the message is queued (up to MAX_QUEUE_SIZE).
-- @param topic    string  Message topic (e.g. "game.event", "mic.start")
-- @param payload  table   Payload table
-- @param r        string  Optional request ID for response correlation
function M.publish(topic, payload, r)
    local encoded = codec.encode(topic, payload, r)
    if _state == STATE.CONNECTED and _handle then
        ws_client.send(_handle, encoded)
    else
        enqueue(encoded)
    end
end

--- Register a handler for incoming messages on a topic.
-- Multiple handlers per topic are supported.
-- @param topic  string    Topic to subscribe to
-- @param fn     function  Handler: fn(payload, request_id)
function M.on(topic, fn)
    if not _handlers[topic] then
        _handlers[topic] = {}
    end
    table.insert(_handlers[topic], fn)
end

--- Send a request and register a callback for the matching response.
-- The callback receives the response payload when a message with matching `r` arrives.
-- @param topic    string    Topic to publish
-- @param payload  table     Payload
-- @param callback function  fn(response_payload)
function M.request(topic, payload, callback)
    local r = _generate_id()
    _pending[r] = callback
    local encoded = codec.encode(topic, payload, r)
    if _state == STATE.CONNECTED and _handle then
        ws_client.send(_handle, encoded)
    else
        enqueue(encoded)
    end
end

--- Register session-scoped handlers for one recording session.
-- Clears any previous session handlers before registering new ones.
-- on_result auto-cleans up session handlers when mic.result is received.
-- @param on_status  function  Handler for mic.status: fn(payload)
-- @param on_result  function  Handler for mic.result: fn(payload)
function M.start_session(on_status, on_result)
    _mic_on_status = on_status
    _mic_on_result = on_result
end

--- Register a callback fired on reconnect (not first connect).
-- @param fn  function  Callback: fn()
function M.set_on_reconnect(fn)
    _on_reconnect = fn
end

--- Close the connection and reset state.
function M.shutdown()
    if _handle then
        ws_client.close(_handle)
        _handle = nil
    end
    _state = STATE.DISCONNECTED
    _queue = {}
    _pending = {}
    _mic_on_status = nil
    _mic_on_result = nil
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
    _handlers         = {}
    _pending          = {}
    _on_reconnect     = nil
    _was_connected    = false
    _mic_on_status    = nil
    _mic_on_result    = nil
    _backoff_attempt  = 0
    _backoff_deadline = 0
    _initialized      = false
    _id_counter       = 0
    _generate_id      = _default_generate_id
end

function M._queue_size()
    return #_queue
end

return M

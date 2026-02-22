-- ZeroMQ Bridge for TALKER Expanded
-- Provides ZMQ PUB socket for publishing events to Python service
-- Provides ZMQ SUB socket for receiving commands from Python service
--
-- Uses LuaJIT FFI to bind to libzmq.dll
-- Implements graceful degradation if ZMQ is unavailable

package.path = package.path .. ";./bin/lua/?.lua;"

local ffi = require("ffi")
local json = require("infra.HTTP.json")
local logger = require("framework.logger")

local bridge = {}

-- State
local zmq_lib = nil
local zmq_ctx = nil
local zmq_pub_socket = nil      -- For publishing events (PUB, bind :5555)
local zmq_sub_socket = nil      -- For receiving commands from talker_service (SUB, connect :5556)
local zmq_mic_sub_socket = nil  -- For receiving mic_python messages (SUB, connect :5557)
local is_available = false
local is_initialized = false

-- Connection status tracking for user notifications
local connection_status = {
    connected = false,           -- Currently connected to Python service
    last_successful_send = 0,    -- Timestamp of last successful send
    last_successful_recv = 0,    -- Timestamp of last successful receive
    initialization_time = 0,     -- When ZMQ was initialized (for timeout if no messages received)
    has_notified_disconnect = false,  -- Already showed disconnect HUD message
    has_notified_reconnect = false,   -- Shown reconnect message for current session
}

-- Command handlers table (topic -> function)
local command_handlers = {}

-- Configuration (can be overridden via init)
local config = {
    pub_endpoint      = "tcp://*:5555",           -- Lua PUB, Python SUB
    sub_endpoint      = "tcp://127.0.0.1:5556",   -- talker_service PUB, Lua SUB
    mic_sub_endpoint  = "tcp://127.0.0.1:5557",   -- mic_python PUB, Lua SUB
    enabled = true,
}

--------------------------------------------------------------------------------
-- FFI Definitions for libzmq
--------------------------------------------------------------------------------

ffi.cdef[[
    // Context
    void* zmq_ctx_new(void);
    int zmq_ctx_term(void* context);
    
    // Socket
    void* zmq_socket(void* context, int type);
    int zmq_close(void* socket);
    int zmq_bind(void* socket, const char* endpoint);
    int zmq_connect(void* socket, const char* endpoint);
    
    // Send/Receive
    int zmq_send(void* socket, const void* buf, size_t len, int flags);
    int zmq_recv(void* socket, void* buf, size_t len, int flags);
    
    // Options
    int zmq_setsockopt(void* socket, int option_name, const void* option_value, size_t option_len);
    
    // Error handling
    int zmq_errno(void);
    const char* zmq_strerror(int errnum);
]]

-- ZMQ constants
local ZMQ_PUB = 1
local ZMQ_SUB = 2
local ZMQ_DONTWAIT = 1
local ZMQ_SNDMORE = 2
local ZMQ_LINGER = 17
local ZMQ_SUBSCRIBE = 6
local ZMQ_RCVTIMEO = 27

-- ZMQ error codes
local EAGAIN = 11

--------------------------------------------------------------------------------
-- Internal Functions
--------------------------------------------------------------------------------

local function get_zmq_error()
    if not zmq_lib then return "ZMQ library not loaded" end
    local errno = zmq_lib.zmq_errno()
    local errstr = zmq_lib.zmq_strerror(errno)
    return ffi.string(errstr)
end

local function try_load_zmq()
    -- Try to load libzmq.dll from bin/pollnet/
    local paths = {
        "./pollnet/libzmq.dll",
        "./bin/pollnet/libzmq.dll",
        "./bin/pollnet/libzmq",
        "libzmq.dll",
        "libzmq",
    }
    
    for _, path in ipairs(paths) do
        local ok, lib = pcall(ffi.load, path)
        if ok then
            logger.info("ZMQ library loaded from: " .. path)
            return lib
        end
    end
    
    return nil
end

--- Create and configure the PUB socket.
local function init_pub_socket()
    zmq_pub_socket = zmq_lib.zmq_socket(zmq_ctx, ZMQ_PUB)
    if zmq_pub_socket == nil then
        logger.error("Failed to create ZMQ PUB socket: " .. get_zmq_error())
        return false
    end
    
    -- Set linger to 0 for fast shutdown
    local linger = ffi.new("int[1]", 0)
    zmq_lib.zmq_setsockopt(zmq_pub_socket, ZMQ_LINGER, linger, ffi.sizeof("int"))
    
    -- Bind socket
    local rc = zmq_lib.zmq_bind(zmq_pub_socket, config.pub_endpoint)
    if rc ~= 0 then
        logger.error("Failed to bind ZMQ PUB socket to " .. config.pub_endpoint .. ": " .. get_zmq_error())
        zmq_lib.zmq_close(zmq_pub_socket)
        zmq_pub_socket = nil
        return false
    end
    
    logger.info("ZMQ PUB socket bound to " .. config.pub_endpoint)
    return true
end

--- Create and configure the SUB socket for receiving commands.
local function init_sub_socket()
    zmq_sub_socket = zmq_lib.zmq_socket(zmq_ctx, ZMQ_SUB)
    if zmq_sub_socket == nil then
        logger.error("Failed to create ZMQ SUB socket: " .. get_zmq_error())
        return false
    end
    
    -- Set linger to 0 for fast shutdown
    local linger = ffi.new("int[1]", 0)
    zmq_lib.zmq_setsockopt(zmq_sub_socket, ZMQ_LINGER, linger, ffi.sizeof("int"))
    
    -- Subscribe to all topics (empty string = all)
    local rc = zmq_lib.zmq_setsockopt(zmq_sub_socket, ZMQ_SUBSCRIBE, "", 0)
    if rc ~= 0 then
        logger.error("Failed to set ZMQ SUB subscription: " .. get_zmq_error())
        zmq_lib.zmq_close(zmq_sub_socket)
        zmq_sub_socket = nil
        return false
    end
    
    -- Connect to Python PUB endpoint (note: connect, not bind)
    rc = zmq_lib.zmq_connect(zmq_sub_socket, config.sub_endpoint)
    if rc ~= 0 then
        logger.error("Failed to connect ZMQ SUB socket to " .. config.sub_endpoint .. ": " .. get_zmq_error())
        zmq_lib.zmq_close(zmq_sub_socket)
        zmq_sub_socket = nil
        return false
    end
    
    logger.info("ZMQ SUB socket connected to " .. config.sub_endpoint)
    return true
end

--- Create and configure the mic SUB socket for receiving mic_python messages.
local function init_mic_sub_socket()
    zmq_mic_sub_socket = zmq_lib.zmq_socket(zmq_ctx, ZMQ_SUB)
    if zmq_mic_sub_socket == nil then
        logger.error("Failed to create ZMQ mic SUB socket: " .. get_zmq_error())
        return false
    end

    -- Set linger to 0 for fast shutdown
    local linger = ffi.new("int[1]", 0)
    zmq_lib.zmq_setsockopt(zmq_mic_sub_socket, ZMQ_LINGER, linger, ffi.sizeof("int"))

    -- Subscribe to mic.* topics only
    local filter = "mic."
    local rc = zmq_lib.zmq_setsockopt(zmq_mic_sub_socket, ZMQ_SUBSCRIBE, filter, #filter)
    if rc ~= 0 then
        logger.error("Failed to set ZMQ mic SUB subscription: " .. get_zmq_error())
        zmq_lib.zmq_close(zmq_mic_sub_socket)
        zmq_mic_sub_socket = nil
        return false
    end

    -- Also subscribe to tts.* topics (mic_python publishes tts.started / tts.done)
    local tts_filter = "tts."
    zmq_lib.zmq_setsockopt(zmq_mic_sub_socket, ZMQ_SUBSCRIBE, tts_filter, #tts_filter)

    -- Connect to mic_python PUB endpoint
    rc = zmq_lib.zmq_connect(zmq_mic_sub_socket, config.mic_sub_endpoint)
    if rc ~= 0 then
        logger.error("Failed to connect ZMQ mic SUB socket to " .. config.mic_sub_endpoint .. ": " .. get_zmq_error())
        zmq_lib.zmq_close(zmq_mic_sub_socket)
        zmq_mic_sub_socket = nil
        return false
    end

    logger.info("ZMQ mic SUB socket connected to " .. config.mic_sub_endpoint)
    return true
end

--------------------------------------------------------------------------------
-- Public API
--------------------------------------------------------------------------------

--- Initialize the ZMQ bridge.
-- @param opts Optional configuration table with 'pub_endpoint', 'sub_endpoint', 'mic_sub_endpoint', 'enabled' fields
-- @return true if initialization successful, false otherwise
function bridge.init(opts)
    if is_initialized then
        logger.debug("ZMQ bridge already initialized")
        return is_available
    end
    
    is_initialized = true
    
    -- Apply options
    if opts then
        if opts.endpoint then config.pub_endpoint = opts.endpoint end  -- Legacy support
        if opts.pub_endpoint then config.pub_endpoint = opts.pub_endpoint end
        if opts.sub_endpoint then config.sub_endpoint = opts.sub_endpoint end
        if opts.mic_sub_endpoint then config.mic_sub_endpoint = opts.mic_sub_endpoint end
        if opts.enabled ~= nil then config.enabled = opts.enabled end
    end
    
    -- Check if enabled
    if not config.enabled then
        logger.info("ZMQ bridge disabled by configuration")
        is_available = false
        return false
    end
    
    -- Try to load ZMQ library
    zmq_lib = try_load_zmq()
    if not zmq_lib then
        logger.warn("ZMQ library not found - bridge disabled. Events will not be sent to Python service.")
        is_available = false
        return false
    end
    
    -- Create context
    zmq_ctx = zmq_lib.zmq_ctx_new()
    if zmq_ctx == nil then
        logger.error("Failed to create ZMQ context: " .. get_zmq_error())
        is_available = false
        return false
    end
    
    -- Initialize PUB socket
    if not init_pub_socket() then
        zmq_lib.zmq_ctx_term(zmq_ctx)
        zmq_ctx = nil
        is_available = false
        return false
    end
    
    -- Initialize SUB socket (optional - doesn't fail init if unavailable)
    if not init_sub_socket() then
        logger.warn("SUB socket initialization failed - command receiving disabled")
        -- Continue anyway, PUB socket works
    end

    -- Initialize mic SUB socket (optional - doesn't fail init if unavailable)
    if not init_mic_sub_socket() then
        logger.warn("Mic SUB socket initialization failed - mic_python receiving disabled")
        -- Continue anyway
    end

    logger.info("ZMQ bridge initialized - PUB on " .. config.pub_endpoint)
    if zmq_sub_socket then
        logger.info("ZMQ bridge SUB connected to " .. config.sub_endpoint)
    end
    if zmq_mic_sub_socket then
        logger.info("ZMQ mic SUB connected to " .. config.mic_sub_endpoint)
    end
    is_available = true
    
    -- Record initialization time for connection timeout tracking
    connection_status.initialization_time = os.time()
    connection_status.connected = true  -- Optimistic: assume connected until proven otherwise
    
    return true
end

--- Publish a message to a topic.
-- @param topic Topic string (e.g., "game.event")
-- @param payload Table to be JSON-encoded
-- @return true if sent successfully, false otherwise
function bridge.publish(topic, payload)
    -- Lazy initialization
    if not is_initialized then
        bridge.init()
    end
    
    if not is_available or not zmq_pub_socket then
        return false
    end
    
    -- Encode payload to JSON
    local ok, payload_json = pcall(json.encode, payload)
    if not ok then
        logger.error("Failed to encode payload to JSON: " .. tostring(payload_json))
        return false
    end
    
    -- Wrap in message envelope
    local message_data = {
        topic = topic,
        payload = payload,
        timestamp = os.time() * 1000,
    }
    
    local ok2, message_json = pcall(json.encode, message_data)
    if not ok2 then
        logger.error("Failed to encode message to JSON")
        return false
    end
    
    -- Format: "topic json_payload"
    local full_message = topic .. " " .. message_json
    
    -- Send (non-blocking)
    local rc = zmq_lib.zmq_send(zmq_pub_socket, full_message, #full_message, ZMQ_DONTWAIT)
    if rc < 0 then
        local err = get_zmq_error()
        -- EAGAIN is expected for non-blocking send with no subscribers
        if not err:find("Resource temporarily unavailable") then
            logger.debug("ZMQ send warning: " .. err)
        end
        return false
    end
    
    logger.debug("Published to %s (%d bytes)", topic, #full_message)
    return true
end

--- Register a handler for a specific topic.
-- @param topic Topic string (e.g., "dialogue.display", "state.query")
-- @param handler Function to call with (topic, payload) arguments
function bridge.register_handler(topic, handler)
    command_handlers[topic] = handler
    logger.info("Registered ZMQ handler for topic: " .. topic)
end

--- Unregister a handler for a topic.
-- @param topic Topic string
function bridge.unregister_handler(topic)
    command_handlers[topic] = nil
    logger.debug("Unregistered handler for topic: " .. topic)
end

--- Poll for incoming commands (non-blocking).
-- Call this periodically from game loop to receive commands from Python.
-- @return Number of messages processed
function bridge.poll_commands()
    if not is_available or not zmq_sub_socket then
        logger.debug("poll_commands: not available or no SUB socket")
        return 0
    end
    
    local messages_processed = 0
    local recv_buf = ffi.new("char[65536]")  -- 64KB buffer
    
    -- Process up to 10 messages per poll to avoid blocking
    for _ = 1, 10 do
        local rc = zmq_lib.zmq_recv(zmq_sub_socket, recv_buf, 65535, ZMQ_DONTWAIT)
        
        if rc < 0 then
            -- No more messages or error (EAGAIN is expected for non-blocking)
            local errno = zmq_lib.zmq_errno()
            if errno ~= EAGAIN then
                logger.debug("poll_commands: recv error errno=%d", errno)
            end
            break
        end
        
        if rc > 0 then
            local raw_msg = ffi.string(recv_buf, rc)
            logger.info("poll_commands: received message (%d bytes): %s", rc, raw_msg:sub(1, 100))
            
            -- Parse message: "topic json_payload"
            local space_idx = raw_msg:find(" ")
            if space_idx then
                local topic = raw_msg:sub(1, space_idx - 1)
                local json_str = raw_msg:sub(space_idx + 1)
                
                -- Decode JSON
                local ok, message = pcall(json.decode, json_str)
                if ok and message then
                    -- Extract payload
                    local payload = message.payload or message
                    
                    -- Find and call handler
                    local handler = command_handlers[topic]
                    if handler then
                        local ok2, err = pcall(handler, topic, payload)
                        if not ok2 then
                            logger.error("Handler error for topic '%s': %s", topic, tostring(err))
                        end
                    else
                        logger.debug("No handler registered for topic: " .. topic)
                    end
                    
                    messages_processed = messages_processed + 1
                    
                    -- Mark service as alive when we receive messages
                    bridge.mark_service_alive()
                else
                    logger.warn("Failed to decode command JSON: " .. tostring(message))
                end
            else
                logger.warn("Invalid message format (no space separator): " .. raw_msg:sub(1, 50))
            end
        end
    end
    
    -- Poll mic SUB socket for mic_python messages (mic.status, mic.result)
    -- mic_python uses simple wire format: "<topic> <json>" without envelope wrapper.
    -- The existing payload = message.payload or message fallback handles this correctly.
    if zmq_mic_sub_socket then
        for _ = 1, 10 do
            local rc = zmq_lib.zmq_recv(zmq_mic_sub_socket, recv_buf, 65535, ZMQ_DONTWAIT)

            if rc < 0 then
                local errno = zmq_lib.zmq_errno()
                if errno ~= EAGAIN then
                    logger.debug("poll_commands: mic recv error errno=%d", errno)
                end
                break
            end

            if rc > 0 then
                local raw_msg = ffi.string(recv_buf, rc)
                logger.info("poll_commands: mic message (%d bytes): %s", rc, raw_msg:sub(1, 100))

                local space_idx = raw_msg:find(" ")
                if space_idx then
                    local topic    = raw_msg:sub(1, space_idx - 1)
                    local json_str = raw_msg:sub(space_idx + 1)

                    local ok, message = pcall(json.decode, json_str)
                    if ok and message then
                        local payload = message.payload or message

                        local handler = command_handlers[topic]
                        if handler then
                            local ok2, err = pcall(handler, topic, payload)
                            if not ok2 then
                                logger.error("Handler error for mic topic '%s': %s", topic, tostring(err))
                            end
                        else
                            logger.debug("No handler for mic topic: " .. topic)
                        end

                        messages_processed = messages_processed + 1
                    else
                        logger.warn("Failed to decode mic message JSON: " .. tostring(message))
                    end
                else
                    logger.warn("Invalid mic message format (no space): " .. raw_msg:sub(1, 50))
                end
            end
        end
    end

    return messages_processed
end

--- Check if ZMQ bridge is connected and available.
-- @return true if available, false otherwise
function bridge.is_connected()
    return is_available
end

--- Check if SUB socket is available for receiving commands.
-- @return true if SUB socket is connected
function bridge.can_receive()
    return zmq_sub_socket ~= nil
end

--- Shutdown the ZMQ bridge and release resources.
function bridge.shutdown()
    if not is_initialized then
        return
    end
    
    logger.info("Shutting down ZMQ bridge...")
    
    -- Close mic SUB socket
    if zmq_mic_sub_socket and zmq_lib then
        zmq_lib.zmq_close(zmq_mic_sub_socket)
        zmq_mic_sub_socket = nil
    end

    -- Close primary SUB socket
    if zmq_sub_socket and zmq_lib then
        zmq_lib.zmq_close(zmq_sub_socket)
        zmq_sub_socket = nil
    end
    
    -- Close PUB socket
    if zmq_pub_socket and zmq_lib then
        zmq_lib.zmq_close(zmq_pub_socket)
        zmq_pub_socket = nil
    end
    
    -- Terminate context
    if zmq_ctx and zmq_lib then
        zmq_lib.zmq_ctx_term(zmq_ctx)
        zmq_ctx = nil
    end
    
    -- Clear handlers
    command_handlers = {}
    
    is_available = false
    is_initialized = false
    logger.info("ZMQ bridge shutdown complete")
end

--- Get current configuration.
-- @return Configuration table
function bridge.get_config()
    return {
        pub_endpoint     = config.pub_endpoint,
        sub_endpoint     = config.sub_endpoint,
        mic_sub_endpoint = config.mic_sub_endpoint,
        enabled          = config.enabled,
        is_available     = is_available,
        is_initialized   = is_initialized,
        can_receive      = zmq_sub_socket ~= nil,
        can_receive_mic  = zmq_mic_sub_socket ~= nil,
    }
end

--------------------------------------------------------------------------------
-- Connection Status API (for user notifications)
--------------------------------------------------------------------------------

--- Get the current connection status.
-- @return Table with connection status details
function bridge.get_connection_status()
    return {
        connected = connection_status.connected,
        last_successful_send = connection_status.last_successful_send,
        last_successful_recv = connection_status.last_successful_recv,
        initialization_time = connection_status.initialization_time,
        has_notified_disconnect = connection_status.has_notified_disconnect,
    }
end

--- Mark that a successful message was received from Python service.
-- This is called internally when poll_commands receives a message.
function bridge.mark_service_alive()
    local was_disconnected = not connection_status.connected
    connection_status.connected = true
    connection_status.last_successful_recv = os.time()
    
    -- If we were previously disconnected, mark for reconnect notification
    if was_disconnected and connection_status.has_notified_disconnect then
        connection_status.has_notified_reconnect = false  -- Allow reconnect notification
        logger.info("Python service connection restored")
    end
end

--- Mark that the Python service appears disconnected.
-- Called when we detect communication failure.
function bridge.mark_service_disconnected()
    connection_status.connected = false
end

--- Check if we should show a disconnect notification.
-- @return true if notification should be shown (first time only)
function bridge.should_notify_disconnect()
    if not connection_status.has_notified_disconnect and not connection_status.connected then
        connection_status.has_notified_disconnect = true
        return true
    end
    return false
end

--- Check if we should show a reconnect notification.
-- @return true if notification should be shown
function bridge.should_notify_reconnect()
    if connection_status.connected and connection_status.has_notified_disconnect and not connection_status.has_notified_reconnect then
        connection_status.has_notified_reconnect = true
        return true
    end
    return false
end

--- Reset notification state (e.g., on new game load).
function bridge.reset_notification_state()
    connection_status.has_notified_disconnect = false
    connection_status.has_notified_reconnect = false
end

--- Check if the Python service is currently available.
-- @return true if connected and responding, false otherwise
function bridge.is_service_available()
    return connection_status.connected and is_available
end

--- Check if we should show an offline attempt notification.
-- This is throttled to avoid spam (max once per 10 seconds).
-- @return true if offline and notification should be shown
local last_offline_attempt_notification = 0
local OFFLINE_ATTEMPT_THROTTLE = 10  -- seconds

function bridge.should_notify_offline_attempt()
    if connection_status.connected then
        return false  -- Service is connected, no need to notify
    end
    
    local now = os.time()
    if (now - last_offline_attempt_notification) >= OFFLINE_ATTEMPT_THROTTLE then
        last_offline_attempt_notification = now
        return true
    end
    return false
end

return bridge

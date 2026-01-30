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
local zmq_pub_socket = nil   -- For publishing events (PUB, bind :5555)
local zmq_sub_socket = nil   -- For receiving commands (SUB, connect :5556)
local is_available = false
local is_initialized = false

-- Command handlers table (topic -> function)
local command_handlers = {}

-- Configuration (can be overridden via init)
local config = {
    pub_endpoint = "tcp://*:5555",      -- Lua PUB, Python SUB
    sub_endpoint = "tcp://127.0.0.1:5556",  -- Python PUB, Lua SUB
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

--------------------------------------------------------------------------------
-- Public API
--------------------------------------------------------------------------------

--- Initialize the ZMQ bridge.
-- @param opts Optional configuration table with 'pub_endpoint', 'sub_endpoint', 'enabled' fields
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
    
    logger.info("ZMQ bridge initialized - PUB on " .. config.pub_endpoint)
    if zmq_sub_socket then
        logger.info("ZMQ bridge SUB connected to " .. config.sub_endpoint)
    end
    is_available = true
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
                else
                    logger.warn("Failed to decode command JSON: " .. tostring(message))
                end
            else
                logger.warn("Invalid message format (no space separator): " .. raw_msg:sub(1, 50))
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
    
    -- Close SUB socket first
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
        pub_endpoint = config.pub_endpoint,
        sub_endpoint = config.sub_endpoint,
        enabled = config.enabled,
        is_available = is_available,
        is_initialized = is_initialized,
        can_receive = zmq_sub_socket ~= nil,
    }
end

return bridge

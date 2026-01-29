-- ZeroMQ Bridge for TALKER Expanded
-- Provides ZMQ PUB socket for publishing events to Python service
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
local zmq_socket = nil
local is_available = false
local is_initialized = false

-- Configuration (can be overridden via init)
local config = {
    endpoint = "tcp://*:5555",
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

--------------------------------------------------------------------------------
-- Public API
--------------------------------------------------------------------------------

--- Initialize the ZMQ bridge.
-- @param opts Optional configuration table with 'endpoint' and 'enabled' fields
-- @return true if initialization successful, false otherwise
function bridge.init(opts)
    if is_initialized then
        logger.debug("ZMQ bridge already initialized")
        return is_available
    end
    
    is_initialized = true
    
    -- Apply options
    if opts then
        if opts.endpoint then config.endpoint = opts.endpoint end
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
    
    -- Create PUB socket
    zmq_socket = zmq_lib.zmq_socket(zmq_ctx, ZMQ_PUB)
    if zmq_socket == nil then
        logger.error("Failed to create ZMQ socket: " .. get_zmq_error())
        zmq_lib.zmq_ctx_term(zmq_ctx)
        zmq_ctx = nil
        is_available = false
        return false
    end
    
    -- Set linger to 0 for fast shutdown
    local linger = ffi.new("int[1]", 0)
    zmq_lib.zmq_setsockopt(zmq_socket, ZMQ_LINGER, linger, ffi.sizeof("int"))
    
    -- Bind socket
    local rc = zmq_lib.zmq_bind(zmq_socket, config.endpoint)
    if rc ~= 0 then
        logger.error("Failed to bind ZMQ socket to " .. config.endpoint .. ": " .. get_zmq_error())
        zmq_lib.zmq_close(zmq_socket)
        zmq_lib.zmq_ctx_term(zmq_ctx)
        zmq_socket = nil
        zmq_ctx = nil
        is_available = false
        return false
    end
    
    logger.info("ZMQ bridge initialized - publishing on " .. config.endpoint)
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
    
    if not is_available then
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
    local rc = zmq_lib.zmq_send(zmq_socket, full_message, #full_message, ZMQ_DONTWAIT)
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

--- Check if ZMQ bridge is connected and available.
-- @return true if available, false otherwise
function bridge.is_connected()
    return is_available
end

--- Shutdown the ZMQ bridge and release resources.
function bridge.shutdown()
    if not is_initialized then
        return
    end
    
    logger.info("Shutting down ZMQ bridge...")
    
    if zmq_socket and zmq_lib then
        zmq_lib.zmq_close(zmq_socket)
        zmq_socket = nil
    end
    
    if zmq_ctx and zmq_lib then
        zmq_lib.zmq_ctx_term(zmq_ctx)
        zmq_ctx = nil
    end
    
    is_available = false
    is_initialized = false
    logger.info("ZMQ bridge shutdown complete")
end

--- Get current configuration.
-- @return Configuration table
function bridge.get_config()
    return {
        endpoint = config.endpoint,
        enabled = config.enabled,
        is_available = is_available,
        is_initialized = is_initialized,
    }
end

return bridge

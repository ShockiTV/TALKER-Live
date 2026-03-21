local logger = require("framework.logger")
local json = require("infra.HTTP.json")

local M = {}

local SAFETY_MARGIN_SECONDS = 60
local FETCH_TIMEOUT_SECONDS = 5
local POLL_INTERVAL_MS = 50

local _token_url = ""
local _client_id = ""
local _username = ""
local _password = ""
local _client_secret = ""
local _enabled = false

local _cached_token = nil
local _cached_expires_at = nil

local _http_post = nil
local _sleep_ms = nil
local _clock = os.clock
local _time = os.time

local function is_nonempty_string(value)
    return type(value) == "string" and value ~= ""
end

local function is_enabled()
    return _enabled
        and is_nonempty_string(_token_url)
        and is_nonempty_string(_client_id)
        and is_nonempty_string(_username)
        and is_nonempty_string(_password)
end

local function clear_cache()
    _cached_token = nil
    _cached_expires_at = nil
end

local function clear_configuration()
    _token_url = ""
    _client_id = ""
    _username = ""
    _password = ""
    _client_secret = ""
    _enabled = false
end

local function url_encode(value)
    local encoded = tostring(value)
    encoded = encoded:gsub("\n", "\r\n")
    encoded = encoded:gsub("([^%w%-%_%.%~])", function(ch)
        return string.format("%%%02X", string.byte(ch))
    end)
    return encoded
end

local function build_form_body()
    local body = "grant_type=password"
        .. "&client_id=" .. url_encode(_client_id)
        .. "&username=" .. url_encode(_username)
        .. "&password=" .. url_encode(_password)
    if is_nonempty_string(_client_secret) then
        body = body .. "&client_secret=" .. url_encode(_client_secret)
    end
    return body
end

local function close_socket(sock)
    if sock and sock.close then
        pcall(function() sock:close() end)
    end
end

local function decode_json(body)
    local ok, payload = pcall(json.decode, body)
    if not ok then
        return nil, "invalid token response"
    end
    if type(payload) ~= "table" then
        return nil, "invalid token response"
    end
    return payload
end

local function format_oauth_error(payload)
    local err = tostring(payload.error)
    local desc = payload.error_description and tostring(payload.error_description) or ""
    if desc ~= "" and desc ~= err then
        return err .. ": " .. desc
    end
    return err
end

local function ensure_transport()
    if _http_post then
        return _http_post, _sleep_ms
    end

    local ok, pollnet = pcall(require, "infra.HTTP.pollnet")
    if not ok or not pollnet or not pollnet.http_post then
        return nil, nil, "pollnet unavailable"
    end

    return pollnet.http_post, pollnet.sleep_ms
end

function M.configure(token_url, client_id, username, password, client_secret, enabled)
    _enabled = enabled ~= false
    _token_url = type(token_url) == "string" and token_url or ""
    _client_id = type(client_id) == "string" and client_id or ""
    _username = type(username) == "string" and username or ""
    _password = type(password) == "string" and password or ""
    _client_secret = type(client_secret) == "string" and client_secret or ""
    clear_cache()

    if is_enabled() then
        logger.info("Keycloak ROPC auth configured (token_url=%s, client_id=%s)", _token_url, _client_id)
    elseif _enabled then
        logger.info("Keycloak auth disabled (missing token_url/client_id/username/password)")
    else
        logger.info("Keycloak auth disabled (local service mode)")
    end
end

function M.fetch_token()
    if not is_enabled() then
        return nil
    end

    local http_post, sleep_ms, transport_err = ensure_transport()
    if not http_post then
        return nil, transport_err
    end

    logger.debug("Fetching Keycloak token (token_url=%s, client_id=%s)", _token_url, _client_id)

    local headers = {
        ["content-type"] = "application/x-www-form-urlencoded",
    }
    local body = build_form_body()
    local sock = http_post(_token_url, headers, body, true)
    if not sock then
        return nil, "token request failed to start"
    end

    local deadline = _clock() + FETCH_TIMEOUT_SECONDS
    local last_error = nil

    while _clock() < deadline do
        local ok, msg = sock:poll()
        local status = sock.status and sock:status() or nil

        if ok and type(msg) == "string" and msg ~= "" then
            local payload, decode_err = decode_json(msg)
            if not payload then
                close_socket(sock)
                return nil, decode_err
            end

            if payload.access_token and payload.access_token ~= "" then
                local expires_in = tonumber(payload.expires_in) or 0
                _cached_token = payload.access_token
                _cached_expires_at = _time() + math.max(expires_in, 0)

                logger.debug("Fetched Keycloak token successfully for client_id=%s", _client_id)
                close_socket(sock)
                return _cached_token
            end

            if payload.error then
                close_socket(sock)
                return nil, format_oauth_error(payload)
            end

            close_socket(sock)
            return nil, "token response missing access_token"
        end

        if status == "error" then
            if type(msg) == "string" and msg ~= "" then
                last_error = msg
            elseif sock.last_message then
                local ok_last, last_msg = pcall(function() return sock:last_message() end)
                if ok_last and type(last_msg) == "string" and last_msg ~= "" then
                    last_error = last_msg
                end
            end
            if not last_error then
                last_error = "token fetch failed"
            end
            break
        end

        if status == "closed" then
            last_error = "token fetch connection closed"
            break
        end

        if sleep_ms then
            sleep_ms(POLL_INTERVAL_MS)
        end
    end

    close_socket(sock)

    if last_error then
        return nil, last_error
    end

    return nil, "token fetch timeout"
end

function M.get_cached_token()
    if not is_enabled() then
        return nil
    end

    if not _cached_token or not _cached_expires_at then
        return nil
    end

    local remaining = _cached_expires_at - _time()
    if remaining <= SAFETY_MARGIN_SECONDS then
        return nil
    end

    return _cached_token
end

function M.clear()
    clear_cache()
    clear_configuration()
end

-- Test helpers
function M._set_transport(http_post_fn, sleep_ms_fn)
    _http_post = http_post_fn
    _sleep_ms = sleep_ms_fn
end

function M._set_time_sources(clock_fn, time_fn)
    _clock = clock_fn or os.clock
    _time = time_fn or os.time
end

function M._reset_for_test()
    M.clear()
    _http_post = nil
    _sleep_ms = nil
    _clock = os.clock
    _time = os.time
end

return M

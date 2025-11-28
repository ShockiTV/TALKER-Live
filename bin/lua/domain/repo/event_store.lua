package.path = package.path .. ";./bin/lua/?.lua;"
local logger = require'framework.logger'

-- Define the EventStore class
local EventStore = {
    events = {}
}


-- Method for saving the event store data
function EventStore:get_save_data()
    logger.info('Saving event store...')
    return self.events
end

function EventStore:clear()
    self.events = {}
end

-- Method for loading the event store data
function EventStore:load_save_data(saved_events)
    logger.info('Loading event store...')
    self.events = saved_events
    logger.info('Events size is now: ' .. #self.events)
end

-- Method for storing an event
function EventStore:store_event(event)
    local game_time_ms = event.game_time_ms

    -- Increment game_time_ms by 1 ms if the key already exists
    while self.events[game_time_ms] do
        game_time_ms = game_time_ms + 1
    end

    -- Store the event with the new game_time_ms as the key
    event.game_time_ms = game_time_ms
    self.events[game_time_ms] = event
end

-- Method to retrieve an event by game_time_ms
function EventStore:get_event(game_time_ms)
    return self.events[game_time_ms]
end

-- Method to remove an event by game_time_ms
function EventStore:remove_event(game_time_ms)
    logger.debug("Removing event with timestamp: %s", game_time_ms)
    self.events[game_time_ms] = nil
end

-- Internal function to find the first event index that is not too old
local function find_start_index(events, since_game_time_ms)
    local keys = {}
    for k in pairs(events) do
        table.insert(keys, k)
    end
    table.sort(keys)

    local low, high = 1, #keys
    while low <= high do
        local mid = math.floor((low + high) / 2)
        if keys[mid] < since_game_time_ms then
            low = mid + 1
        else
            high = mid - 1
        end
    end
    return low, keys
end

-- Method to get recent events since a specific game_time
function EventStore:get_events_since(since_game_time_ms)
    local start_index, sorted_keys = find_start_index(self.events, since_game_time_ms)
    local recent_events = {}
    for i = start_index, #sorted_keys do
        table.insert(recent_events, self.events[sorted_keys[i]])
    end
    return recent_events
end

-- Method to retrieve all events
function EventStore:get_all_events()
    local all_events = {}
    for _, event in pairs(self.events) do
        table.insert(all_events, event)
    end
    return all_events
end

-- Method to count events since a specific game_time
function EventStore:get_count_events_since(since_game_time_ms)
    local start_index, sorted_keys = find_start_index(self.events, since_game_time_ms)
    return #sorted_keys - start_index + 1
end

return EventStore

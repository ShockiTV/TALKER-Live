package.path = package.path .. ";./bin/lua/?.lua;"
local logger = require("framework.logger")

-- Define the EventStore class
local EventStore = {
	events = {},
	sorted_keys = {}, -- Maintain a sorted list of timestamps for efficient range queries
}

-- Method for saving the event store data
function EventStore:get_save_data()
	logger.info("Saving event store...")
	-- We only save events map. sorted_keys is transient and rebuilt on load.
	return self.events
end

function EventStore:clear()
	self.events = {}
	self.sorted_keys = {}
end

-- Helper to binary search for insertion point or specific value
local function binary_search(list, value)
	local low, high = 1, #list
	while low <= high do
		local mid = math.floor((low + high) / 2)
		if list[mid] < value then
			low = mid + 1
		else
			high = mid - 1
		end
	end
	return low -- Returns the index where 'value' should be or is found
end

-- Method for loading the event store data
function EventStore:load_save_data(saved_events)
	logger.info("Loading event store...")
	
	-- MIGRATION: Check if saved data uses old format (content string instead of typed events)
	-- Old format events have a 'content' field with a string description
	-- New format events have a 'type' field with an EventType enum value
	if saved_events then
		for _, event in pairs(saved_events) do
			-- Check first event to detect format
			if event.content and type(event.content) == "string" and not event.type then
				logger.warn("Detected old event format (content-based). Wiping event store for clean migration.")
				saved_events = {}
			end
			break -- Only need to check first event
		end
	end
	
	self.events = saved_events or {}

	-- Rebuild sorted_keys and count
	self.sorted_keys = {}
	local count = 0
	for k in pairs(self.events) do
		table.insert(self.sorted_keys, k)
		count = count + 1
	end
	table.sort(self.sorted_keys)

	logger.info("Events size is now: " .. count)
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

	-- Insert into sorted_keys keeping it sorted
	local count = #self.sorted_keys
	-- Optimization: mostly we append new events at the end
	if count == 0 or game_time_ms > self.sorted_keys[count] then
		table.insert(self.sorted_keys, game_time_ms)
	else
		-- Rare case: inserting older event or out of order
		local insert_pos = binary_search(self.sorted_keys, game_time_ms)
		table.insert(self.sorted_keys, insert_pos, game_time_ms)
	end
end

-- Method to retrieve an event by game_time_ms
function EventStore:get_event(game_time_ms)
	return self.events[game_time_ms]
end

-- Method to remove an event by game_time_ms
function EventStore:remove_event(game_time_ms)
	logger.debug("Removing event with timestamp: %s", game_time_ms)
	if self.events[game_time_ms] then
		self.events[game_time_ms] = nil

		-- Remove from sorted_keys
		local idx = binary_search(self.sorted_keys, game_time_ms)
		-- Verify it matches before removing
		if self.sorted_keys[idx] == game_time_ms then
			table.remove(self.sorted_keys, idx)
		else
			-- Fallback linear search if index drifted
			for i, k in ipairs(self.sorted_keys) do
				if k == game_time_ms then
					table.remove(self.sorted_keys, i)
					break
				end
			end
		end
	end
end

-- Method to get recent events since a specific game_time
function EventStore:get_events_since(since_game_time_ms)
	local start_index = binary_search(self.sorted_keys, since_game_time_ms)

	local recent_events = {}
	for i = start_index, #self.sorted_keys do
		local key = self.sorted_keys[i]
		if key > since_game_time_ms then
			table.insert(recent_events, self.events[key])
		end
	end
	return recent_events
end

-- Method to retrieve all events
function EventStore:get_all_events()
	local all_events = {}
	-- Return in sorted order
	for _, k in ipairs(self.sorted_keys) do
		-- Safety check
		if self.events[k] then
			table.insert(all_events, self.events[k])
		end
	end
	return all_events
end

-- Method to count events since a specific game_time
function EventStore:get_count_events_since(since_game_time_ms)
	local start_index = binary_search(self.sorted_keys, since_game_time_ms)
	local count = 0
	for i = start_index, #self.sorted_keys do
		if self.sorted_keys[i] > since_game_time_ms then
			count = count + 1
		end
	end
	return count
end

return EventStore

local logger = require("framework.logger")
local game = require("infra.game_adapter")
local config = require("interface.config")
local mcm = talker_mcm
local transformation = {}
transformation.__index = transformation

local function is_too_far_to_speak(character)
	local distance = game.get_distance_to_player(character.game_id)
	local result = distance > config.NPC_SPEAK_DISTANCE
	if result == true then
		logger.debug(
			"too far to speak %s at distance %s when max distance is %s ",
			character.game_id,
			distance,
			config.NPC_SPEAK_DISTANCE
		)
	end
	return result
end

function transformation.pick_potential_speakers(recent_events)
	local latest_event = recent_events[#recent_events]
	-- filter out any witnesses further than config.NPC_SPEAK_DISTANCE
	local witnesses = latest_event.witnesses
	logger.info("wintesses " .. #witnesses)
	logger.debug("witnesses %s", witnesses)

	for i = #witnesses, 1, -1 do -- iterate in reverse to safely remove items
		if game.is_player(witnesses[i].game_id) or is_too_far_to_speak(witnesses[i]) then
			logger.debug("removing witness from speaker list: %s", witnesses[i])
			table.remove(witnesses, i)
		end
	end
	return witnesses
end

------------------------------------------------------------------------------------------------------
-- Constants for memory management
------------------------------------------------------------------------------------------------------
transformation.COMPRESSION_THRESHOLD = 12

------------------------------------------------------------------------------------------------------
function transformation.should_update_narrative(new_events)
	if not new_events then
		return false
	end
	return #new_events >= transformation.COMPRESSION_THRESHOLD
end

function transformation.inject_time_gaps(events, last_update_time, current_game_time)
	if not events then
		events = {}
	end

	local processed_events = {}
	local previous_time = last_update_time or 0
	local SIGNIFICANT_GAP_MS = mcm.get("time_gap") * 60 * 60 * 1000 -- Default 12 in-game hours

	-- Helper to create gap event
	local function create_gap_event(start_time, end_time)
		local delta = end_time - start_time
		if delta > SIGNIFICANT_GAP_MS then
			local hours = math.floor(delta / (1000 * 60 * 60))
			local gap_content =
				string.format("TIME GAP: It has been approximately %d hours since the last event.", hours)
			logger.info("Injecting synthetic time gap event: " .. gap_content)
			return {
				content = gap_content,
				game_time_ms = start_time + 1,
				is_synthetic = true,
				flags = { is_synthetic = true },
			}
		end
		return nil
	end

	-- 1. Check gap before first event (or current time if no events)
	local first_event_time = current_game_time
	if #events > 0 then
		first_event_time = events[1].game_time_ms
	end

	if previous_time > 0 then
		local gap = create_gap_event(previous_time, first_event_time)
		if gap then
			table.insert(processed_events, gap)
		end
	end

	-- 2. Process events and check internal gaps
	for i, event in ipairs(events) do
		-- Check gap between previous event (or start) and this event
		-- Note: We already checked the gap before the FIRST event above.
		-- But for subsequent events (i > 1), we check gap between even[i-1] and event[i].

		if i > 1 then
			local prev_event_time = events[i - 1].game_time_ms
			local current_event_time = event.game_time_ms
			local gap = create_gap_event(prev_event_time, current_event_time)
			if gap then
				table.insert(processed_events, gap)
			end
		end

		table.insert(processed_events, event)
	end

	return processed_events
end

function transformation.mockGame(mockGame)
	game = mockGame
end

return transformation

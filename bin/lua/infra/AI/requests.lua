-- AI_request module
-- This module is responsible for the AI_request's functionalities.
-- It provides functions for:
-- - picking the next speaker
-- - compressing memories
-- - requesting dialogue
-- they use a callback system to deal with the asynchronous nature of the AI requests

package.path = package.path .. ";./bin/lua/?.lua"

local transformations = require("infra.AI.transformations")
local json = require("infra.HTTP.json")
local game = require("infra.game_adapter")

local prompt_builder = require("infra.AI.prompt_builder")
local logger = require("framework.logger")
local memory_store = require("domain.repo.memory_store")
local event_store = require("domain.repo.event_store")
local config = require("interface.config")
local dialogue_cleaner = require("infra.AI.dialogue_cleaner")

local gpt_model = require("infra.AI.GPT")
local openrouter = require("infra.AI.OpenRouterAI")
local local_model = require("infra.AI.local_ollama")
local proxy_model = require("infra.AI.proxy")

-- Game interface
local query = talker_game_queries

local ModelList = {
	[0] = gpt_model,
	[1] = openrouter,
	[2] = local_model,
	[3] = proxy_model,
}

local model = function()
	return ModelList[config.modelmethod()]
end

local AI_request = {}
AI_request.__index = AI_request
AI_request.active_updates = {} -- LOCK to prevent concurrent memory updates for same char

-- Speaker cooldown system
local COOLDOWN_DURATION_MS = 3 * 1000 -- seconds in milliseconds
local speaker_last_spoke = {} -- table to track when each speaker last spoke

-- to be moved
local function is_player(character_id)
	return tostring(character_id) == "0"
end

------------------------------------------------------------------------------------------
-- Cooldown functions
------------------------------------------------------------------------------------------

-- Check if a speaker is on cooldown
local function is_speaker_on_cooldown(speaker_id, current_game_time)
	local last_spoke_time = speaker_last_spoke[tostring(speaker_id)]
	if not last_spoke_time then
		return false -- Never spoke before, not on cooldown
	end

	local time_since_last_spoke = current_game_time - last_spoke_time

	logger.debug("Speaker " .. speaker_id .. " last spoke " .. time_since_last_spoke .. "ms ago")

	return time_since_last_spoke < COOLDOWN_DURATION_MS
end

-- Set the last spoke time for a speaker
local function set_speaker_last_spoke(speaker_id, current_game_time)
	speaker_last_spoke[tostring(speaker_id)] = current_game_time
	logger.debug("Set cooldown for speaker " .. speaker_id .. " at time " .. current_game_time)
end

-- Filter out speakers that are on cooldown
local function filter_speakers_by_cooldown(speakers, current_game_time)
	local available_speakers = {}

	for _, speaker in ipairs(speakers) do
		if not is_speaker_on_cooldown(speaker.game_id, current_game_time) then
			table.insert(available_speakers, speaker)
		else
			logger.debug("Speaker " .. speaker.game_id .. " is on cooldown, skipping")
		end
	end

	return available_speakers
end

------------------------------------------------------------------------------------------
-- Core functions
------------------------------------------------------------------------------------------

local function check_if_id_in_recent_events(recent_events, picked_speaker_id)
	local latest_event = recent_events[#recent_events]
	local witnesses = latest_event.witnesses
	local witness_ids = ""
	for _, witness in ipairs(witnesses) do
		witness_ids = witness_ids .. witness.game_id .. ", "
		if tostring(witness.game_id) == tostring(picked_speaker_id) then
			return true
		end
	end
	logger.warn("AI picked invalid speaker: " .. tostring(picked_speaker_id) .. ". Valid IDs were: " .. witness_ids)
	return false
end

local function is_valid_speaker(recent_events, picked_speaker_id)
	-- check if speaker id was in recent events
	if not check_if_id_in_recent_events(recent_events, picked_speaker_id) then
		logger.warn("AI did not pick a valid speaker: " .. picked_speaker_id)
		return false
	end

	-- get current game time from the most recent event
	local current_game_time = recent_events[#recent_events].game_time_ms

	-- check if speaker is on cooldown
	if is_speaker_on_cooldown(picked_speaker_id, current_game_time) then
		logger.warn("AI picked speaker on cooldown: " .. picked_speaker_id)
		return false
	end

	logger.info("Picked next speaker: " .. picked_speaker_id)
	-- check if player was picked
	if is_player(picked_speaker_id) and not config.player_speaks then
		logger.info("Player picked, but does not speak automatically")
		return false
	end
	return true
end

function AI_request.pick_speaker(recent_events, compress_memories)
	logger.info("AI_request.pick_speaker")
	-- start function
	local speakers = transformations.pick_potential_speakers(recent_events)

	if not speakers then -- only player
		logger.warn("No viable speaker found close enough to player")
		return nil
	end

	-- Get current game time from the most recent event
	local current_game_time = recent_events[#recent_events].game_time_ms

	-- Filter out speakers on cooldown
	local available_speakers = filter_speakers_by_cooldown(speakers, current_game_time)

	if #available_speakers == 0 then
		logger.warn("All potential speakers are on cooldown")
		return nil
	end

	if #available_speakers == 1 then -- no need to pick using AI
		logger.debug("Only one possible speaker nearby (after cooldown filter)")
		local selected_speaker_id = available_speakers[1].game_id
		set_speaker_last_spoke(selected_speaker_id, current_game_time) -- Set cooldown
		logger.debug("Compressing memories after picking speaker")
		return compress_memories(selected_speaker_id)
	end

	-- Helper to reliably extract speaker ID
	local function extract_speaker_id(event)
		if not event then
			return nil
		end
		-- Try involved_objects first (if they are character objects)
		if
			event.involved_objects
			and event.involved_objects[1]
			and type(event.involved_objects[1]) == "table"
			and event.involved_objects[1].game_id
		then
			return event.involved_objects[1].game_id
		end
		-- Fallback to witnesses (guaranteed to be character objects)
		-- The speaker is virtually always the first witness to their own event
		if event.witnesses and event.witnesses[1] and event.witnesses[1].game_id then
			return event.witnesses[1].game_id
		end
		return nil
	end

	-- Determine context from last speaker
	local context_speaker_id = extract_speaker_id(recent_events[#recent_events])

	-- Fallback to second last event if needed
	if not context_speaker_id and #recent_events > 1 then
		context_speaker_id = extract_speaker_id(recent_events[#recent_events - 1])
	end

	local mid_term_memory = nil
	local combined_events_list = {}

	-- If we found a context speaker, try to fetch their narrative context
	if context_speaker_id then
		logger.debug("Fetching context for speaker ID: " .. tostring(context_speaker_id))
		local new_events_context = memory_store:get_new_events(context_speaker_id)

		if new_events_context and #new_events_context > 0 then
			local start_idx = 1
			-- Check for compressed event (Mid-Term Memory)
			-- Assume new_events_context is already sorted by time (as per memory_store implementation)
			if new_events_context[1].flags and new_events_context[1].flags.is_compressed then
				mid_term_memory = new_events_context[1].content
				start_idx = 2
			end

			-- Add the rest as raw events
			for i = start_idx, #new_events_context do
				table.insert(combined_events_list, new_events_context[i])
			end
		end
	end

	-- Fallback: If no context speaker or no events found, usage original recent_events
	if #combined_events_list == 0 then
		combined_events_list = recent_events
	end

	local messages =
		prompt_builder.create_pick_speaker_prompt(combined_events_list, available_speakers, mid_term_memory)
	-- call the model to pick the next speaker
	return model().pick_speaker(messages, function(response)
		local picked_speaker_id = nil

		-- Try to parse as JSON first
		local status, decoded = pcall(json.decode, response)
		if status and type(decoded) == "table" and decoded.id then
			picked_speaker_id = decoded.id
			logger.debug("Parsed speaker ID from JSON: " .. tostring(picked_speaker_id))
		else
			-- Fallback to raw text parsing (legacy/safeguard)
			local clean_response = response:match("^%s*(%d+)%s*$") -- extract integers only, ignoring whitespace
			if clean_response then
				picked_speaker_id = tonumber(clean_response)
				logger.debug("Parsed speaker ID from raw text: " .. tostring(picked_speaker_id))
			else
				logger.warn("Could not parse speaker ID from response: " .. tostring(response))
			end
		end

		if not picked_speaker_id then
			return
		end
		-- check if AI picked a valid speaker
		-- Note: we check against 'recent_events' (the raw inputs) for validity to ensure
		-- we don't pick someone far away just because they were in memory
		if not is_valid_speaker(recent_events, picked_speaker_id) then
			return
		end
		-- Set the speaker's cooldown
		set_speaker_last_spoke(picked_speaker_id, current_game_time)
		-- move on to update narrative step
		-- this is actually a callback given to the pick_speaker function, but it's expected to be update_narrative
		logger.debug("Updating narrative after picking speaker")
		compress_memories(picked_speaker_id)
	end)
end

------------------------------------------------------------------------------------------
-- Hierarchical Memory Management
------------------------------------------------------------------------------------------

--- Manages the hierarchical memory system (Raw Events List -> Compressed Mid-Term Memory -> Long-Term Memory ("narrative"))
-- @param speaker_id The ID of the speaker
-- @param request_dialogue Function to request dialogue after update
function AI_request.update_narrative(speaker_id, request_dialogue)
	logger.info("AI_request.manage_memory_hierarchy")

	-- Fetch memory context (narrative + new events)
	local context = memory_store:get_memory_context(speaker_id)

	local new_events = context.new_events or {}
	local current_game_time = query and query.get_game_time_ms() or 0
	new_events = transformations.inject_time_gaps(new_events, context.last_update_time_ms, current_game_time)
	context.new_events = new_events

	logger.info("# of new events fetched: " .. #new_events)

	-- Check if we should perform memory maintenance
	if not transformations.should_update_narrative(new_events) then
		logger.debug("Not enough new events to trigger memory maintenance.")
		if request_dialogue then
			request_dialogue(speaker_id)
		end
		return
	end

	-- LOCK CHECK
	if AI_request.active_updates[speaker_id] then
		logger.warn("Memory update already in progress for " .. speaker_id .. ". Skipping duplicate request.")
		-- We still request dialogue because the previous update will eventually finish,
		if request_dialogue then
			request_dialogue(speaker_id)
		end
		return
	end
	AI_request.active_updates[speaker_id] = true
	logger.info("Acquired memory lock for " .. speaker_id)

	-- Helper to clear lock
	local function clear_lock()
		AI_request.active_updates[speaker_id] = nil
		logger.info("Released memory lock for " .. speaker_id)
	end

	logger.info("Triggering memory maintenance cycle...")

	local current_narrative = context.narrative
	local speaker = AI_request.get_character_by_id(speaker_id, new_events)

	-- Preserve the very last event (contextual trigger)
	-- We remove it from the list of events to be compressed so that it remains "fresh".
	-- This ensures the dialogue generation prompt sees the exact text of the latest interaction.
	if #new_events > 1 then
		logger.info("Preserving latest event for immediate context: " .. tostring(new_events[#new_events].game_time_ms))
		table.remove(new_events)
	end

	-- Bootstrapping: If Long-Term Memory is empty, generate it from scratch using all available events
	if not current_narrative or current_narrative == "" then
		logger.info("Long-Term Memory is empty. Bootstrapping Long-Term Memory from raw events.")
		-- Use the Narrative Update prompt to generate the initial history
		local messages = prompt_builder.create_update_narrative_prompt(speaker, "", new_events)

		model().summarize_story(messages, function(updated_narrative)
			if not updated_narrative then
				logger.error("Failed to generate bootstrapped narrative.")
				clear_lock() -- RELEASE LOCK
				if request_dialogue then
					request_dialogue(speaker_id)
				end
				return
			end

			logger.info("Bootstrapped narrative received.")
			-- We consume ALL events into Long-Term Memory. Set time to the newest event.
			local newest_event_time = new_events[#new_events].game_time_ms
			memory_store:update_narrative(speaker_id, updated_narrative, newest_event_time)

			clear_lock() -- RELEASE LOCK
			if request_dialogue then
				request_dialogue(speaker_id)
			end
		end)
		return
	end

	-- PHASE 1: Promote Compressed Memory to Long-Term Memory (if applicable)
	local oldest_event = new_events[1]
	if oldest_event and oldest_event.flags and oldest_event.flags.is_compressed then
		logger.info("Phase 1: Oldest event is compressed. Integrating into LTM.")

		local function proceed_to_phase_2()
			-- Remove the promoted event from the list used for Phase 2
			table.remove(new_events, 1)
			-- Pass clear_lock to Phase 2.
			AI_request.phase_2_compression(speaker_id, context.narrative, new_events, request_dialogue, clear_lock)
		end

		logger.info("Long-Term Memory exists. Using LLM to integrate compressed memory.")
		-- We pass ONLY the compressed event for integration
		local messages = prompt_builder.create_update_narrative_prompt(speaker, current_narrative, { oldest_event })

		model().summarize_story(messages, function(updated_narrative)
			if not updated_narrative then
				logger.error(
					"Failed to generate updated Long-Term Memory (Phase 1). Aborting update to preserve existing memory."
				)
				clear_lock()
				if request_dialogue then
					request_dialogue(speaker_id)
				end
				return
			end

			logger.info("Updated narrative received.")
			memory_store:update_narrative(speaker_id, updated_narrative, oldest_event.game_time_ms)
			context.narrative = updated_narrative -- Update local ref
			proceed_to_phase_2()
		end)
	else
		logger.info("Phase 1: Oldest event is NOT compressed. Skipping Long-Term Memory update.")
		AI_request.phase_2_compression(speaker_id, context.narrative, new_events, request_dialogue, clear_lock)
	end
end

-- PHASE 2: Compress Raw Events
function AI_request.phase_2_compression(speaker_id, current_narrative, raw_events, request_dialogue, unlock_callback)
	logger.info("Phase 2: Compressing remaining raw events (" .. #raw_events .. " events)")

	if #raw_events == 0 then
		logger.debug("No raw events to compress. Proceeding.")
		if unlock_callback then
			unlock_callback()
		end
		if request_dialogue then
			request_dialogue(speaker_id)
		end
		return
	end

	local speaker = AI_request.get_character_by_id(speaker_id, raw_events)
	local messages = prompt_builder.create_compress_memories_prompt(raw_events, speaker)

	model().summarize_story(messages, function(summary_text) -- Using summarize_story as it is standard for compression
		if not summary_text then
			logger.error("Failed to generate compression summary.")
			if unlock_callback then
				unlock_callback()
			end
			if request_dialogue then
				request_dialogue(speaker_id)
			end
			return
		end

		logger.info("Compression complete. Summary length: " .. string.len(summary_text))

		local newest_raw_event_time = raw_events[#raw_events].game_time_ms

		-- 1. Mark raw events as "processed" by advancing the LTM timestamp
		--    We consider them handled because they are now represented by the summary.
		--    This prevents them from being fetched again as raw events.
		memory_store:update_last_update_time(speaker_id, newest_raw_event_time)

		-- 2. Create and Inject the Compressed Memory into Event Store
		--    It needs to be witnessed by this character so they see it next time.
		local compressed_event = {
			content = summary_text,
			game_time_ms = newest_raw_event_time + 1,
			-- We need to ensure it's witnessed by this speaker.
			witnesses = { { game_id = speaker_id } },
			involved_objects = { { game_id = speaker_id } },
			flags = { is_compressed = true, is_synthetic = true },
		}

		-- We store the event, setting only THIS speaker as witness.
		event_store:store_event(compressed_event)

		logger.info("Compressed memory injected. Time: " .. compressed_event.game_time_ms)

		if request_dialogue then
			request_dialogue(speaker_id)
		end
		if unlock_callback then
			unlock_callback()
		end
	end)
end

-- Backward compatibility alias if needed
AI_request.compress_memories = AI_request.update_narrative

function AI_request.request_dialogue(speaker_id, callback)
	logger.info("AI_request.request_dialogue")
	logger.info("AI_request.request_dialogue")
	local memory_context = memory_store:get_memory_context(speaker_id)

	-- Inject time gap if applicable
	local current_game_time = query and query.get_game_time_ms() or 0
	memory_context.new_events = transformations.inject_time_gaps(
		memory_context.new_events,
		memory_context.last_update_time_ms,
		current_game_time
	)

	-- SLICING OPTIMIZATION (Parallel Execution Logic)
	-- If there are too many new events (e.g. during migration), we only show the MOST RECENT ones to the dialogue prompt.
	-- This prevents the prompt from exploding with 100+ events while the background compression is still running.
	local MAX_DIALOGUE_EVENTS = 12
	if #memory_context.new_events > MAX_DIALOGUE_EVENTS then
		logger.info(
			"Too many new events for dialogue context ("
				.. #memory_context.new_events
				.. "). Slicing to last "
				.. MAX_DIALOGUE_EVENTS
		)
		local sliced_events = {}
		local start_index = #memory_context.new_events - MAX_DIALOGUE_EVENTS + 1
		for i = start_index, #memory_context.new_events do
			table.insert(sliced_events, memory_context.new_events[i])
		end
		memory_context.new_events = sliced_events
	end

	-- Safety check
	if (not memory_context.new_events or #memory_context.new_events == 0) and not memory_context.narrative then
		logger.warn("Requesting dialogue with absolutely no context (no narrative, no events).")
	end

	local speaker_character = AI_request.get_character_by_id(speaker_id, memory_context.new_events)
	local messages, timestamp_to_delete =
		prompt_builder.create_dialogue_request_prompt(speaker_character, memory_context)

	-- call the model to generate the dialogue
	return model().generate_dialogue(messages, function(generated_dialogue)
		-- when it responds...
		if generated_dialogue == nil then
			logger.error("Error generating dialogue")
			return
		end
		logger.info("Received dialogue: " .. generated_dialogue)
		generated_dialogue = dialogue_cleaner.improve_response_text(generated_dialogue) -- remove censorship and other unwanted content
		callback(generated_dialogue, timestamp_to_delete)
	end)
end

------------------------------------------------------------------------------------------
-- Utility functions
------------------------------------------------------------------------------------------

AI_request.witnesses = {}
-- Utility function to extract witness names using saved IDs.
-- Can optionally search a provided list of events instead of the global witness list (thread-safe).
function AI_request.get_character_by_id(speaker_id, search_events)
	logger.info("Getting character name for ID: " .. speaker_id)

	-- 1. Prefer Engine Lookup (Thread-Safe & Full Data)
	-- This gets the most up-to-date and complete character object directly from the game.
	local engine_char = game.get_character_by_id(speaker_id)
	if engine_char then
		logger.info("Character found via Engine Lookup: " .. speaker_id)
		return engine_char
	end

	-- 2. Fallback to Local Context (if provided)
	-- Useful for dead characters or off-line entities preserved in events
	if search_events then
		for _, event in ipairs(search_events) do
			if event.witnesses then
				for _, witness in ipairs(event.witnesses) do
					if tostring(witness.game_id) == tostring(speaker_id) then
						return witness
					end
				end
			end
			if event.involved_objects then
				for _, obj in ipairs(event.involved_objects) do
					if tostring(obj.game_id) == tostring(speaker_id) then
						return obj
					end
				end
			end
		end
		logger.debug("Character ID " .. speaker_id .. " not found in provided local events.")
	end

	-- 3. Fallback to Global List (Legacy behavior)
	for _, witness in ipairs(AI_request.witnesses) do
		logger.debug("Checking witness: " .. witness.game_id)
		if tostring(witness.game_id) == tostring(speaker_id) then
			return witness
		end
	end

	error("No character found for ID: " .. tostring(speaker_id))
end

function AI_request.set_witnesses(recent_events)
	AI_request.witnesses = recent_events[#recent_events].witnesses
end

-- Sequencing function
function AI_request.generate_dialogue(recent_events, function_send_dialogue_to_game)
	logger.info("AI_request.generate_dialogue")
	AI_request.set_witnesses(recent_events)
	AI_request.pick_speaker(recent_events, function(speaker_id)
		-- PARALLEL EXECUTION:
		-- 1. Request Dialogue IMMEDIATELY (Optimize Latency)
		-- We give the player immediate feedback using the current state (all recent events + current memory).
		AI_request.request_dialogue(speaker_id, function(dialogue, timestamp_to_delete)
			function_send_dialogue_to_game(speaker_id, dialogue, timestamp_to_delete)
		end)

		-- 2. Trigger Memory Maintenance in BACKGROUND (Fire and Forget)
		-- This will compress memories if needed, updating LTM for the NEXT interaction.
		-- We pass nil as the callback because the dialogue is already handled.
		AI_request.update_narrative(speaker_id, nil)
	end)
end

-- New function for direct dialogue generation, bypassing speaker picking.
function AI_request.generate_dialogue_from_instruction(speaker_name, event, function_send_dialogue_to_game)
	logger.info("AI_request.generate_dialogue_from_instruction for " .. speaker_name)
	AI_request.set_witnesses({ event })

	local speaker_id = event.involved_objects[1].game_id
	if not speaker_id then
		logger.error("Could not find speaker_id in event.involved_objects[1]. Aborting instruction.")
		return
	end

	-- Directly compress memories and request dialogue for the specified speaker.
	AI_request.update_narrative(speaker_id, function()
		AI_request.request_dialogue(speaker_id, function(dialogue, timestamp_to_delete)
			function_send_dialogue_to_game(speaker_id, dialogue, timestamp_to_delete)
		end)
	end)
end

------------------------------------------------------------------------------------------
-- Cooldown management functions (for external use)
------------------------------------------------------------------------------------------

-- Clear cooldown for a specific speaker (useful for testing or special events)
function AI_request.clear_speaker_cooldown(speaker_id)
	speaker_last_spoke[tostring(speaker_id)] = nil
	logger.debug("Cleared cooldown for speaker " .. speaker_id)
end

-- Clear all speaker cooldowns
function AI_request.clear_all_cooldowns()
	speaker_last_spoke = {}
	logger.debug("Cleared all speaker cooldowns")
end

-- Get remaining cooldown time for a speaker (in milliseconds)
-- Requires current_game_time to be passed in
function AI_request.get_remaining_cooldown(speaker_id, current_game_time)
	local last_spoke_time = speaker_last_spoke[tostring(speaker_id)]
	if not last_spoke_time then
		return 0 -- No cooldown
	end

	local time_since_last_spoke = current_game_time - last_spoke_time
	local remaining = COOLDOWN_DURATION_MS - time_since_last_spoke

	return math.max(0, remaining)
end

-- Get the raw timestamp of when a speaker last spoke
function AI_request.get_last_spoke_time(speaker_id)
	return speaker_last_spoke[tostring(speaker_id)]
end

-- for mocks
function AI_request.insert_mocks(mock_memory_store, mock_game, mock_prompt_builder)
	memory_store = mock_memory_store
	transformations.mockGame(mock_game)
	if mock_prompt_builder ~= nil then
		prompt_builder = mock_prompt_builder
	end
end

return AI_request

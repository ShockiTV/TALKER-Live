package.path = package.path .. ";./bin/lua/?.lua;"
local event_store = require("domain.repo.event_store")
local logger = require("framework.logger")
local AI_request = require("infra.AI.requests")
local game_adapter = require("infra.game_adapter")
local config = require("interface.config")
local queries = talker_game_queries
local talker = {}

function talker.register_event(event, is_important)
	logger.info("talker.register_event")
	event_store:store_event(event)

	-- Silent events go into the store but don't generate dialogue
	if event.flags and event.flags.is_silent then
		logger.info("Silent event registered - no dialogue will be generated")
		return
	end

	-- If the event has the 'is_idle' flag, it's a direct instruction.
	-- Bypass the 'should_someone_speak' and generic 'generate_dialogue' logic.
	if event.flags and event.flags.is_idle then
		logger.info("Idle conversation event detected. Using direct generation path.")
		-- The first object in an idle event is the character object of the intended speaker.
		local speaker_character = event.involved_objects[1]
		if not speaker_character or not speaker_character.game_id then
			logger.error("Idle conversation event has no valid speaker character. Aborting.")
			return
		end
		talker.generate_dialogue_from_instruction(speaker_character.name, event)
	elseif should_someone_speak(event, is_important) then
		talker.generate_dialogue(event)
	end
end

local TEN_SECONDS_ms = 10 * 1000

function talker.generate_dialogue(event)
	logger.debug("Getting all events since " .. event.game_time_ms - TEN_SECONDS_ms)
	local recent_events = event_store:get_events_since(event.game_time_ms - TEN_SECONDS_ms)
	-- begin a dialogue generation request, input is recent_events, output is speaker_id and dialogue
	AI_request.generate_dialogue(recent_events, function(speaker_id, dialogue, timestamp_to_delete)
		-- on response:
		logger.info(
			"talker.generate_dialogue: dialogue generated for speaker_id: " .. speaker_id .. ", dialogue: " .. dialogue
		)

		event.dialogue_generated = true

		game_adapter.display_dialogue(speaker_id, dialogue)
		local dialogue_event = game_adapter.create_dialogue_event(speaker_id, dialogue, event)
		if dialogue_event then
			talker.register_event(dialogue_event)
		end

		if timestamp_to_delete then
			event_store:remove_event(timestamp_to_delete)
		end
	end)
end

function talker.generate_dialogue_from_instruction(speaker_name, event)
	logger.debug("Generating dialogue from instruction for " .. speaker_name)
	AI_request.generate_dialogue_from_instruction(
		speaker_name,
		event,
		function(speaker_id, dialogue, timestamp_to_delete)
			-- on response:
			logger.info(
				"talker.generate_dialogue_from_instruction: dialogue generated for speaker_id: "
					.. speaker_id
					.. ", dialogue: "
					.. dialogue
			)

			-- Race condition check:
			-- If the speaker has spoken recently (e.g. while this slow request was processing), we abort.
			-- This prevents rare occurances where the "Idle Conversation" event triggers just as another event generates dialogue,
			-- leading to moments of double dialogue from the same character.
			local last_spoke_time = AI_request.get_last_spoke_time(speaker_id)
			local current_time = queries.get_game_time_ms()
			local threshold_ms = config.recent_speech_threshold() * 1000

			if last_spoke_time and (current_time - last_spoke_time < threshold_ms) then
				logger.debug(
					"Idle conversation aborted: speaker "
						.. speaker_id
						.. " spoke recently ("
						.. (current_time - last_spoke_time)
						.. "ms ago)."
				)
				if timestamp_to_delete then
					event_store:remove_event(timestamp_to_delete)
				end
				return
			end

			-- Check passed, proceed with dialogue
			-- CRITICAL: We must now update the last spoke time so they don't speak AGAIN immediately after this.
			AI_request.set_speaker_last_spoke(speaker_id, current_time)

			game_adapter.display_dialogue(speaker_id, dialogue)
			local dialogue_event = game_adapter.create_dialogue_event(speaker_id, dialogue, event)
			if dialogue_event then
				talker.register_event(dialogue_event)
			end

			if timestamp_to_delete then
				event_store:remove_event(timestamp_to_delete)
			end
		end
	)
end

function should_someone_speak(event, is_important)
	-- mostly a placeholder
	-- always should reply to player dialogue
	-- for all others, 25% chance
	if #event.witnesses == 1 and game_adapter.is_player(event.witnesses[1]) then
		logger.debug("Only witness is player, not generating dialogue, should probably not save this event at all")
		-- player is only witness
		return false
	end
	return is_important or math.random() < config.BASE_DIALOGUE_CHANCE
end

-- for mocking
function talker.set_game_adapter(adapter)
	game_adapter = adapter
end

return talker

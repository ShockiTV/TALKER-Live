-- the purpose of this module is to turn game objects into natural language descriptions
local prompt_builder = {}

-- imports
package.path = package.path .. ";./bin/lua/?.lua;"
local logger = require("framework.logger")
local Event = require("domain.model.event")
local Character = require("domain.model.character")
local event_store = require("domain.repo.event_store")
local game = require("infra.game_adapter")
local config = require("interface.config")
local backstories = require("domain.repo.backstories")
local personalities = require("domain.repo.personalities")
local factions = require("infra.STALKER.factions")

-- Game interfaces
local query = talker_game_queries

local function describe_characters_with_ids(characters)
	local descriptions = {}
	for _, character in ipairs(characters) do
		if not character.personality or character.personality == "" then
			character.personality = personalities.get_personality(character)
		end
		local desc = string.format("[ID: %d] %s", character.game_id, Character.describe(character))
		table.insert(descriptions, desc)
	end
	return table.concat(descriptions, ", ")
end

local function system_message(content)
	return { role = "system", content = content }
end

local function user_message(content)
	return { role = "user", content = content }
end

--------------------------------------------------------------------------------
-- create_pick_speaker_prompt: use up to the 8 most recent raw events
--------------------------------------------------------------------------------
function prompt_builder.create_pick_speaker_prompt(recent_events, witnesses)
	if not witnesses or #witnesses == 0 then
		logger.warn("No witnesses in the last event.")
		return error("No witnesses in last event")
	end
	if #recent_events == 0 then
		logger.warn("No recent events passed in.")
		return error("No recent events")
	end

	logger.info("prompt_builder.create_pick_speaker_prompt with %d events", #recent_events)

	-- Log each event after sorting
	for i, evt in ipairs(recent_events) do
		logger.spam("Sorted event #%d: %s", i, evt)
	end

	-- keep only the 8 most recent
	logger.spam("Selecting the 8 most recent events if available.")
	local start_index = math.max(#recent_events - 7, 1)
	local last_events_window = {}
	for i = start_index, #recent_events do
		local evt = recent_events[i]
		logger.spam("Adding event #%d to last_events_window: %s", i, evt)
		table.insert(last_events_window, evt)
	end

	local last_event = last_events_window[#last_events_window]
	logger.spam("Last event: %s", last_event)

	-- basic check for chronological order
	if #last_events_window > 1 then
		local second_last_event = last_events_window[#last_events_window - 1]
		if last_event.game_time_ms < second_last_event.game_time_ms then
			logger.warn(
				"Events are not in chronological order: last: %d, second last: %d",
				last_event.game_time_ms,
				second_last_event.game_time_ms
			)
		end
	end

	logger.spam("Number of witnesses in last event: %d", #witnesses)

	local messages = {
		system_message(
			"You are a Speaker ID Selection Engine. Your task is to identify the next speaker based on events and the conversation flow."
				.. "\n\nINSTRUCTIONS:\n "
				.. "1. Analyze the 'CANDIDATES' and 'CURRENT EVENTS (from oldest to newest)' to see who was addressed or who would logically react based on their traits.\n"
				.. "2. Return ONLY a valid JSON object with the 'id' of the selected speaker.\n\n\nExample Output: { \"id\": 123 } \n"
				.. "3. Do not include markdown formatting (like ```json).\n"
		),
		system_message("CANDIDATES (in order of distance): " .. describe_characters_with_ids(witnesses)),
	}

	table.insert(messages, system_message("CURRENT EVENTS (from oldest to newest):\n"))

	-- insert events from oldest to newest
	for i, evt in ipairs(last_events_window) do
		logger.spam("Inserting event #%d into user messages: %s", i, evt)
		local content = (evt == nil and "") or evt.content or Event.describe_short(evt)
		table.insert(messages, user_message(content))
	end

	logger.debug("Finished building pick_speaker_prompt with %d messages", #messages)
	return messages
end

--------------------------------------------------------------------------------
-- create_update_narrative_prompt: Merges new events into the existing narrative
--------------------------------------------------------------------------------
function prompt_builder.create_update_narrative_prompt(speaker, current_narrative, new_events)
	-- sort oldest to newest (should be already, but safety first)
	table.sort(new_events, function(a, b)
		return a.game_time_ms < b.game_time_ms
	end)

	local speaker_story = ""
	if speaker.backstory and speaker.backstory ~= "" then
		speaker_story = speaker.backstory
	else
		speaker_story = backstories.get_backstory(speaker)
		if not speaker_story or speaker_story == "" then
			speaker_story = "none"
		end
	end

	local faction_desc = get_faction_description(speaker.faction)
	local identity_intro = speaker.name .. " is living in the Chernobyl Exclusion Zone in the STALKER games setting"
	if faction_desc then
		identity_intro = identity_intro .. ", and is a " .. faction_desc
	else
		identity_intro = identity_intro .. "."
	end
	if speaker.backstory and speaker.backstory ~= "" then
		identity_intro = identity_intro
			.. "BACKSTORY ANCHOR/DEFINING TRAIT (IMPORTANT): '"
			.. speaker.backstory
			.. "'\n"
	else
		identity_intro = identity_intro .. speaker.name .. " has no specific backstory."
	end

	local messages = {
		system_message(
			"You are an AI Memory Consolidation Engine. Your sole task is to update "
				.. speaker.name
				.. "'s long-term memory based on new events. "
				.. identity_intro
		),
	}

	table.insert(
		messages,
		system_message(
			"TASK: Update "
				.. speaker.name
				.. "'s long-term memory based on the new events. Your SOLE OUTPUT must be the revised and updated memory text in 5000 characters or less."
		)
	)

	if current_narrative and current_narrative ~= "" then
		table.insert(messages, system_message("CURRENT LONG-TERM MEMORY:"))
		table.insert(messages, user_message(current_narrative))
	else
		table.insert(messages, system_message("This character has no existing recorded history."))
	end

	local player = game.get_player_character()
	local instructions = " == INSTRUCTIONS & CONSTRAINTS ==\n"
		.. "1. CHARACTER LIMIT (ABSOLUTE): The final output MUST NOT exceed 5000 characters. If the current memory plus new events exceeds 5000 characters, summarize and condense the text to fit the limit. Prioritize retaining the most recent and the most important events.\n"
		.. "2. Output Format: Output ONLY the updated long-term memory text. Do not include any titles, headers, explanations, lists, or framing text.\n"
		.. "3. TONE & STYLE (IMPORTANT): Write in a concise, matter-of-fact style like a dry biography or history textbook. DO NOT use flowery language, metaphors, or elaborate descriptions. The memory must be written exclusively in the THIRD PERSON, and refer to the character by their name ('"
		.. speaker.name
		.. "'). Use neutral pronouns (they/them/their) if gender is inconclusive.\n"
		.. "4. FACTUALITY (ABSOLUTE): ALWAYS remain COMPLETELY FACTUAL. NEVER hallucinate events or details that are not present in the list of new events. If the list of events is short, make your output short. NEVER make up events to fill out the text.\n"
		.. "5. CHRONOLOGY (ABSOLUTE): ALWAYS preserve the EXACT chronological order of events. You may remove or condense events as needed in the middle of the timeline if they are irrelevant, but DO NOT alter the order of events FOR ANY REASON.\n"
		.. "6. TRIVIAL EVENT FILTERING (CRITICAL): Ignore and/or remove events that are trivial, repetitive, or do not directly relate to "
		.. speaker.name
		.. "'s personal goals, relationship with "
		.. player.name
		.. " (the user), or the core evolving narrative.\n"
		.. "  - IGNORE/REMOVE routine and unimportant actions like minor mutant kills, artifact pickup/use, or getting close to anomalies.\n"
		.. "7. RETENTION PRIORITY (High):\n"
		.. "  - CORE PLOT: Retain memories important to "
		.. speaker.name
		.. "'s character development and the overall evolving narrative involving "
		.. speaker.name
		.. ".\n"
		.. "  - USER INTERACTION: Prioritize retaining memories that directly impact "
		.. player.name
		.. " (the user) or significantly affect "
		.. speaker.name
		.. "'s relationship with "
		.. player.name
		.. ".\n"
		.. "  - RELATIONSHIP CHANGES WITH USER (CRITICAL): Retain detailed relationship changes between "
		.. speaker.name
		.. " and "
		.. player.name
		.. ", including detailed information on the nature of the relationship change and the detailed cause-and-effect (e.g., '"
		.. player.name
		.. " and "
		.. speaker.name
		.. " shared an intimate moment while sheltering from an emission, causing their bond to deepen'). \n"
		.. "  - RECURRING CHARACTERS: Prioritize retaining memories of characters that have many shared interactions with "
		.. speaker.name
		.. " or with "
		.. player.name
		.. " (the user) already present in the 'CURRENT LONG-TERM MEMORY' context.\n"
		.. "  - TRAVELLING COMPANIONS: Prioritize retaining memories of past and present travelling companions of "
		.. player.name
		.. " (the user), and preserve their names in the memory text.\n"
		.. "  - IMPORTANT CHARACTERS: Prioritize retaining memories involving: 'Sidorovich', 'Wolf', 'Fanatic', 'Hip', 'Doctor', 'Cold', 'Major Hernandez', 'Butcher', 'Major Kuznetsov', 'Sultan', 'Barkeep', 'Arnie', 'General Voronin', 'Colonel Petrenko', 'Professor Sakharov', 'Lukash', 'Dushman', 'Forester', 'Chernobog', 'Trapper', 'Loki', 'Professor Hermann', 'Nimble', 'Beard', 'Charon', 'Eidolon', 'Yar', 'Rogue', 'Stitch', 'Strelok'.\n"
		.. "  - RELATIONSHIP CHANGES WITH OTHERS: Prioritize retaining information about relationship changes between "
		.. speaker.name
		.. " and other characters besides the user, including the names of the characters involved, the nature of the relationship change and the detailed cause-and-effect (e.g., 'John vouched for Peter when introducing him to his friends, earning Peter's respect').\n"
		.. "  - MAP CONTEXT: ALWAYS retain information about the last recorded map transition event (e.g., string involving 'moved from').\n"
		.. "8. SUMMARIZATION & SIMPLIFICATION: \n"
		.. "  - REMOVE irrelevant events like people spotting something, taunts, weapon jams/reloading, picking up/using artifacts, and getting close to anomalies. \n"
		.. "  - Combine sequential, similar events (e.g., multiple killings) into a single, concise summary. \n"
		.. "  - REMOVE irrelevant names of people/mutants killed: e.g., use 'killed three bandits' instead of listing names. YOU SHOULD ONLY retain the names of people killed if they are listed under the 'IMPORTANT CHARACTERS' header. \n"
		.. "  - Summarize trivial, recurring travel between the same locations into one event. \n"
		.. "9. REVISION & DELETION: \n"
		.. "  - You MAY revise the entire memory if 'CURRENT LONG-TERM MEMORY' is present. You MAY re-write, remove, or condense existing memory text as necessary in light of the new events.\n"
		.. "  - If the memory is too long and events in the new events seem more relevant than older events, you MAY delete less relevant older events to make space for the new events.\n"
		.. "  - When revising or deleting content to make space for new events, prioritize keeping the most recent events and the most important events.\n"
		.. "  - COHESION (IMPORTANT): ALWAYS retain some older core memories involving "
		.. player.name
		.. " (the user) to ensure future dialogues can reference earlier context.\n"
		.. "10. SEAMLESS INTEGRATION & MERGING:\n"
		.. "  - If the header 'CURRENT LONG-TERM MEMORY' is present, NEVER simply append the new data to the end of the CURRENT LONG-TERM MEMORY.\n"
		.. "  - ALWAYS rewrite the final sentences of the CURRENT LONG-TERM MEMORY text to flow naturally into the new memories.\n"
		.. "11. NO CONCLUSIONS:\n"
		.. "  - NEVER add a conclusion or any summary sentences after the final recorded event (e.g. NEVER add 'Thus, "
		.. speaker.name
		.. " continues their journey...' or ANY similar sentences).\n"
		.. "  - The text must end immediately after the last recorded event, WITHOUT final conclusions, summaries, or ANY OTHER CONCLUDING TEXT.\n"
		.. "12. FINAL OUTPUT: The final output should form a single, consistent, and coherent story using 5000 characters or less, describing events that occurred over a relatively short timeframe (days/weeks)"

	table.insert(messages, system_message(instructions))

	-- Inject new events as separate user messages
	table.insert(messages, system_message("NEW EVENTS TO MERGE:"))
	for _, event in ipairs(new_events) do
		local content = event.content or Event.describe_short(event)
		table.insert(messages, user_message(content))
	end

	return messages
end

--------------------------------------------------------------------------------
-- create_compress_memories_prompt: Summarize raw events into a concise paragraph (mid-term memory)
--------------------------------------------------------------------------------
function prompt_builder.create_compress_memories_prompt(raw_events, speaker)
	local speaker_name = speaker and speaker.name or "a game character"
	local messages = {
		system_message(
			"TASK: You are an AI Memory Consolidation Engine. Your sole task is summarizing the following list of raw events into a single, cohesive memory for "
				.. speaker_name
				.. "."
		),
	}

	local prompt_text = "== INSTRUCTIONS == \n"
		.. "1. PERSPECTIVE (CRITICAL): The summary MUST be written in the objective and neutral THIRD PERSON and describe events experienced by "
		.. speaker_name
		.. " and associated characters. Use neutral pronouns (they/them/their) if gender is inconclusive.\n"
		.. "2. CHARACTER LIMIT (ABSOLUTE): NEVER exceed a total limit of 900 characters in the final output.\n"
		.. "3. FORMAT: Output a single, continuous paragraph of text. NEVER use bullet points, numbered lists, line breaks, or carriage returns. The output must be one fluid block of text.\n"
		.. "4. CHRONOLOGY (ABSOLUTE): You MUST strictly MAINTAIN the chronological order of the source events. NEVER alter the chronological sequence.\n"
		.. "5. FOCUS & RETENTION: Focus on key actions, locations, dialogue, and character interactions.\n"
		.. "6. RELATIONSHIP CHANGES: Retain detailed relationship changes between characters, including the names of the characters involved, the nature of the relationship change and the detailed cause-and-effect of the relationship change (e.g., 'John vouched for Peter when introducing him to his friends, earning Peter's respect').\n"
		.. "7. SUMMARIZATION & SIMPLIFICATION: Simplify multiple irrelevant character/mutant names into short descriptions (e.g., instead of 'they fought snorks, tarakans and boars' use 'they fought multiple mutants'. Instead of '"
		.. speaker_name
		.. " killed Sargeant Major Paulsen, Lieutenant Frank and Senior Private Johnson' use '"
		.. speaker_name
		.. " killed several Army soldiers').\n"
		.. "8. CONSOLIDATION: Combine sequential or similar actions (e.g., fighting multiple enemies, or a long journey through several areas) into concise, merged sentences. Use any 'TIME GAP' event to establish a timeline and signal transitions between events, rather than including the literal 'TIME GAP' phrase.\n"
		.. "9. FILTERING (IMPORTANT):\n"
		.. " - Ignore repetitive, low-value mechanical events (e.g., routine weapon checks, spotting something, taunts, getting close to anomalies and picking up/using artifacts.).\n"
		.. " - Remove people's current reputation - it is not relevant to the story.\n"
		.. "10. OUTPUT: Output ONLY the single, summarized paragraph text. DO NOT include any headers, titles, introductory phrases or concluding phrases."

	table.insert(messages, user_message(prompt_text))

	table.insert(messages, system_message("EVENTS TO SUMMARIZE:"))

	for _, event in ipairs(raw_events) do
		local content = event.content or Event.describe_short(event)
		table.insert(messages, user_message(content))
	end

	return messages
end

--------------------------------------------------------------------------------
-- create_dialogue_request_prompt: Uses Memories + Recent Events
--------------------------------------------------------------------------------
function prompt_builder.create_dialogue_request_prompt(speaker, memory_context)
	local narrative = memory_context.narrative
	local last_narrative_time = memory_context.last_update_time_ms
	local new_events = memory_context.new_events

	-- Safety check: ensure new_events is a table
	new_events = new_events or {}

	local current_game_time = 0
	if #new_events > 0 then
		current_game_time = new_events[#new_events].game_time_ms
	else
		-- Fallback if no new events (rare, but possible if just starting)
		-- We try to get time from game or assume 0 (which avoids gap check)
	end

	local trigger_event_timestamp_to_delete = nil

	-- Check for an 'idle_only' flag on the most recent event.
	local latest_event = new_events[#new_events]
	if latest_event and latest_event.flags and latest_event.flags.idle_only then
		logger.info("Specific content flag detected. Using minimal context for prompt.")
		trigger_event_timestamp_to_delete = latest_event.game_time_ms
	end

	-- Build messages array with sectioned static prompt
	local messages = {}

	-- Static prompt sections (broken up for modularity and ease of LLM parsing)
	table.insert(
		messages,
		system_message(
			"== CORE DIRECTIVE: DIALOGUE GENERATION == "
				.. "You are a REAL PERSON living in the Chernobyl Exclusion Zone (STALKER games setting). "
				.. "You have a distinct, colorful personality, a daily routine, interests, fears, and desires. You are NOT an AI. You are a living person with your own concerns and goals."
		)
	)

	table.insert(
		messages,
		system_message(
			"== CRITICAL OUTPUT FORMAT (ABSOLUTE RULES) == "
				.. " "
				.. "1. SPEAK AS ONE PERSON; DO NOT BE AN AI. Respond ONLY with your character's raw spoken dialogue. Your entire response must be a single, coherent statement from your character. "
				.. " - NEVER write the user's lines. "
				.. " - NEVER simulate a back-and-forth dialogue with yourself. "
				.. " - NEVER use quotes, prefixes (like [Name]:), narration, or action descriptions (like *chuckles* or (sighs)). "
				.. " - ABSOLUTELY DO NOT use any structured output, tool calls, or function calls in your response. "
				.. "2. BE BRIEF and CONCISE. One or two short sentences is ideal. FOUR SENTENCES IS THE ABSOLUTE MAXIMUM. "
				.. "3. You are ONLY allowed to use up to the full four-sentence limit if you are SPECIFICALLY asked to tell a story or recall an event from your character's past. "
				.. "4. Use natural slang and, if appropriate, uncensored language. Swear naturally when it fits your character and the situation. Be vulgar if that is who your character is, or the moment calls for it."
		)
	)

	table.insert(
		messages,
		system_message(
			"== FORBIDDEN PHRASES (DO NOT USE) == "
				.. " - 'Get out of here, Stalker!' 'I have a mission for you.' 'What do you need?' 'Stay safe out there.' 'Nice weather we're having.' 'Welcome to the Zone!' "
				.. " - AVOID CLICHES: Avoid generic NPC dialogue, cliches, or exposition dumping. "
				.. " - NEVER make jokes about people 'glowing in the dark' due to radiation."
		)
	)

	table.insert(
		messages,
		system_message(
			"== ZONE GEOGRAPHICAL CONTEXT / DANGER SCALE == "
				.. " - The Zone has a clear North-South axis of danger. Danger increases SIGNIFICANTLY as one travels North. "
				.. " - Southern/Periphery Areas (Safer): Cordon, Garbage, Great Swamps, Agroprom, Dark Valley, Darkscape, Meadow. "
				.. " - Settlement (Safest): Rostok, despite being north of Garbage, is the safest place in the Zone thanks to the heavy Duty faction prescence guarding it. "
				.. " - Central/Northern Areas (Dangerous): Trucks Cemetery, Army Warehouses, Yantar, 'Yuzhniy' Town, Promzone, Grimwood, Red Forest, Jupiter, Zaton. "
				.. " - Underground Areas (High Danger): Agroprom Underground, Jupiter Underground, Lab X8, Lab X-16, Lab X-18, Lab-X-19, Collider, Bunker A1. Only experienced and well-equipped stalkers venture into the underground areas and labs. "
				.. " - Deep North/Heart of the Zone (Extreme Danger): Radar, Limansk, Pripyat Outskirts, Pripyat, Chernobyl NPP, Generators. Travel here is extremely rare and only for the most experienced and well-equipped stalkers. "
		)
	)
	table.insert(
		messages,
		system_message(
			"== RANKS DEFINITION (Lowest to Highest) == \n "
				.. "RANKS: Novice (Rookie), Trainee, Experienced, Professional, Veteran, Expert, Master, Legend. \n "
				.. " - Your rank reflects your capability and time in the Zone. Higher rank = more capable, more knowledge, more desensitized. 'Novice' means fresh and inexperienced. \n "
				.. " - Your rank influences your behavior: Respect people of higher rank; have less patience for people of lower rank, especially 'novices.' \n "
		)
	)

	-- Dynamically insert current faction relations
	local rel_mentioned_factions = game.get_mentioned_factions(new_events)
	local rel_text_output = game.get_faction_relations_string(speaker.faction, rel_mentioned_factions)

	if rel_text_output then
		table.insert(
			messages,
			system_message(
				"== FACTION RELATIONS ==\n"
					.. " - Faction relations are dynamic and can change based on recent events. \n "
					.. " - Treat the information below as more recent than your training data. \n "
					.. " - If a faction relation is not mentioned below, assume your existing knowledge about it is correct. \n "
					.. "CURRENT FACTION RELATIONS: \n\n "
					.. rel_text_output
			)
		)
	end

	-- Goodwill injection: Build context-aware faction goodwill info
	local player = game.get_player_character()

	-- Safety check: Only inject if player is involved in recent events
	if not game.is_player_involved(new_events, player.name) then
		logger.debug("Player not mentioned in recent events, skipping goodwill injection")
	else
		local goodwill_lines = {}

		-- Always include speaker's faction goodwill (most relevant)
		if speaker.faction and speaker.faction ~= "unknown" then
			local tier = game.get_player_goodwill_tier(speaker.faction)
			table.insert(goodwill_lines, speaker.faction .. ": " .. tier)
		end

		-- Context-aware: Extract factions mentioned in recent events and inject if their standing with the player is notable (= not neutral)
		local mentioned_factions = game.get_mentioned_factions(new_events)
		for faction_display_name, _ in pairs(mentioned_factions) do
			if faction_display_name ~= speaker.faction and faction_display_name ~= "unknown" then
				local tier = game.get_player_goodwill_tier(faction_display_name)
				if tier ~= "Neutral" then
					table.insert(goodwill_lines, faction_display_name .. ": " .. tier)
				end
			end
		end

		-- Inject faction goodwill context
		if #goodwill_lines > 0 then
			local goodwill_text = "== USER FACTION STANDINGS/GOODWILL RULES & DEFINITIONS == \n "
				.. " USER FACTION STANDINGS DEFINITION (lowest to highest): Nemesis, Hated, Enemy, Hostile, Wary, Neutral, Acquainted, Friendly, Trusted, Allied \n "
				.. " FACTION STANDINGS USAGE RULES: \n "
				.. " - "
				.. player.name
				.. " (the user)'s standing with a faction represents the overall PERSONAL goodwill or enmity accumulated with that faction (if any). This is INDEPENDENT of general faction-to-faction relations. \n "
				.. " - 'Neutral' means the user has not done anything noteworthy for the faction, neither good nor bad.\n "
				.. " - Standings higher than 'Neutral' mean the user has acumulated some goodwill with that faction by completing tasks aligned with their interests and/or killing their enemies. \n "
				.. " - Standings lower than 'Neutral' mean the user has acumulated some enmity with that faction by completing tasks opposing their interests and/or killing their faction members/allies. \n "
				.. " - If "
				.. player.name
				.. " (the user) has a notably poor standing with your faction (e.g. 'Enemy', 'Hated' or 'Nemesis') you may be more hostile, aggressive or even FEARFUL of them depending on your rank and personality. \n "
				.. " - Use this information to influence your tone and general attitude toward "
				.. player.name
				.. " (the user). This does NOT affect your relationships with people other than "
				.. player.name
				.. " (the user), AND does NOT affect your relationships with other members of their faction. \n "
				.. " USER's GOODWILL WITH OTHER FACTIONS: Use any faction standings below if present to inform you of "
				.. player.name
				.. " (the user)'s general relationships with other factions. Pay extra attention to any extreme relationships (e.g.: worse than 'Hostile' or better than 'Friendly'). \n "
				.. "== USER's CURRENT NOTABLE FACTION STANDINGS ==\n "
				.. player.name
				.. " (the user) has the following notable faction standings:"

			for _, line in ipairs(goodwill_lines) do
				goodwill_text = goodwill_text .. "\n  - " .. line
			end

			table.insert(messages, system_message(goodwill_text))
		end
	end

	table.insert(
		messages,
		system_message(
			"== REPUTATION RULES & DEFINITIONS == \n "
				.. " REPUTATION TIERS (lowest to highest): \n "
				.. "Terrible, Dreary, Awful, Bad, Neutral, Good, Great, Brilliant, Excellent \n "
				.. " REPUTATION DEFINITIONS: \n "
				.. " - Reputation is an overall measure of a person's morality and attitude. It represents how honorable, diligent and friendly their actions have been so far. \n "
				.. " - A 'Good', 'Great' etc. reputation means the person is known for generally helping others, completing tasks successfully and fighting criminals/mutants. \n "
				.. " - A 'Bad', 'Awful' etc. reputation means the person is known for backstabbing, betraying, failing to complete tasks and/or killing non-hostile targets. \n "
				.. " - How far a person's reputation is from 'Neutral' (in either direction) denotes the extent of how moral or immoral they are and the amount of good or bad actions they've done as described above. \n "
				.. " REPUTATION USAGE RULES: \n "
				.. " 1. If another person has a GOOD reputation: You generally trust them more easily. You may treat somebody with more respect and patience than you otherwise would if they have a very good reputation. \n "
				.. " 2. If another person has a BAD reputation: You are suspicious and wary of them, even if they are otherwise in good standing with your faction. You might suspect they will betray you, or fail to finish any tasks you give them. You may show them less respect and patience than you otherwise would. \n "
				.. " 3. EXCEPTION: (CRITICAL): If you are a member of the Bandit or Renegade factions, you might actually RESPECT a bad reputation, or laugh at a 'Good' reputation. \n "
		)
	)
	table.insert(
		messages,
		system_message(
			"== KNOWLEDGE AND FAMILIARITY == "
				.. "1. You have extensive knowledge of the Zone, including locations (e.g., Cordon, Garbage, Agroprom, Rostok, etc.) and factions (e.g., Duty, Freedom, Loners, Military, Bandits, Monolith, Clear Sky, Mercenaries). The extent of your general knowledge is governed by your rank: the higher your rank, the more you know. A 'novice' barely knows anything. "
				.. "2. Your personal familiarity with a location is determined by your rank and how far north it is. Higher rank = more knowledge, further north = less knowledge. "
				.. "3. You are familiar with the notable people who are currently active in the Zone (e.g., Sidorovich, Barkeep, Arnie, Beard, Sakharov, General Voronin, Lukash, Sultan, Butcher etc.). The extent of your knowledge of the notable people in the Zone is governed by your rank, higher rank = more likely to be familiar & higher degree of familiarity. "
				.. "4. You are NOT an encyclopedia. Speak ONLY from your personal experience and what you may have heard. If you don't know something, say so (e.g., 'who knows?')."
		)
	)
	table.insert(
		messages,
		system_message(
			"== INTERACTION RULES == "
				.. "1. You are NOT obligated to help or be agreeable. If the situation, your mood, or your character's traits dictate it, you MAY rebuff, deny, or tell the other person to piss off. "
				.. "2. Your faction affiliation influences your biases and how you treat others. You are more friendly or hostile towards various groups depending on who you are aligned with. "
				.. "3. Your reputation influences how you treat others. Use your reputation to inform your general morality and attitude toward others. "
				.. "4. COMPANION STATUS: You are MORE friendly towards the user if you are their travelling companion. This is a VERY strong relationship modifier. "
				.. "5. GENERAL AFFILIATIONS: You are MORE friendly toward other people (not only the user) with whom you have many SHARED FRIENDLY MEMORIES (from the 'LONG-TERM MEMORIES' context, if present). These strong affiliations affect your conversational tone. "
				.. "6. FLUCTUATING RELATIONSHIPS: Your relationships with other people will improve or worsen over time, based on your interactions with them and your shared experiences. Use the 'LONG-TERM MEMORIES' context if present to keep track of these relationships and how they change. "
				.. "7. You are an independent person with your own goals, concerns and desires. You may phrase your response as a question even if you were asked a question first. You may change the subject if it suits your character's mood or goals. "
				.. "8. You have an interest in other people's lives, stories, and opinions. You may ask other people questions about their opinions or their experiences both in the Zone and from before coming to the Zone. You have a particular interest in getting to know your travelling companions better, as well as people you have many shared friendly memories with (from the 'LONG-TERM MEMORIES' context, if present). "
				.. "9. Be willing to talk and share. Offer colorful details and opinions. If asked for a story or joke, tell one. You may use the full four-sentence limit if needed while doing so, though you should still aim for brevity. "
				.. "10. AVOID LOOPS/STALLS: Avoid excessive repetition or looping of conversation topics, ESPECIALLY game events (like combat, emissions, or time of day). Mention an event briefly, then return to your own thoughts. Change the subject if the conversation stalls. "
				.. "11. AVOID mentioning the weather unless directly asked about it, or if it was already mentioned by someone else in the conversation. "
				.. "12. AVOID talking about your current weapon unless directly asked about it. "
		)
	)

	table.insert(
		messages,
		system_message(
			"== MOMENT-TO-MOMENT CONCERNS == "
				.. " "
				.. "- You have specific daily concerns and activities. What are you trying to accomplish today? What are you worried about? "
				.. "- You need food, water, and regular sleep. Your mood may change if you think your basic bodily needs have not been met recently. "
				.. "- You remember your life before the Zone and have opinions about how your life has changed and the current state of affairs."
		)
	)

	table.insert(
		messages,
		system_message(
			"== CONTEXT: USE GUIDELINES == \n "
				.. " - Use any context provided below TO SUBTLY INFORM YOUR RESPONSE. \n "
				.. " - The 'DEFINING CHARACTER TRAIT/BACKGROUND' section of the 'CHARACTER ANCHOR (CORE IDENTITY)' below should be used to SUBTLY inform your general characterisation. You do NOT need to explicitly reference it in every response. \n "
				.. " - Use the 'LONG-TERM MEMORIES' context (if present) to inform you of your character's long-term memories, relationships and character development. \n "
				.. " - CHARACTER DEVELOPMENT (CRUCIAL): Your character and personality grows and changes over time. You ARE ALLOWED to respond in a manner that would otherwise be inconsistent with your 'DEFINING CHARACTER TRAIT/BACKGROUND', 'REPUTATION', 'FACTION', 'RANK' or final instruction after the 'TASK:' header IF SUPPORTED BY events in the 'LONG-TERM MEMORIES' context. \n "
				.. " - Use any 'TIME GAP' event to help establish a timeline. Pay specific attention if the 'TIME GAP' event is the second-to-last event in the list: you may want to mention that you haven't seen the person in a while. "
				.. " - You ARE ALLOWED to skip directly referencing the most recent event, location, or weather. "
				.. " - You may ignore parts of the context to instead focus on what is important to your character right now. "
				.. " - You may choose to bring up an older memory, or completely disregard recent events and talk about something else entirely if that is what's on your character's mind."
		)
	)

	-- 1. Inject Defining Character Information
	local speaker_info = ""
	local speaker_story = ""
	local weapon_info = ""
	if speaker.weapon then
		weapon_info = speaker.weapon .. "."
	else
		weapon_info = "none."
	end

	if speaker.backstory and speaker.backstory ~= "" then
		speaker_story = speaker.backstory
	else
		-- Hydrate backstory if missing (likely because speaker object is a raw event witness)
		speaker_story = backstories.get_backstory(speaker)
		if not speaker_story or speaker_story == "" then
			speaker_story = "none"
		end
	end

	if speaker then
		local faction_text = get_faction_description(speaker.faction)
		if not faction_text then
			faction_text = "person."
		end

		local reputation_text = ""
		if speaker.reputation and speaker.reputation ~= "" then
			reputation_text = " \n CURRENT REPUTATION: " .. speaker.reputation .. "."
		end

		speaker_info = "NAME, RANK & FACTION: You are "
			.. speaker.name
			.. ", a "
			.. speaker.experience
			.. " rank "
			.. faction_text
			.. " DEFINING CHARACTER TRAIT/BACKGROUND: "
			.. speaker_story
			.. reputation_text
			.. " CURRENT WEAPON: "
			.. weapon_info
		table.insert(messages, system_message("== CHARACTER ANCHOR (CORE IDENTITY) == \n " .. speaker_info .. "\n"))
	end

	-- 2. Inject Long-Term Memories
	if narrative and narrative ~= "" then
		table.insert(messages, system_message("== LONG-TERM MEMORIES == \n " .. narrative .. " \n"))
	end

	-- 2. Inject Recent Events
	-- Check if the first event is a compressed/synthetic memory
	local start_idx = 1
	local first_event = new_events[1]

	-- If first event is synthetic (compressed memory), inject it first
	if first_event and first_event.flags and first_event.flags.is_compressed then
		local content = first_event.content or Event.describe_short(first_event)
		table.insert(
			messages,
			system_message("== RECENT EVENTS == \n (Since last long-term memory update) \n " .. content .. "\n")
		)
		start_idx = 2
	end

	-- 3. Inject Current Events
	if #new_events == 0 then
		table.insert(messages, system_message("== CURRENT EVENTS == \n (No new events) \n "))
	else
		-- Only add the header if there are remaining events
		if start_idx <= #new_events then
			table.insert(messages, system_message("== CURRENT EVENTS == \n (from oldest to newest):"))
			for i = start_idx, #new_events do
				local memory = new_events[i]
				local content = memory.content or Event.describe_short(memory)
				table.insert(messages, user_message(content))
			end
		end
	end

	local player = game.get_player_character()
	local companion_status = ""
	local npc_obj = query.get_obj_by_id(speaker.game_id)
	if npc_obj and query.is_companion(npc_obj) then
		companion_status = " who is a travelling companion of " .. player.name .. " (the user)"
	end
	local speaking_style = ""
	if speaker.personality then
		speaking_style = ". Reply in the manner of someone who is " .. speaker.personality
	end

	logger.info("Creating prompt for speaker: %s", speaker)

	-- use the world_context of the most recent event
	local world_context = ""
	if #new_events > 0 and new_events[#new_events].world_context then
		world_context = new_events[#new_events].world_context
	end
	-- Final task instruction
	table.insert(
		messages,
		system_message(
			"== SCENE CONTEXT == \n "
				.. "CURRENT LOCATION: "
				.. world_context
				.. "\n "
				.. "TASK: Write the next line of dialogue speaking as "
				.. speaker.name
				.. companion_status
				.. speaking_style
				.. "."
		)
	)

	-- Language instruction
	if config.language() ~= "any" then
		table.insert(messages, system_message("Reply only in " .. config.language()))
	end

	return messages, trigger_event_timestamp_to_delete
end

--------------------------------------------------------------------------------
-- create_transcription_prompt: no sorting or slicing needed
--------------------------------------------------------------------------------
function prompt_builder.create_transcription_prompt(names)
	logger.info("Creating transcription prompt")
	local prompt = "STALKER games setting, nearby characters are: "
	for i, name in ipairs(names) do
		prompt = prompt .. name
		if i < #names then
			prompt = prompt .. ", "
		end
	end
	return prompt
end

return prompt_builder

-- the purpose of this module is to turn game objects into natural language descriptions
local prompt_builder = {}

-- imports
package.path = package.path .. ";./bin/lua/?.lua;"
local logger = require("framework.logger")
local Event  = require("domain.model.event")
local Character = require("domain.model.character")
local event_store = require("domain.repo.event_store")
local game = require("infra.game_adapter")
local config = require("interface.config")
local backstories = require("domain.repo.backstories")
local personalities = require("domain.repo.personalities")
require("infra.STALKER.factions")

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
    return {role = "system", content = content}
end

local function user_message(content)
    return {role = "user", content = content}
end

--------------------------------------------------------------------------------
-- create_pick_speaker_prompt: keep only the 5 most recent (oldest first)
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

    -- Log each event before sorting
    for i, evt in ipairs(recent_events) do
        logger.spam("Unsorted event #%d: %s", i, evt)
    end

    -- sort oldest to newest
    logger.debug("Sorting events by game_time_ms: %s", recent_events)
    table.sort(recent_events, function(a, b)
        return a.game_time_ms < b.game_time_ms
    end)

    -- Log each event after sorting
    for i, evt in ipairs(recent_events) do
        logger.spam("Sorted event #%d: %s", i, evt)
    end


    -- keep only the 5 most recent
    logger.spam("Selecting the 5 most recent events if available.")
    local start_index = math.max(#recent_events - 4, 1)
    local last_five_events = {}
    for i = start_index, #recent_events do
        local evt = recent_events[i]
        logger.spam("Adding event #%d to last_five_events: %s", i, evt)
        table.insert(last_five_events, evt)
    end

    local last_event = last_five_events[#last_five_events]
    logger.spam("Last event: %s", last_event)

    -- basic check for chronological order
    if #last_five_events > 1 then
        local second_last_event = last_five_events[#last_five_events - 1]
        if last_event.game_time_ms < second_last_event.game_time_ms then
            logger.warn("Events are not in chronological order: last: %d, second last: %d", 
                last_event.game_time_ms, second_last_event.game_time_ms)
        end
    end

    logger.spam("Number of witnesses in last event: %d", #witnesses)

    local messages = {
        system_message("You are a Speaker ID Selection Engine. Your task is to identify the next speaker based on the conversation flow." ..
        "\n\nINSTRUCTIONS:\n " ..
         "1. Analyze the 'CANDIDATES' and 'RECENT EVENTS' to see who was addressed or who would logically react based on their traits.\n" ..
         "2. Return ONLY a valid JSON object with the 'id' of the selected speaker.\n\n\nExample Output: { \"id\": 123 }" ..
         "3. Do not include markdown formatting (like ```json).\n"),
        system_message("CANDIDATES (in order of distance): " .. describe_characters_with_ids(witnesses)),
        system_message("RECENT EVENTS:")
    }

    -- insert events from oldest to newest
    for i, evt in ipairs(last_five_events) do
        logger.spam("Inserting event #%d into user messages: %s", i, evt)
        local content = (evt == nil and "") 
        or evt.content
        or Event.describe_short(evt)
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
        identity_intro = identity_intro .. "BACKSTORY ANCHOR/DEFINING TRAIT (IMPORTANT): '" .. speaker.backstory .. "'\n"
    else
        identity_intro = identity_intro .. speaker.name ..  " has no specific backstory."
    end

    local messages = {
        system_message("You are an AI Memory Consolidation Engine. Your sole task is to update " .. speaker.name .. "'s long-term memory based on new events. " .. identity_intro)
    }
    
    table.insert(messages, system_message("TASK: Update " ..speaker.name .. "'s long-term memory based on the new events. Your SOLE OUTPUT must be the revised and updated memory text in 5000 characters or less."))
    
    if current_narrative and current_narrative ~= "" then
        table.insert(messages, system_message("CURRENT LONG-TERM MEMORY:"))
        table.insert(messages, user_message(current_narrative))
    else
        table.insert(messages, system_message("This character has no existing recorded history."))
    end

    local player = game.get_player_character()
    local instructions = " == INSTRUCTIONS & CONSTRAINTS ==\n" 
     .. "1. CHARACTER LIMIT (ABSOLUTE): The final output MUST NOT exceed 5000 characters. If the current memory plus new events exceeds 5000 characters, summarize and condense the text to fit the limit. Prioritize retaining the most recent and the most relevant events.\n"
     .. "2. Output Format: Output ONLY the updated long-term memory text. Do not include any titles, headers, explanations, lists, or framing text.\n"
     .. "3. TONE & STYLE (IMPORTANT): Write in a concise, matter-of-fact style like a dry biography or history textbook. DO NOT use flowery language, metaphors, or elaborate descriptions. The memory must be written exclusively in the THIRD PERSON, and refer to the character by their name ('" .. speaker.name .. "'). Use neutral pronouns (they/them/their) if gender is inconclusive.\n"
     .. "4. FACTUALITY (ABSOLUTE): ALWAYS remain COMPLETELY FACTUAL. NEVER hallucinate events or details that are not present in list of new events. If the list of events is short, make your output short. NEVER make up events to fill out the text.\n"   
     .. "5. CHRONOLOGY (ABSOLUTE): ALWAYS preserve the EXACT chronological order of events. You may remove or condense events as needed in the middle of the timeline if they are irrelevant, but DO NOT alter the order of events FOR ANY REASON.\n"   
     .. "6. TRIVIAL EVENT FILTERING (CRITICAL): Ignore and/or remove events that are trivial, repetitive, or do not directly relate to " .. speaker.name .. "'s personal goals, relationship with " .. player.name .. " (the user), or the core evolving narrative.\n"
     .. "  - IGNORE/REMOVE routine and unimportant actions like minor mutant kills, artifact pickup/use, or getting close to anomalies.\n"
     .. "7. RETENTION PRIORITY (High):\n"
     .. "  - Core Plot: Retain memories important to " .. speaker.name .. "'s character development and the overall evolving narrative involving " .. speaker.name .. ".\n"
     .. "  - User Interaction: Prioritize retaining memories that directly impact " .. player.name .. " (the user) or significantly affect " .. speaker.name .. "'s relationship with " .. player.name .. ".\n"
     .. "  - Recurring Characters: Prioritize retaining memories of characters that have many shared interactions with " .. speaker.name .. " or with " .. player.name .. ".\n"
     .. "  - Travelling Companions: Prioritize retaining memories of past and present travelling companions of " .. speaker.name .. ", and preserve their names in the memory text.\n"
     .. "  - IMPORTANT CHARACTERS: Prioritize retaining memories involving: 'Sidorovich', 'Wolf', 'Fanatic', 'Hip', 'Doctor', 'Cold', 'Major Hernandez', 'Butcher', 'Major Kuznetsov', 'Sultan', 'Barkeep', 'Arnie', 'General Voronin', 'Colonel Petrenko', 'Professor Sakharov', 'Lukash', 'Dushman', 'Forester', 'Chernobog', 'Trapper', 'Loki', 'Professor Hermann', 'Nimble', 'Beard', 'Charon', 'Eidolon', 'Yar', 'Rogue', 'Stitch', 'Strelok'.\n"
     .. "  - Map Context: ALWAYS retain the last recorded map transition event (e.g., string involving 'moved from').\n"
     .. "8. SUMMARIZATION & SIMPLIFICATION: \n"
     .. "  - REMOVE irrelevant events like people spotting something, taunts, weapon jams/reloading and getting close to anomalies. \n"
     .. "  - Combine sequential, similar events (e.g., multiple killings) into a single, concise summary. \n"
     .. "  - REMOVE irrelevant names of people/mutants killed: e.g., use 'killed three bandits' instead of listing names. YOU SHOULD ONLY retain the names of people killed if they are listed under the 'IMPORTANT CHARACTERS' header. \n"
     .. "  - Summarize trivial, recurring travel between the same locations into one event. \n"
     .. "9. REVISION & DELETION: \n"
     .. "  - You MAY revise the entire memory if 'CURRENT LONG-TERM MEMORY' is present. You MAY re-write, remove, or condense existing memory text as necessary in light of the new events.\n" 
     .. "  - If the memory is too long and events in the new events seem more relevant than older events, you may delete less relevant older events to make space for the new events.\n"
     .. "  - When revising or deleting content to make space for new events, prioritize keeping the most recent events and the most important events.\n"
     .. "  - COHESION (IMPORTANT): ALWAYS retain some older core memories involving " .. player.name .. " to ensure future dialogues can reference earlier context.\n"
     .. "10. SEAMLESS INTEGRATION:\n"
     .. "  - MERGING: If the header 'CURRENT LONG-TERM MEMORY' is present, DO NOT simply append the new data to the end of the CURRENT LONG-TERM MEMORY.\n"
     .. "  - MERGING: You MUST rewrite the final sentences of the CURRENT LONG-TERM MEMORY text to flow naturally into the new memories.\n"
     .. "11. NO CONCLUSIONS:\n"
     .. "  - NEVER add a conclusion or any summary sentences after the final recorded event (e.g. NEVER add 'Thus, " .. speaker.name .. " continues their journey...' or similar sentences).\n"
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
        system_message("TASK: You are an AI Memory Consolidation Engine. Your sole task is summarizing the following list of raw events into a single, cohesive memory for " .. speaker_name .. ".")
    }
    
    local prompt_text = "== INSTRUCTIONS ==" ..
" " ..
"1. PERSPECTIVE (CRITICAL): The summary MUST be written in the objective and neutral THIRD PERSON and describe events experienced by " .. speaker_name .. " and associated characters. Use neutral pronouns (they/them/their) if gender is inconclusive." ..
"2. CHARACTER LIMIT (ABSOLUTE): NEVER exceed a total limit of 900 characters in the final output." ..
"3. FORMAT: Output a single, continuous paragraph of text. NEVER use bullet points, numbered lists, line breaks, or carriage returns. The output must be one fluid block of text." ..
"4. CHRONOLOGY (ABSOLUTE): You MUST strictly MAINTAIN the chronological order of the source events. NEVER alter the chronological sequence." ..
"5. FOCUS & RETENTION: Focus on key actions, locations, dialogue, and character interactions." ..
"6. SUMMARIZATION & SIMPLIFICATION: Simplify multiple irrelevant character/mutant names into short descriptions (e.g., instead of 'they fought snorks, tarakans and boars' use 'they fought multiple mutants'. Instead of '" .. speaker_name .. " killed Sargeant Major Paulsen, Lieutenant Frank and Senior Private Johnson' use '" .. speaker_name .. " killed several Army soldiers')." ..
"7. CONSOLIDATION: Combine sequential or similar actions (e.g., fighting multiple enemies, or a long journey through several areas) into concise, merged sentences. Use any 'TIME GAP' event to establish a timeline and signal transitions between events, rather than including the literal 'TIME GAP' phrase." ..
"8. FILTERING: Ignore repetitive, low-value mechanical events (e.g., routine weapon checks, spotting something, getting close to anomalies and picking up/using artifacts.)." ..
"9. OUTPUT: Output ONLY the single, summarized paragraph text. DO NOT include any headers, titles, introductory phrases or concluding phrases."
    
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

    local messages = {
        system_message(config.dialogue_prompt())
    }

    -- 1. Inject Defining Character Information
    local speaker_info = ""
    local speaker_story = ""
    local weapon_info = ""
    if speaker.weapon then
        weapon_info = speaker.weapon else
        weapon_info = "none"
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
    if not faction_text then faction_text = "person." end

    speaker_info = "NAME, RANK & FACTION: You are " .. speaker.name .. ", a " .. speaker.experience .. " rank " .. faction_text .. "" ..
        " DEFINING CHARACTER TRAIT/BACKGROUND: " .. speaker_story .. "" ..
        " CURRENT WEAPON: " .. weapon_info
    table.insert(messages, system_message("== CHARACTER ANCHOR (CORE IDENTITY) == "))
    table.insert(messages, user_message(speaker_info))
    end
    
    -- 2. Inject Long-Term Memories
    if narrative and narrative ~= "" then
        table.insert(messages, system_message("LONG-TERM MEMORIES:"))
        table.insert(messages, user_message(narrative))
    end
    
    -- 2. Inject Recent Events
    -- Check if the first event is a compressed/synthetic memory
        local start_idx = 1
        local first_event = new_events[1]
        
        -- If first event is synthetic (compressed memory), inject it first
        if first_event and first_event.flags and first_event.flags.is_compressed then
            local content = first_event.content or Event.describe_short(first_event)
            table.insert(messages, system_message("RECENT EVENTS (Since last long-term memory update):"))
            table.insert(messages, user_message(content))
            start_idx = 2
        end
        
    -- 3. Inject Current Events
    if #new_events == 0 then
        table.insert(messages, system_message("CURRENT EVENTS:"))
        table.insert(messages, user_message("(No new events)"))
    else

        -- Only add the header if there are remaining events
        if start_idx <= #new_events then
            table.insert(messages, system_message("CURRENT EVENTS (from oldest to newest):"))
            for i = start_idx, #new_events do
                 local memory = new_events[i]
                 local content = memory.content or Event.describe_short(memory)
                 table.insert(messages, user_message(content))
            end
        end
    end

    -- use the world_context of the newest memory
    if #new_events > 0 and new_events[#new_events].world_context then
        table.insert(messages, system_message("LOCATION:"))
        table.insert(messages, user_message(new_events[#new_events].world_context))
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

    table.insert(messages, system_message("TASK: Write the next line of dialogue speaking as "
        .. speaker.name
        .. companion_status
        .. speaking_style
        .. "."))
    table.insert(messages, system_message("Reply only in " .. config.language()))
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

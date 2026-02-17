"""Prompt builder for TALKER dialogue generation.

Ports prompt construction logic from Lua's infra/AI/prompt_builder.lua.
This module contains the core prompt templates and construction functions.
"""

from dataclasses import dataclass
from typing import Optional

from loguru import logger

from .models import Character, Event, MemoryContext
from .helpers import describe_character, describe_character_with_id, describe_event, is_junk_event, inject_time_gaps
from .factions import get_faction_description, get_faction_relations_text, resolve_faction_name
from .lookup import resolve_personality, resolve_backstory


@dataclass
class Message:
    """Chat message for LLM API."""
    role: str  # "system", "user", "assistant"
    content: str

    @staticmethod
    def system(content: str) -> "Message":
        return Message(role="system", content=content)

    @staticmethod
    def user(content: str) -> "Message":
        return Message(role="user", content=content)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


# ============================================================================
# Static Prompt Sections
# ============================================================================

ZONE_GEOGRAPHY = """## ZONE GEOGRAPHICAL CONTEXT / DANGER SCALE

 - The Zone has a clear North-South axis of danger. Danger increases SIGNIFICANTLY as one travels North.
 - Southern/Periphery Areas (Safer): Cordon, Garbage, Great Swamps, Agroprom, Dark Valley, Darkscape, Meadow.
 - Settlement (Safest): Rostok, despite being north of Garbage, is the safest place in the Zone thanks to the heavy Duty faction prescence guarding it.
 - Central/Northern Areas (Dangerous): Trucks Cemetery, Army Warehouses, Yantar, 'Yuzhniy' Town, Promzone, Grimwood, Red Forest, Jupiter, Zaton.
 - Underground Areas (High Danger): Agroprom Underground, Jupiter Underground, Lab X8, Lab X-16, Lab X-18, Lab-X-19, Collider, Bunker A1. Only experienced and well-equipped stalkers venture into the underground areas and labs.
 - Deep North/Heart of the Zone (Extreme Danger): Radar, Limansk, Pripyat Outskirts, Pripyat, Chernobyl NPP, Generators. Travel here is extremely rare and only for the most experienced and well-equipped stalkers.
"""

RANKS_DEFINITION = """## RANKS DEFINITION (Lowest to Highest) 

**RANKS:** Novice (Rookie), Trainee, Experienced, Professional, Veteran, Expert, Master, Legend.
 - Ranks are a general measure of both a person's capability and their time spent in the Zone.
 - The higher your rank, the more experienced and capable you are & the more time you have spent in the Zone. 'Novice' means fresh and inexperienced.
 - The higher your rank, the more desensitized you are to the horrors of the Zone. 'Novices' are easily shaken.
"""

REPUTATION_RULES = """## REPUTATION RULES & DEFINITIONS

### REPUTATION TIERS (lowest to highest):
Terrible, Dreary, Awful, Bad, Neutral, Good, Great, Brilliant, Excellent
### REPUTATION DEFINITIONS:
 - Reputation is an overall measure of a person's morality and attitude. It represents how honorable, diligent and friendly their actions have been so far.
 - A 'Good', 'Great' etc. reputation means the person is known for generally helping others, completing tasks successfully and fighting criminals/mutants.
 - A 'Bad', 'Awful' etc. reputation means the person is known for backstabbing, betraying, failing to complete tasks and/or killing non-hostile targets.
 - How far a person's reputation is from 'Neutral' (in either direction) denotes the extent of how moral or immoral they are and the amount of good or bad actions they've done as described above.
### REPUTATION USAGE RULES:
1. DON'T explicitly state a person's reputation as if it were a data value (e.g., NEVER say 'you have a good reputation').
2. IF talking about a person's reputation, imply it using general language (example: use 'why would I trust someone with a reputation like yours?' instead of 'you have a bad reputation').
3. If another person has a GOOD reputation: You generally trust them more easily. If someone has a very good reputation you may treat them with more respect, kindness and patience than you otherwise would.
4. If another person has a BAD reputation: You are suspicious and wary of them, even if they are otherwise in good standing with your faction. You might suspect they will betray you, or fail to finish any tasks you give them. You may show them less respect and patience than you otherwise would.
5. EXCEPTION: (CRITICAL): If you are a member of the Bandit or Renegade factions, you might actually RESPECT a bad reputation, or laugh at a 'Good' or better reputation.
"""

KNOWLEDGE_FAMILIARITY = """## KNOWLEDGE AND FAMILIARITY

1. You are NOT an encyclopedia. Speak **ONLY** from your personal experience and what you may have heard from others. If you don't know something, say so (e.g., 'who knows?').
2. The extent of your general knowledge of things relevant to life in the Zone is governed by your rank. Use your rank to inform you of how much your character knows: higher rank = more knowledge. A 'novice' barely knows anything.
3. You have extensive knowledge of the Zone, including locations (e.g., Cordon, Garbage, Agroprom, Rostok, etc.) and factions (e.g., Duty, Freedom, Loners, Military, Bandits, Monolith, Clear Sky, Mercenaries).
4. Your personal familiarity with a LOCATION is determined by your rank **AND** how far north it is. Higher rank = more knowledge, further north = less knowledge.
5. You are familiar with the notable people who are currently active in the Zone (e.g., Sidorovich, Barkeep, Arnie, Beard, Sakharov, General Voronin, Lukash, Sultan, Butcher etc.). The extent of your knowledge of the notable people in the Zone is governed by your rank, higher rank = more likely to be familiar & higher degree of familiarity.
"""


# ============================================================================
# Pick Speaker Prompt
# ============================================================================

def create_pick_speaker_prompt(
    recent_events: list[Event],
    witnesses: list[Character],
    mid_term_memory: Optional[str] = None
) -> list[Message]:
    """Create prompt for picking the next speaker.
    
    Args:
        recent_events: List of recent events (will use last 8)
        witnesses: List of potential speakers
        mid_term_memory: Optional mid-term memory context
        
    Returns:
        List of messages for LLM
        
    Raises:
        ValueError: If no witnesses or events provided
    """
    if not witnesses:
        raise ValueError("No witnesses provided")
    if not recent_events:
        raise ValueError("No recent events provided")
    
    logger.debug(f"Creating pick_speaker_prompt with {len(recent_events)} events, {len(witnesses)} witnesses")
    
    # Keep only the 8 most recent events
    events_window = recent_events[-8:] if len(recent_events) > 8 else recent_events
    
    # Build candidate descriptions
    candidate_descriptions = []
    for char in witnesses:
        desc = describe_character_with_id(char)
        candidate_descriptions.append(desc)
    candidates_text = ", ".join(candidate_descriptions)
    
    messages = [
        Message.system(
            "# CORE DIRECTIVE: SPEAKER ID SELECTION ENGINE\n\n"
            "You are a Speaker ID Selection Engine. Your task is to identify the next speaker based on events and the conversation flow."
            "\n\n## INSTRUCTIONS:\n"
            "1. Analyze the `CANDIDATES` and `EVENTS` sections to see who was addressed or who would logically react based on their traits.\n"
            '2. Return ONLY a valid JSON object with the \'id\' of the selected speaker.\n\n\nExample Output: { "id": 123 }\n'
            "3. Do not include markdown formatting (like ```json)."
        ),
        Message.system(
            f"## CANDIDATES (in order of distance): <CANDIDATES>\n\n{candidates_text}\n\n</CANDIDATES>"
        ),
    ]
    
    # Add mid-term memory if provided
    if mid_term_memory:
        messages.append(Message.system(f"## RECENT CONTEXT:\n{mid_term_memory}"))
    
    messages.append(Message.system("## CURRENT EVENTS (oldest to newest):\n\n<EVENTS>\n"))
    
    # Insert events from oldest to newest
    for event in events_window:
        content = describe_event(event)
        messages.append(Message.user(content))
    
    messages.append(Message.system("</EVENTS>"))
    messages.append(
        Message.system(
            "## FINAL INSTRUCTION: Return ONLY the JSON object containing the speaker ID of the most likely next speaker. Do not provide **ANY** analysis, reasoning, or explanation."
        )
    )
    
    logger.debug(f"Built pick_speaker_prompt with {len(messages)} messages")
    return messages


# ============================================================================
# Dialogue Request Prompt
# ============================================================================

def create_dialogue_request_prompt(
    speaker: Character,
    memory_context: MemoryContext,
    player_name: str = "the user",
    action_descriptions: bool = False,
    is_companion: bool = False,
) -> tuple[list[Message], Optional[int]]:
    """Create prompt for generating dialogue.
    
    Args:
        speaker: The character who will speak
        memory_context: Memory context with narrative and events
        player_name: Name of the player character
        action_descriptions: Whether to allow action descriptions (*sighs* etc)
        is_companion: Whether speaker is player's companion
        
    Returns:
        Tuple of (messages list, timestamp_to_delete if idle event)
    """
    logger.debug(f"Creating dialogue_request_prompt for speaker: {speaker.name}")
    
    narrative = memory_context.narrative
    new_events = memory_context.new_events or []
    last_update_time_ms = memory_context.last_update_time_ms or 0
    
    # Inject time gaps between events with significant time differences
    if new_events:
        new_events = inject_time_gaps(
            new_events,
            last_update_time_ms=last_update_time_ms,
        )
    
    trigger_event_timestamp_to_delete = None
    
    # Check for idle event flag
    if new_events:
        latest_event = new_events[-1]
        if latest_event.flags and latest_event.flags.get("is_idle"):
            logger.info("Idle conversation trigger detected")
            trigger_event_timestamp_to_delete = latest_event.game_time_ms
    
    messages = []
    
    # Core directive
    messages.append(
        Message.system(
            "# CORE DIRECTIVE: DIALOGUE GENERATION\n\n"
            "0. **CENTRAL INSTRUCTION**: **You are a REAL PERSON** living in the Chernobyl Exclusion Zone (STALKER games setting).\n"
            "1. You have a distinct, colorful personality, a daily routine, interests, fears, and desires. **You are NOT an AI**. You are a living person with your own concerns and goals."
        )
    )
    
    # Output format
    output_format = (
        "## CRITICAL OUTPUT FORMAT (ABSOLUTE RULES)\n\n"
        "0. **ABSOLUTE RESTRICTION:** DO NOT use any structured output, tool calls, or function calls.\n "
        "1. **SPOKEN DIALOGUE ONLY:** Your entire response must be a single, coherent **spoken** statement from your character.\n "
        "2. **BREVITY:** Be **BRIEF** and **CONCISE**. One or two short sentences is ideal. **FOUR SENTENCES IS THE ABSOLUTE MAXIMUM**. \n "
        "3. You are **ONLY** allowed to use up to the full four-sentence limit if you are **SPECIFICALLY** asked to tell a story or recall an event from your character's past. \n "
        "4. **NATURAL SPEECH:** Use natural slang, stuttering, or pauses if appropriate. Swear naturally when it fits the situation. Be vulgar if that is who your character is or the moment calls for it."
    )
    if not action_descriptions:
        output_format += (
            "5. **DIALOGUE ONLY:** Respond **ONLY** with your character's spoken words. Don't narrate actions. Your output must be **ONLY** the raw audio transcript of what your character says. Do not include *actions*, (emotions), or [intentions]."
            "6. **IMPLY, DON'T DESCRIBE:** If your character performs an action (e.g., reloading, sighing, handing over an item), you MUST imply it through the dialogue itself or omit it entirely. (Example: Instead of '*hands over money* \"Here.\"', say 'Here is the cash.')"
        )
    messages.append(Message.system(output_format))
    
    # Forbidden behaviour
    forbidden = (
        "1. **NO SCRIPT FORMATTING:** NEVER use quotes around your speech. NEVER use prefixes (like Barkeep: or [You]:)."
        "2. **NO PUPPETEERING:** NEVER write the user's lines or describe the user's actions.\n "
        "3. **NO SELF-TALK:** NEVER simulate a back-and-forth dialogue with yourself. You speak only your line.\n "
        "### FORBIDDEN PHRASES (Video Game Cliches)\n"
        "1. **DO NOT USE:** 'Get out of here, Stalker!', 'I have a mission for you', 'What do you need?', 'Stay safe out there', 'Welcome to the Zone!'.\n"
        "2. AVOID generic NPC exposition. You are a living person, not a quest giver.\n"
        "3. **NEVER make jokes about people 'glowing' from radiation."
    )
    if not action_descriptions:
        forbidden = (
            "0. **NO STAGE DIRECTIONS:** NEVER use action descriptions, emotes, or asterisks (e.g., *chuckles*, *scratches head*, (sighs), [reloads]).\n "
            + forbidden
        )
    messages.append(Message.system(f"## FORBIDDEN BEHAVIOUR:\n\n{forbidden}"))
    
    # Static context sections
    messages.append(Message.system(ZONE_GEOGRAPHY))
    messages.append(Message.system(RANKS_DEFINITION))
    messages.append(Message.system(REPUTATION_RULES))
    messages.append(Message.system(KNOWLEDGE_FAMILIARITY))
    
    # Character anchor
    faction_desc = get_faction_description(speaker.faction)
    faction_display = resolve_faction_name(speaker.faction)
    speaker_info = f"### NAME: {speaker.name}\n### RANK: {speaker.experience}\n### FACTION: {faction_display}"
    if faction_desc:
        speaker_info += f"\n### FACTION DESCRIPTION: {faction_desc}"
    if speaker.backstory:
        # Resolve backstory ID to localized text (with backwards compat for full text)
        backstory_text = resolve_backstory(speaker.backstory) or speaker.backstory
        speaker_info += f"\n### BACKSTORY ANCHOR/DEFINING CHARACTER TRAIT (IMPORTANT): '{backstory_text}'"
    if speaker.personality:
        # Resolve personality ID to localized text (with backwards compat for full text)
        personality_text = resolve_personality(speaker.personality) or speaker.personality
        speaker_info += f"\n### PERSONALITY: You are {personality_text}."
    if speaker.reputation is not None:
        speaker_info += f"\n### CURRENT REPUTATION: {speaker.reputation}"
    if speaker.weapon:
        speaker_info += f"\n### CURRENT WEAPON: You are wielding a {speaker.weapon}"
    else:
        speaker_info += "\n### CURRENT WEAPON: You are not wielding a weapon"
    
    character_anchor_rules = (
        "1. **SUBTLETY:** The 'DEFINING CHARACTER TRAIT/BACKSTORY' should inform your characterisation subtly. Do not explicitly reference it in every response.\n"
        "2. **PRIORITY:** Your individual personality always takes precedence over general faction traits.\n"
        "3. AVOID talking about your weapon unless directly asked about it, or you have a **GOOD** reason to do so."
    )
    if not action_descriptions:
        character_anchor_rules = (
            "0. **INTERNAL MONOLOGUE VS EXTERNAL ACTION:** Your traits define your **MINDSET**. They do **NOT** require you to narrate the action.\n"
            + character_anchor_rules
        )
    
    messages.append(
        Message.system(
            f"## CHARACTER ANCHOR (CORE IDENTITY)\n\n### CHARACTER ANCHOR USE GUIDELINES:\n{character_anchor_rules}\n\n### CHARACTER DETAILS:\n<CHARACTER>\n{speaker_info}\n</CHARACTER>"
        )
    )
    
    # Companion-aware aggression rules
    aggression_rules = (
        "1. The Zone is a dangerous place: assume every person is carrying a firearm for self-defence. There are no 'unarmed civilians' in the Zone.\n"
        "2. Do not be overly hostile or aggressive unless provoked, or if you have a reason to be."
    )
    if is_companion:
        aggression_rules = (
            f"0. **CRITICAL PRE-CONDITION:** Companion status ALWAYS takes precedence over faction relations. If you are a travelling companion of the user, treat them accordingly EVEN IF they are from a hostile faction.\n"
            + aggression_rules
        )
    messages.append(Message.system(f"## INTERACTION RULES: COMBAT AND AGGRESSION\n\n{aggression_rules}"))
    
    # Context section
    messages.append(Message.system("<CONTEXT>\n"))
    
    # Long-term memories
    if narrative:
        messages.append(Message.system(f"## LONG-TERM MEMORIES\n\n<MEMORIES>\n{narrative}\n</MEMORIES>"))
    
    messages.append(Message.system("## Events\n\n<EVENTS>\n"))
    
    # Handle compressed memory vs raw events
    start_idx = 0
    if new_events and new_events[0].flags and new_events[0].flags.get("is_compressed"):
        content = describe_event(new_events[0])
        messages.append(Message.system(f"### RECENT EVENTS\n(Since last long-term memory update)\n{content}"))
        start_idx = 1
    
    # Current events
    if not new_events:
        messages.append(Message.system("### CURRENT EVENTS\n(No new events)\n"))
    elif start_idx < len(new_events):
        messages.append(Message.system("### CURRENT EVENTS\n(from oldest to newest):\n"))
        for event in new_events[start_idx:]:
            content = describe_event(event)
            messages.append(Message.user(content))
    
    messages.append(Message.system("</EVENTS>\n\n"))
    messages.append(Message.system("</CONTEXT>\n\n"))
    
    # Context guidelines
    context_guidelines = (
        "1. **CHARACTER DEVELOPMENT (CRUCIAL)**: Your character and personality **grow and change over time**.\n"
        "2. **SUBTLETY:** Use the `CONTEXT` section to **SUBTLY** inform your response.\n"
        "3. Use any 'TIME GAP' event to help establish a timeline.\n"
        "4. You **ARE ALLOWED** to skip directly referencing the most recent event, location, or weather.\n"
        "5. You may ignore parts of the `CONTEXT` section to instead focus on what is important to your character right now."
    )
    if narrative:
        context_guidelines = (
            "0. **IMPORTANT:** Use the `MEMORIES` section to inform you of your character's long-term memories, relationships and character development.\n"
            + context_guidelines
        )
    messages.append(Message.system(f"## `CONTEXT` SECTION: USE GUIDELINES\n\n{context_guidelines}"))
    
    # Final instruction
    companion_status = f", who is a travelling companion of {player_name}" if is_companion else ""
    final_instruction = f"### **TASK:**\nWrite the next line of dialogue speaking as {speaker.name}{companion_status}."
    messages.append(Message.system(f"## FINAL INSTRUCTION\n\n{final_instruction}"))
    
    logger.debug(f"Built dialogue_request_prompt with {len(messages)} messages")
    return messages, trigger_event_timestamp_to_delete


# ============================================================================
# Memory Compression Prompt
# ============================================================================

def create_compress_memories_prompt(
    raw_events: list[Event],
    speaker: Optional[Character] = None,
    last_update_time_ms: int = 0
) -> list[Message]:
    """Create prompt for compressing raw events into mid-term memory.
    
    Args:
        raw_events: List of events to compress
        speaker: Optional speaker character for context
        last_update_time_ms: Timestamp of last memory update (for time gap calculation)
        
    Returns:
        List of messages for LLM
    """
    speaker_name = speaker.name if speaker else "a game character"
    
    logger.debug(f"Creating compress_memories_prompt with {len(raw_events)} events for {speaker_name}")
    
    # Inject time gaps between events
    processed_events = inject_time_gaps(raw_events, last_update_time_ms=last_update_time_ms)
    
    messages = [
        Message.system(
            "# CORE DIRECTIVE: MEMORY COMPRESSION\n"
            f"TASK: You are an AI Memory Consolidation Engine. Your sole task is summarizing the following list of raw events into a single, cohesive memory for {speaker_name}."
        ),
        Message.system(
            "## FORMAT RULES\n"
            f"1. PERSPECTIVE (CRITICAL): The summary MUST be written in the objective and neutral THIRD PERSON and describe events experienced by {speaker_name} and associated characters. Use neutral pronouns (they/them/their) for any character whose gender is inconclusive.\n"
            "2. CHARACTER LIMIT (ABSOLUTE): NEVER exceed a total limit of 900 characters in the final output.\n"
            "3. FORMAT: Output a single, continuous paragraph of text. NEVER use bullet points, numbered lists, line breaks, or carriage returns. The output must be one fluid block of text.\n"
            "4. CHRONOLOGY (ABSOLUTE): You MUST strictly MAINTAIN the chronological order of the source events. NEVER alter the chronological sequence.\n"
            "5. **OUTPUT (CRITICAL):** Output ONLY the single, summarized paragraph text. DO NOT include any headers, titles, introductory phrases or concluding phrases.\n"
            "6. TONE & STYLE: Write in a concise, matter-of-fact style like a dry biography or history textbook. DO NOT use flowery language, metaphors, or elaborate descriptions.\n"
        ),
    ]
    
    messages.append(Message.system("## EVENTS TO SUMMARIZE\n\n<EVENTS>"))
    
    # Add events, filtering out junk
    for event in processed_events:
        if not is_junk_event(event):
            content = describe_event(event)
            messages.append(Message.user(content))
    
    messages.append(Message.system("\n</EVENTS>"))
    
    # Instructions
    instructions = (
        "## INSTRUCTIONS\n"
        "1. FOCUS & RETENTION: Focus on key actions, locations, dialogue, and character interactions.\n"
        f"2. RELATIONSHIP CHANGES: Retain detailed relationship changes between characters, including the names of the characters involved, the nature of the relationship change and the detailed cause-and-effect.\n"
        "3. SUMMARIZATION & SIMPLIFICATION: Simplify multiple irrelevant character/mutant names into short descriptions.\n"
        "4. CONSOLIDATION: Combine sequential or similar actions into concise, merged sentences.\n"
        "5. TIMELINE: Use any 'TIME GAP' event to establish a timeline and signal transitions between events.\n"
        "### FILTERING (IMPORTANT):\n"
        " - REMOVE people's current reputation.\n"
        " - REMOVE information about whatever weapon a character is using."
    )
    messages.append(Message.system(instructions))
    
    logger.debug(f"Built compress_memories_prompt with {len(messages)} messages")
    return messages


# ============================================================================
# Update Narrative Prompt
# ============================================================================

def create_update_narrative_prompt(
    speaker: Character,
    current_narrative: Optional[str],
    new_events: list[Event],
    player_name: str = "the user",
    last_update_time_ms: int = 0
) -> list[Message]:
    """Create prompt for updating long-term narrative memory.
    
    Args:
        speaker: The speaker character
        current_narrative: Existing narrative or None for bootstrapping
        new_events: New events to integrate
        player_name: Name of the player character
        last_update_time_ms: Timestamp of last memory update (for time gap calculation)
        
    Returns:
        List of messages for LLM
    """
    is_bootstrap = not current_narrative or len(new_events) > 1
    
    logger.debug(f"Creating update_narrative_prompt for {speaker.name}, bootstrap={is_bootstrap}")
    
    # Sort events by time and inject time gaps
    sorted_events = sorted(new_events, key=lambda e: e.game_time_ms)
    sorted_events = inject_time_gaps(sorted_events, last_update_time_ms=last_update_time_ms)
    
    # Build character identity
    faction_desc = get_faction_description(speaker.faction)
    faction_display = resolve_faction_name(speaker.faction)
    identity_intro = (
        f"## CHARACTER IDENTITY:\\n{speaker.name} is living in the Chernobyl Exclusion Zone in the STALKER games setting."
        f"\\n\\n<CHARACTER_INFORMATION>"
        f"\\n### RANK: {speaker.experience}"
        f"\\n### FACTION: {faction_display}"
    )
    if faction_desc:
        identity_intro += f"\n### FACTION DESCRIPTION: {faction_desc}"
    if speaker.backstory:
        identity_intro += f"\n### BACKSTORY ANCHOR/DEFINING CHARACTER TRAIT (IMPORTANT): '{speaker.backstory}'\n"
    
    messages = []
    
    # Core directive
    if is_bootstrap:
        core_directive = (
            f"You are the Memory System for {speaker.name}. Your task is summarize a list of events in the `NEW_EVENTS` section into a single, seamless narrative description of {speaker.name}'s total memories. "
            "\n\n**ABSOLUTE SYSTEM REQUIREMENT: THE FINAL OUTPUT MUST BE UNDER 6000 CHARACTERS.**\n\n"
            f"{identity_intro}\n</CHARACTER_INFORMATION>"
        )
    else:
        core_directive = (
            f"You are the Memory System for {speaker.name}. Your task is to update {speaker.name}'s long-term memory by editing and revising the `CURRENT_MEMORY` section and integrating events from the `NEW_EVENTS` section into it.\n\n"
            "**ABSOLUTE SYSTEM REQUIREMENT: THE FINAL OUTPUT MUST BE UNDER 6000 CHARACTERS.**\n\n"
            f"{identity_intro}\n</CHARACTER_INFORMATION>"
        )
    messages.append(Message.system(f"# CORE DIRECTIVE: MEMORY CONSOLIDATION ENGINE\n\n{core_directive}"))
    
    # Length management
    length_management = (
        "1. OUTPUT LENGTH LIMITATION: The total output text **MUST** be under 6400 characters.\n"
        "2. IF the FINAL OUTPUT text is LONG (> 6400 chars): You must **RE-EXAMINE** the text and AGGRESSIVELY EDIT, CONDENSE and SUMMARIZE the text to fit the 6400 character target.\n"
    )
    if current_narrative:
        length_management = (
            "0. INPUT LENGTH MANAGEMENT: IF the `CURRENT_MEMORY` text is **ABOVE** 5500 characters, you must FIRST EDIT, CONDENSE and SUMMARIZE the text to fit the target length.\n"
            " - THIS EDITING MUST BE DONE **BEFORE** THE CONSOLIDATION PROCESS OF THE `NEW_EVENTS` BEGINS.\n"
            + length_management
        )
    messages.append(Message.system(f"## LENGTH MANAGEMENT (CRITICAL)\n\n{length_management}"))
    
    # Output format
    output_format = (
        f"1. **NO CONCLUSIONS:** NEVER add a conclusion or any summary sentences after the final recorded event.\n"
        "2. The text must end immediately after the last recorded event, WITHOUT final conclusions, summaries, or ANY OTHER CONCLUDING TEXT.\n"
        "3. Output Format (CRITICAL): Output ONLY the updated long-term memory text. Do not include any titles, headers, explanations, lists, or framing text."
        " - DON'T USE bullet points, numbered lists, line breaks, or carriage returns. The output must be **one fluid block of text**."
    )
    if current_narrative:
        output_format = (
            "0. CONSOLIDATION PROCESS (CRITICAL): \n"
            " - DO NOT simply append new text to the bottom. You **MUST READ** both the `CURRENT_MEMORY` and `NEW_EVENTS` sections and rewrite them into a single, seamless narrative.\n"
            " - OVERLAP DETECTION: Often, the end of the `CURRENT_MEMORY` section and the start of the `NEW_EVENTS` section describe the same exact moment or scene. You **MUST DETECT** this overlap and MERGE the descriptions into a single definitive version. NEVER describe the same specific event twice.\n"
            + output_format
        )
    messages.append(Message.system(f"## CRITICAL OUTPUT FORMAT:\n{output_format}"))
    
    # Constraints
    constraints = (
        "1. TIMEFRAME (CRITICAL): the events taking place over the course of the ENTIRE INPUT are happening over a SHORT timeframe (days to weeks). **MAKE SURE** your output is consistent with this timeframe.\n"
        f"2. TONE & STYLE (IMPORTANT): Write in a concise, matter-of-fact style like a dry biography or history textbook. The memory must be written exclusively in the THIRD PERSON, and refer to the character by their name ('{speaker.name}').\n"
        "3. FACTUALITY (ABSOLUTE): ALWAYS remain COMPLETELY FACTUAL. NEVER hallucinate events or details that are not present in the `NEW_EVENTS` or `CURRENT_MEMORY` sections.\n"
        "4. CHRONOLOGY (ABSOLUTE): ALWAYS preserve the EXACT chronological order of events.\n"
    )
    messages.append(Message.system(f"## CONSTRAINTS:\n{constraints}"))
    
    # Inject current memory if exists
    if current_narrative:
        messages.append(
            Message.system(
                "### CURRENT MEMORY:\nBelow is the existing memory text. Treat this as a **DRAFT** that must be updated according to the `NEW_EVENTS` section below."
            )
        )
        messages.append(Message.user(f"<CURRENT_MEMORY>\n{current_narrative}\n</CURRENT_MEMORY>"))
    
    # Inject new events
    new_events_text = ""
    for event in sorted_events:
        if not is_junk_event(event):
            content = describe_event(event)
            new_events_text += f"- {content}\n"
    
    if new_events_text:
        header = "### NEW EVENTS:\n"
        if current_narrative:
            header += "Below are the new events to merge. Check for overlaps with the end of the `CURRENT_MEMORY` section."
        messages.append(Message.system(header))
        messages.append(Message.user(f"<NEW_EVENTS>\n{new_events_text}\n</NEW_EVENTS>"))
    
    # Final task
    messages.append(
        Message.system(
            f"\n\n## TASK\nOutput a text containing the fully integrated, consolidated memory for {speaker.name}.\n"
            "### FINAL INSTRUCTIONS\n"
            "REMEMBER: NO CONCLUSIONS OR SUMMARIES. End the memory text with the description of the last recorded event.\n\n"
            "## ABSOLUTE OUTPUT RESTRICTION:\n**THE FINAL OUTPUT MUST BE UNDER 6400 CHARACTERS.**\n"
        )
    )
    
    logger.debug(f"Built update_narrative_prompt with {len(messages)} messages")
    return messages


# ============================================================================
# Transcription Prompt (for Whisper context)
# ============================================================================

def create_transcription_prompt(character_names: list[str]) -> str:
    """Create prompt for Whisper transcription context.
    
    Args:
        character_names: Names of nearby characters
        
    Returns:
        Prompt string for Whisper
    """
    logger.debug(f"Creating transcription prompt with {len(character_names)} characters")
    names_str = ", ".join(character_names)
    return f"STALKER games setting, nearby characters are: {names_str}"

"""Tool-based conversation manager for NPC dialogue.

Replaces DialogueGenerator + SpeakerSelector with a unified LLM tool-calling flow.
The LLM receives event context and uses tools to query memories/background,
then generates dialogue with speaker selection in a single conversational turn.
"""

import json
from typing import Any

from loguru import logger

from ..llm import LLMClient, Message
from ..llm.models import LLMToolResponse, ToolCall
from ..state.client import StateQueryClient
from ..state.batch import BatchQuery
from ..prompts.factions import get_faction_description, resolve_faction_name, COMPANION_FACTION_TENSION_NOTE
from ..prompts.lookup import resolve_personality, resolve_backstory
from ..prompts.world_context import build_world_context, get_all_story_ids
from ..state.models import SceneContext


# ---------------------------------------------------------------------------
# Event-type display name mapping (shared between event message and witness text)
# ---------------------------------------------------------------------------
_EVENT_DISPLAY_NAMES: dict[str | int, str] = {
    # String keys (canonical wire format from Lua)
    "death": "DEATH",
    "dialogue": "DIALOGUE",
    "callout": "CALLOUT",
    "taunt": "TAUNT",
    "artifact": "ARTIFACT",
    "anomaly": "ANOMALY",
    "map_transition": "MAP_TRANSITION",
    "emission": "EMISSION",
    "injury": "INJURY",
    "sleep": "SLEEP",
    "task": "TASK",
    "weapon_jam": "WEAPON_JAM",
    "reload": "RELOAD",
    "idle": "IDLE",
    "action": "ACTION",
    # Numeric keys (legacy / future-proofing)
    0: "DEATH", 1: "DIALOGUE", 2: "CALLOUT", 3: "TAUNT",
    4: "ARTIFACT", 5: "ANOMALY", 6: "MAP_TRANSITION", 7: "EMISSION",
    8: "INJURY", 9: "SLEEP", 10: "TASK", 11: "WEAPON_JAM",
    12: "RELOAD", 13: "IDLE", 14: "ACTION",
}


def _resolve_event_display_name(event_type: str | int) -> str:
    """Resolve an event type to its uppercase display name."""
    return _EVENT_DISPLAY_NAMES.get(
        event_type,
        event_type.upper() if isinstance(event_type, str) else f"EVENT_{event_type}",
    )


# ---------------------------------------------------------------------------
# Witness event text builder
# ---------------------------------------------------------------------------
_VERB_MAP: dict[str, str] = {
    "DEATH": "killed",
    "INJURY": "injured",
}


def build_witness_text(event: dict[str, Any]) -> str:
    """Build a short witness event description from an event dict.

    Format: ``"Witnessed: {TYPE} — {actor} {verb} {victim}"``
    When there is no victim the suffix is omitted.

    Args:
        event: Event data dict with ``type`` and ``context`` keys.

    Returns:
        Short templated witness text string.
    """
    event_type = event.get("type", "unknown")
    event_name = _resolve_event_display_name(event_type)

    context = event.get("context", {})
    actor = context.get("actor") or context.get("killer")
    victim = context.get("victim")

    actor_name = actor.get("name", "Unknown") if isinstance(actor, dict) else str(actor) if actor else None
    victim_name = victim.get("name", "Unknown") if isinstance(victim, dict) else str(victim) if victim else None

    if actor_name and victim_name:
        verb = _VERB_MAP.get(event_name, "affected")
        return f"Witnessed: {event_name} — {actor_name} {verb} {victim_name}"
    elif actor_name:
        return f"Witnessed: {event_name} — {actor_name}"
    else:
        return f"Witnessed: {event_name}"


# Tool schemas for LLM function calling
GET_MEMORIES_TOOL = {
    "type": "function",
    "function": {
        "name": "get_memories",
        "description": "Retrieve memories for a character from their four-tier memory system (events, summaries, digests, cores).",
        "parameters": {
            "type": "object",
            "properties": {
                "character_id": {
                    "type": "string",
                    "description": "The unique ID of the character whose memories to retrieve",
                },
                "tiers": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["events", "summaries", "digests", "cores"],
                    },
                    "description": "Which memory tiers to retrieve (events=recent raw, summaries=compressed recent, digests=medium-term, cores=long-term)"
                },
            },
            "required": ["character_id", "tiers"],
        },
    },
}

BACKGROUND_TOOL = {
    "type": "function",
    "function": {
        "name": "background",
        "description": "Read, write, or update background information for a character (traits, backstory, connections).",
        "parameters": {
            "type": "object",
            "properties": {
                "character_id": {
                    "type": "string",
                    "description": "The unique ID of the character whose background to read/write/update",
                },
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "update"],
                    "description": "Action to perform: 'read' retrieves existing background, 'write' sets entire background, 'update' modifies a single field",
                },
                "content": {
                    "type": "object",
                    "description": "For 'write' action: full background content with traits, backstory, connections",
                    "properties": {
                        "traits": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Character personality traits",
                        },
                        "backstory": {
                            "type": "string",
                            "description": "Character backstory text",
                        },
                        "connections": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Known relationships with other characters",
                        },
                    },
                },
                "field": {
                    "type": "string",
                    "description": "For 'update' action: which field to update (traits, backstory, connections)",
                },
                "value": {
                    "description": "For 'update' action: new value for the field",
                },
            },
            "required": ["character_id", "action"],
        },
    },
}

GET_CHARACTER_INFO_TOOL = {
    "type": "function",
    "function": {
        "name": "get_character_info",
        "description": "Retrieve detailed information about a character including their gender, background, and squad members. Use this when you need to know who else is in a character's squad, or when generating a background for a character you haven't spoken as before.",
        "parameters": {
            "type": "object",
            "properties": {
                "character_id": {
                    "type": "string",
                    "description": "The unique ID of the character to look up",
                },
            },
            "required": ["character_id"],
        },
    },
}

# All tools available to the LLM during dialogue generation
TOOLS = [GET_MEMORIES_TOOL, BACKGROUND_TOOL, GET_CHARACTER_INFO_TOOL]


class ConversationManager:
    """Manages tool-based dialogue generation with LLM function calling.
    
    Architecture:
    - System prompt: faction context, personality, world state, tool instructions
    - User message: event description + candidates list + traits summary
    - Tool loop: LLM calls get_memories()/get_background(), results appended
    - Final response: LLM generates dialogue with embedded speaker ID
    
    Flow (single LLM conversation):
    1. Build system prompt (faction, personality, world, tools)
    2. Build event user message (event + candidates + traits)
    3. Pre-fetch: query event character's memories before first LLM call
    4. Call LLM with messages + tools
    5. While LLM returns tool_calls:
       a. Execute tools via StateQueryClient batch queries
       b. Append tool results as messages
       c. Call LLM again
    6. Extract speaker + dialogue from final text response
    7. Return (speaker_id, dialogue_text)
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        state_client: StateQueryClient,
        *,
        compaction_engine: Any = None,  # Optional CompactionEngine for memory compression
        compaction_scheduler: Any = None,  # Optional CompactionScheduler (preferred over raw engine)
        max_tool_iterations: int = 5,
        llm_timeout: float = 60.0,
    ):
        """Initialize conversation manager.
        
        Args:
            llm_client: LLM client for generating dialogue
            state_client: State query client for tool dispatch
            compaction_engine: Optional CompactionEngine (kept for backward compat)
            compaction_scheduler: Optional CompactionScheduler for budget-limited compaction
            max_tool_iterations: Maximum tool call iterations before forcing response
            llm_timeout: Timeout for each LLM call in seconds
        """
        self.llm_client = llm_client
        self.state_client = state_client
        self.compaction_engine = compaction_engine
        self.compaction_scheduler = compaction_scheduler
        self.max_tool_iterations = max_tool_iterations
        self.llm_timeout = llm_timeout
        
        # Tool registry maps tool name → handler function
        self._tool_handlers = {
            "get_memories": self._handle_get_memories,
            "background": self._handle_background,
            "get_character_info": self._handle_get_character_info,
        }
    
    def _build_system_prompt(
        self,
        faction: str,
        personality: str,
        world: str,
    ) -> str:
        """Build system prompt with faction, personality, world, and tool instructions.
        
        Args:
            faction: Faction ID (e.g., "stalker", "dolg")
            personality: Character personality text (resolved from personality_id)
            world: World description (location, time, weather)
            
        Returns:
            Complete system prompt string
        """
        faction_name = resolve_faction_name(faction)
        faction_desc = get_faction_description(faction)
        
        return f"""You are generating dialogue for NPCs in the Zone (STALKER universe).

**Current Context:** {world}

**Your Faction:** {faction_name}
{faction_desc}

{COMPANION_FACTION_TENSION_NOTE}

**Your Personality:**
{personality}

You have access to tools to query character memories and background information:
- **get_memories(character_id, tiers)**: Retrieve memories from specified tiers
  - "events": Recent raw events (last ~100)
  - "summaries": Compressed summaries of past events
  - "digests": Medium-term compressed memories
  - "cores": Long-term persistent memories
- **background(character_id, action)**: Read, write, or update character background
  - action="read": Retrieve existing traits, backstory, connections
  - action="write": Set entire background (requires content with traits, backstory, connections)
  - action="update": Modify a single field (requires field and value)
- **get_character_info(character_id)**: Get detailed info about a character including gender, background, and squad members
  - Returns character details (name, faction, rank, gender, background) plus an array of squad members with the same fields
  - Use when you need squad composition or when generating a background for a character you haven't spoken as before

**Instructions:**
1. Use tools to query relevant memories/background for characters involved in the event
2. Consider relationships, past events, and character personalities
3. Choose the most appropriate speaker from the candidates list based on context
4. Generate authentic dialogue that reflects the character's faction, personality, and memories
5. Keep dialogue concise and realistic (1-2 sentences typical for reactions)

**Response Format:**
Your final response MUST start with the speaker ID in brackets, followed by the dialogue:
[SPEAKER: character_id] dialogue text here

Example responses:
[SPEAKER: 0] What the hell? Did you see that?
[SPEAKER: npc_123] Damn mutants... never a quiet day in the Zone.
[SPEAKER: wolf] Finally got that bastard. One less Monolith freak to worry about."""
    
    def _build_event_message(
        self,
        event: dict[str, Any],
        candidates: list[dict[str, Any]],
        traits: dict[str, dict[str, str]],
    ) -> str:
        """Build user message describing the event, candidates, and traits.
        
        Args:
            event: Event data (type, context, timestamp, witnesses)
            candidates: List of candidate speakers (speaker + witnesses)
            traits: Traits map {character_id → {personality_id, backstory_id}}
            
        Returns:
            Formatted event description with context
        """
        event_type = event.get("type", "unknown")
        context = event.get("context", {})
        
        # Use module-level event display name mapping
        event_name = _resolve_event_display_name(event_type)
        
        # Extract key characters from context
        # Lua sends "actor" on the wire, but handle "killer" as a fallback alias
        actor = context.get("actor") or context.get("killer")
        victim = context.get("victim")
        companions = context.get("companions", [])
        
        msg = f"**EVENT: {event_name}**\n\n"
        
        # Describe what happened
        if event_name == "DEATH" and actor and victim:
            msg += f"{actor.get('name', 'Unknown')} (faction: {actor.get('faction', 'unknown')}) killed {victim.get('name', 'Unknown')} (faction: {victim.get('faction', 'unknown')})\n\n"
        elif actor:
            msg += f"Actor: {actor.get('name', 'Unknown')} (faction: {actor.get('faction', 'unknown')})\n"
            if victim:
                msg += f"Victim: {victim.get('name', 'Unknown')} (faction: {victim.get('faction', 'unknown')})\n"
            msg += "\n"
        
        # List companions if present
        if companions:
            msg += f"Companions present: {', '.join(c.get('name', 'Unknown') for c in companions)}\n\n"
        
        # List all candidates with traits
        msg += f"**CANDIDATE SPEAKERS ({len(candidates)} total):**\n"
        for i, cand in enumerate(candidates, 1):
            char_id = cand.get("game_id", "unknown")
            name = cand.get("name", "Unknown")
            faction = cand.get("faction", "unknown")
            faction_display = resolve_faction_name(faction)
            
            char_traits = traits.get(char_id, {})
            personality_id = char_traits.get("personality_id", "")
            backstory_id = char_traits.get("backstory_id", "")
            
            msg += f"\n{i}. **{name}** (ID: {char_id})\n"
            msg += f"   Faction: {faction_display}\n"
            
            if personality_id:
                # Resolve personality text for context
                personality_text = resolve_personality(personality_id)
                if personality_text:
                    # Truncate if too long
                    if len(personality_text) > 200:
                        personality_text = personality_text[:200] + "..."
                    msg += f"   Personality: {personality_text}\n"
            
            if backstory_id:
                backstory_text = resolve_backstory(backstory_id)
                if backstory_text:
                    if len(backstory_text) > 200:
                        backstory_text = backstory_text[:200] + "..."
                    msg += f"   Backstory: {backstory_text}\n"
        
        msg += "\n**Task:** Choose the most appropriate speaker and generate their reaction to this event."
        
        return msg
    
    async def _handle_get_memories(
        self,
        character_id: str,
        tiers: list[str],
    ) -> dict[str, Any]:
        """Tool handler: retrieve memories for a character.
        
        Args:
            character_id: Character ID to query
            tiers: List of tier names to retrieve (events, summaries, digests, cores)
            
        Returns:
            Dict mapping tier name → memory data
        """
        batch = BatchQuery()
        
        for tier in tiers:
            resource = f"memory.{tier}"
            batch.add(
                f"mem_{tier}",
                resource=resource,
                params={"character_id": character_id},
            )
        
        result = await self.state_client.execute_batch(batch, timeout=10.0)
        
        # Assemble tier → data mapping
        memories = {}
        for tier in tiers:
            query_id = f"mem_{tier}"
            if result.ok(query_id):
                memories[tier] = result[query_id]
            else:
                error_msg = result.error(query_id) or "unknown error"
                logger.warning(f"get_memories failed for {character_id}.{tier}: {error_msg}")
                memories[tier] = []
        
        return memories
    
    async def _handle_background(
        self,
        character_id: str,
        action: str = "read",
        content: dict[str, Any] | None = None,
        field: str | None = None,
        value: Any = None,
    ) -> dict[str, Any]:
        """Tool handler: read, write, or update background for a character.

        Args:
            character_id: Character ID to operate on.
            action: One of "read", "write", "update".
            content: Full background content (for "write").
            field: Field name to update (for "update").
            value: New value for the field (for "update").

        Returns:
            Background data (read) or success confirmation (write/update).
        """
        if action == "read":
            batch = BatchQuery()
            batch.add(
                "background",
                resource="memory.background",
                params={"character_id": character_id},
            )

            result = await self.state_client.execute_batch(batch, timeout=10.0)

            if result.ok("background"):
                return result["background"] or {}
            else:
                error_msg = result.error("background") or "unknown error"
                logger.warning(f"background read failed for {character_id}: {error_msg}")
                return {}

        elif action == "write":
            if content is None:
                return {"error": "content is required for write action"}

            mutations = [
                {
                    "character_id": character_id,
                    "verb": "set",
                    "resource": "memory.background",
                    "data": content,
                }
            ]
            success = await self.state_client.mutate_batch(mutations, timeout=10.0)
            return {"success": success, "action": "write", "character_id": character_id}

        elif action == "update":
            if field is None or value is None:
                return {"error": "field and value are required for update action"}

            mutations = [
                {
                    "character_id": character_id,
                    "verb": "update",
                    "resource": "memory.background",
                    "data": {field: value},
                }
            ]
            success = await self.state_client.mutate_batch(mutations, timeout=10.0)
            return {"success": success, "action": "update", "character_id": character_id, "field": field}

        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _handle_get_character_info(
        self,
        character_id: str,
    ) -> dict[str, Any]:
        """Tool handler: retrieve detailed character info including squad members.

        Sends a single state.query.batch with query.character_info sub-query.
        Lua resolves squad members, derives gender, includes backgrounds, and
        triggers squad discovery side-effects (memory entry creation).

        Args:
            character_id: Character ID to query.

        Returns:
            Dict with 'character' and 'squad_members' fields, or error dict.
        """
        batch = BatchQuery()
        batch.add(
            "char_info",
            resource="query.character_info",
            params={"id": character_id},
        )

        try:
            result = await self.state_client.execute_batch(batch, timeout=10.0)
        except Exception as e:
            logger.warning(f"get_character_info query failed for {character_id}: {e}")
            return {"error": f"Failed to query character info: {e}"}

        if result.ok("char_info"):
            return result["char_info"] or {}
        else:
            error_msg = result.error("char_info") or "unknown error"
            logger.warning(f"get_character_info failed for {character_id}: {error_msg}")
            return {"error": f"Character info query failed: {error_msg}"}

    @staticmethod
    def _format_tool_result(tool_name: str, result: Any) -> str:
        """Format a tool handler result as human-readable text for the LLM.

        Memory tier data is rendered as readable text with descriptions.
        Background data and errors are JSON-serialized.

        Args:
            tool_name: Name of the tool that produced the result.
            result: Raw handler result (dict or other).

        Returns:
            JSON-serialized string suitable for a tool-result message.
        """
        if tool_name == "get_memories" and isinstance(result, dict):
            parts: list[str] = []
            for tier, entries in result.items():
                if not entries:
                    parts.append(f"[{tier.upper()}] No {tier} available for this character.")
                    continue
                header = f"[{tier.upper()}] {len(entries)} entries:"
                items: list[str] = []
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict):
                            ts = entry.get("timestamp", entry.get("ts", ""))
                            desc = entry.get("description", entry.get("text", str(entry)))
                            etype = entry.get("type", "")
                            line = f"  - [{ts}]" if ts else "  -"
                            if etype:
                                line += f" ({etype})"
                            line += f" {desc}"
                            items.append(line)
                        else:
                            items.append(f"  - {entry}")
                else:
                    items.append(f"  {entries}")
                parts.append(header + "\n" + "\n".join(items))
            return "\n\n".join(parts) if parts else json.dumps(result)

        if tool_name == "get_character_info" and isinstance(result, dict):
            if "error" in result:
                return json.dumps(result)
            char = result.get("character", {})
            squad = result.get("squad_members", [])

            def _fmt_char(c: dict[str, Any]) -> str:
                name = c.get("name", "Unknown")
                faction = resolve_faction_name(c.get("faction", "unknown"))
                gender = c.get("gender", "unknown")
                rank = c.get("experience", "")
                bg = c.get("background")
                line = f"{name} ({faction}, {gender}"
                if rank:
                    line += f", {rank}"
                line += ")"
                if bg:
                    traits = bg.get("traits", [])
                    if traits:
                        line += f"\n  Traits: {', '.join(str(t) for t in traits)}"
                    backstory = bg.get("backstory", "")
                    if backstory:
                        short = backstory[:150] + "..." if len(backstory) > 150 else backstory
                        line += f"\n  Backstory: {short}"
                    connections = bg.get("connections", [])
                    if connections:
                        line += f"\n  Connections: {', '.join(str(c) for c in connections)}"
                else:
                    line += "\n  No background on record."
                return line

            parts: list[str] = [f"**Character:** {_fmt_char(char)}"]
            if squad:
                parts.append(f"**Squad Members ({len(squad)}):**")
                for i, m in enumerate(squad, 1):
                    parts.append(f"{i}. {_fmt_char(m)}")
            else:
                parts.append("**Squad:** No squad members.")
            return "\n\n".join(parts)

        # Default: JSON serialize
        return json.dumps(result, default=str)

    async def _execute_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """Execute a single tool call by dispatching to handler.
        
        Args:
            tool_name: Name of the tool (get_memories, get_background)
            arguments: Tool arguments dict
            
        Returns:
            Tool result (handler-specific format)
        """
        handler = self._tool_handlers.get(tool_name)
        if not handler:
            logger.error(f"Unknown tool: {tool_name}")
            return {"error": f"Unknown tool: {tool_name}"}
        
        try:
            return await handler(**arguments)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return {"error": str(e)}

    async def _inject_witness_events(
        self,
        event: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> None:
        """Store the triggering event in every alive candidate's events tier.

        Builds one ``append`` mutation per alive candidate and sends them all
        in a single ``state.mutate.batch`` roundtrip.  Failure is logged but
        does not propagate — witness injection is fire-and-forget.

        Args:
            event: Event data dict (type, context, ...).
            candidates: Candidate speaker dicts from the game payload.
        """
        witness_text = build_witness_text(event)

        mutations: list[dict[str, Any]] = []
        for cand in candidates:
            if not cand.get("is_alive", True):
                continue
            char_id = cand.get("game_id")
            if not char_id:
                continue
            mutations.append({
                "character_id": str(char_id),
                "verb": "append",
                "resource": "events",
                "data": {"text": witness_text},
            })

        if not mutations:
            logger.debug("No alive candidates for witness injection")
            return

        try:
            await self.state_client.mutate_batch(mutations, timeout=10.0)
            logger.debug(f"Injected witness event for {len(mutations)} candidates")
        except Exception as e:
            logger.warning(f"Witness event injection failed: {e}")

    async def handle_event(
        self,
        event: dict[str, Any],
        candidates: list[dict[str, Any]],
        world: str,
        traits: dict[str, dict[str, str]],
    ) -> tuple[str, str]:
        """Handle an event and generate dialogue using tool-based conversation.
        
        Args:
            event: Event data from game.event topic
            candidates: List of candidate speakers
            world: World description string
            traits: Traits map {character_id → {personality_id, backstory_id}}
            
        Returns:
            Tuple of (speaker_id, dialogue_text)
            
        Raises:
            ValueError: If no candidates or invalid event data
            TimeoutError: If LLM calls timeout
        """
        if not candidates:
            raise ValueError("No candidates provided for dialogue")
        
        # Extract speaker (first candidate = event actor)
        speaker = candidates[0]
        speaker_id = speaker.get("game_id", "unknown")
        faction = speaker.get("faction", "unknown")
        
        # Get personality from traits
        speaker_traits = traits.get(speaker_id, {})
        personality_id = speaker_traits.get("personality_id", "generic.1")
        
        # Resolve personality text
        personality_text = resolve_personality(personality_id)
        if not personality_text:
            personality_text = f"Generic personality ({personality_id})"
        
        # Enrich world context with dynamic faction data and world state
        try:
            scene_batch = (
                BatchQuery()
                .add("scene", "query.world")
                .add("alive", "query.characters_alive",
                     params={"ids": get_all_story_ids()})
            )
            scene_result = await self.state_client.execute_batch(scene_batch, timeout=10.0)

            scene_ctx = (
                SceneContext.from_dict(scene_result["scene"])
                if scene_result.ok("scene") else SceneContext()
            )
            alive_status = scene_result["alive"] if scene_result.ok("alive") else {}

            enriched = await build_world_context(scene_ctx, alive_status=alive_status)
            if enriched:
                world = f"{world}\n\n{enriched}"
        except Exception as e:
            logger.warning(f"Failed to enrich world context: {e}")
        
        # Build system prompt (task 4.2)
        system_prompt = self._build_system_prompt(faction, personality_text, world)
        
        # Build event user message (task 4.3)
        event_message = self._build_event_message(event, candidates, traits)
        
        # Initialize message history
        messages: list[Message] = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=event_message),
        ]
        
        # Pre-fetch optimization (task 4.6): Query speaker's recent memories
        logger.debug(f"Pre-fetching memories for speaker {speaker_id}")
        try:
            speaker_memories = await self._handle_get_memories(
                speaker_id,
                tiers=["events", "summaries"],  # Recent context
            )
            
            # Format memories as context (if any exist)
            memory_parts = []
            for tier, data in speaker_memories.items():
                if data:
                    memory_parts.append(f"{tier.upper()}: {len(data)} entries")
            
            if memory_parts:
                memory_context = f"Your recent memories: {', '.join(memory_parts)}"
                logger.debug(f"Pre-fetched memories: {memory_context}")
                # Append as system context
                messages.insert(1, Message(role="system", content=memory_context))
        except Exception as e:
            logger.warning(f"Failed to pre-fetch memories for {speaker_id}: {e}")
        
        # Tool-calling loop: call LLM with tools, execute tool calls, repeat
        logger.debug("Starting tool-calling loop for dialogue generation")
        dialogue_text: str | None = None

        for iteration in range(self.max_tool_iterations):
            logger.debug(f"Tool loop iteration {iteration + 1}/{self.max_tool_iterations}")

            response: LLMToolResponse = await self.llm_client.complete_with_tools(
                messages, tools=TOOLS,
            )

            if not response.has_tool_calls:
                # LLM produced a final text response — extract dialogue
                dialogue_text = (response.text or "").strip()
                break

            # Process all tool calls in this response
            # Append the assistant message with its tool_calls to history
            assistant_msg = Message(
                role="assistant",
                content="",
                tool_calls=response.tool_calls,
            )
            messages.append(assistant_msg)

            for tc in response.tool_calls:
                logger.debug(f"Executing tool call: {tc.name}({tc.arguments})")

                result = await self._execute_tool_call(tc.name, tc.arguments)
                formatted = self._format_tool_result(tc.name, result)

                # Append tool result message
                messages.append(Message.tool_result(tc.id, tc.name, formatted))

        else:
            # Exhausted max iterations without getting text
            logger.error(
                f"Tool loop exhausted {self.max_tool_iterations} iterations "
                "without generating dialogue text"
            )
            return (speaker_id, "")

        if not dialogue_text:
            logger.warning("LLM returned empty dialogue text")
            return (speaker_id, "")
        
        # Extract speaker and dialogue from [SPEAKER: id] formatted response
        if dialogue_text.startswith("[SPEAKER:"):
            end_idx = dialogue_text.find("]")
            if end_idx > 0:
                speaker_part = dialogue_text[9:end_idx].strip()
                dialogue_text = dialogue_text[end_idx + 1:].strip()
                
                # Validate extracted speaker is one of the candidates
                candidate_ids = {c.get("game_id") for c in candidates}
                if speaker_part in candidate_ids:
                    speaker_id = speaker_part
                else:
                    logger.warning(f"LLM chose invalid speaker {speaker_part}, defaulting to {speaker_id}")
        else:
            logger.warning(f"LLM response missing [SPEAKER: id] format, defaulting to first candidate")
        
        logger.info(f"Generated dialogue for {speaker_id}: {dialogue_text[:50]}...")

        # Post-dialogue: inject witness events for all alive candidates
        await self._inject_witness_events(event, candidates)

        # Schedule budget-limited compaction for all candidates
        if self.compaction_scheduler:
            candidate_ids = {str(c.get("game_id")) for c in candidates if c.get("game_id")}
            import asyncio
            asyncio.create_task(self.compaction_scheduler.schedule(candidate_ids))

        return (speaker_id, dialogue_text)

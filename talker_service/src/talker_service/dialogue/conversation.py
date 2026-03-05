"""Tool-based conversation manager for NPC dialogue.

Replaces DialogueGenerator + SpeakerSelector with a unified LLM tool-calling flow.
The LLM receives event context and uses tools to query memories/background,
then generates dialogue with speaker selection in a single conversational turn.
"""

import json
from typing import Any, Callable, TYPE_CHECKING

from loguru import logger

from ..llm import LLMClient, Message
from ..llm.models import LLMOptions, LLMToolResponse, ReasoningOptions, ToolCall
from ..state.client import StateQueryClient
from ..state.batch import BatchQuery
from ..prompts.factions import get_faction_description, resolve_faction_name, COMPANION_FACTION_TENSION_NOTE
from ..prompts.lookup import resolve_personality, resolve_backstory
from ..prompts.world_context import build_world_context, get_all_story_ids
from ..state.models import SceneContext

if TYPE_CHECKING:
    from ..transport.session_registry import SessionRegistry


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


# ---------------------------------------------------------------------------
# Helper for batch tool parameter normalisation
# ---------------------------------------------------------------------------

def _normalise_character_ids(
    character_ids: str | list[str] | None,
    character_id: str | None = None,
) -> list[str]:
    """Collapse the new ``character_ids`` and legacy ``character_id`` args into a list.

    Accepts singular strings, lists, or ``None``.  The legacy ``character_id``
    parameter is only used when ``character_ids`` is ``None`` (backward compat).
    """
    if character_ids is not None:
        if isinstance(character_ids, str):
            return [character_ids]
        return list(character_ids)
    if character_id is not None:
        return [character_id]
    return []


# Tool schemas for LLM function calling
GET_MEMORIES_TOOL = {
    "type": "function",
    "function": {
        "name": "get_memories",
        "description": "Retrieve memories for THE CHOSEN SPEAKER ONLY. Do NOT use for candidate evaluation—use backgrounds instead. If speaker memories are already in context, check timestamps for freshness before re-fetching. If stale or absent, fetch to get current data.",
        "parameters": {
            "type": "object",
            "properties": {
                "character_id": {
                    "type": "string",
                    "description": "The character ID of the speaker you've chosen",
                },
                "tiers": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["events", "summaries", "digests", "cores"],
                    },
                    "description": "Which memory tiers to retrieve. If omitted, returns all tiers."
                },
            },
            "required": ["character_id"],
        },
    },
}

_MAX_BATCH_SIZE = 10

BACKGROUND_TOOL = {
    "type": "function",
    "function": {
        "name": "background",
        "description": "Read, write, or update persisted character backgrounds (traits, backstory, connections). Use to retrieve stored details beyond what is shown in the candidate list, or to persist new background info. Supports batch reads for up to 10 characters.",
        "parameters": {
            "type": "object",
            "properties": {
                "character_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Character IDs to query (max 10 per call)",
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
            "required": ["character_ids", "action"],
        },
    },
}

GET_CHARACTER_INFO_TOOL = {
    "type": "function",
    "function": {
        "name": "get_character_info",
        "description": "Get detailed info about characters including gender, background, and squad members. Supports batch queries for up to 10 characters.",
        "parameters": {
            "type": "object",
            "properties": {
                "character_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Character IDs to query (max 10 per call)",
                },
            },
            "required": ["character_ids"],
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
        session_registry: "SessionRegistry | None" = None,
        llm_client_factory: Callable[[], LLMClient] | None = None,
        compaction_engine: Any = None,  # Optional CompactionEngine for memory compression
        compaction_scheduler: Any = None,  # Optional CompactionScheduler (preferred over raw engine)
        max_tool_iterations: int = 5,
        llm_timeout: float = 60.0,
        reasoning: ReasoningOptions | None = None,
    ):
        """Initialize conversation manager.
        
        Args:
            llm_client: Fallback LLM client (used when no session registry or session lacks a client)
            state_client: State query client for tool dispatch
            session_registry: Optional session registry for per-session LLM clients
            llm_client_factory: Optional factory to create per-session LLM clients
            compaction_engine: Optional CompactionEngine (kept for backward compat)
            compaction_scheduler: Optional CompactionScheduler for budget-limited compaction
            max_tool_iterations: Maximum tool call iterations before forcing response
            llm_timeout: Timeout for each LLM call in seconds
            reasoning: Reasoning options for models that support extended thinking
        """
        self.llm_client = llm_client
        self.state_client = state_client
        self.session_registry = session_registry
        self.llm_client_factory = llm_client_factory
        self.compaction_engine = compaction_engine
        self.compaction_scheduler = compaction_scheduler
        self.max_tool_iterations = max_tool_iterations
        self.llm_timeout = llm_timeout
        self.reasoning = reasoning
        
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
- **get_memories(character_id, tiers)**: Retrieve memories for the chosen speaker
  - "events": Recent raw events (last ~100)
  - "summaries": Compressed summaries of past events
  - "digests": Medium-term compressed memories
  - "cores": Long-term persistent memories
- **background(character_ids, action)**: Read, write, or update character backgrounds
  - Supports batch reads for up to 10 characters at once
  - action="read": Retrieve existing traits, backstory, connections
  - action="write": Set entire background (requires content with traits, backstory, connections) — single character only
  - action="update": Modify a single field (requires field and value) — single character only
- **get_character_info(character_ids)**: Get detailed info about characters including gender, background, and squad members
  - Supports batch queries for up to 10 characters at once
  - Returns character details (name, faction, rank, gender, background) plus an array of squad members with the same fields
  - Use when you need squad composition or when generating a background for a character you haven't spoken as before

**Tool Usage Rules:**
1. **background(character_ids, action)**: Read or write persisted character backgrounds
   - Candidate personalities and backstories are already listed above — do NOT fetch backgrounds just for speaker selection
   - Use `action="read"` when you need stored traits/connections beyond what is shown above
   - Use `action="write"` or `action="update"` to persist background details you generate for the speaker

2. **get_memories(character_id, tiers)**: Retrieve the speaker's memories
   - ONLY use for the character you've chosen to speak
   - **Check context first:** if the speaker's memories are already present in this conversation, examine the timestamps:
     - If the most recent memory timestamp is close to the current event, the data is fresh — skip re-fetching
     - If the latest timestamp is old or there are gaps, fetch to get up-to-date context
   - **If no memories are in context** for the chosen speaker, always fetch full memories
   - The `tiers` parameter is optional; omit it to fetch all tiers

3. **Workflow:**
   a. Read event context + candidate list (personalities and backstories are already provided)
   b. Choose speaker based on faction, personality, and relevance to the event
   c. If the chosen speaker's memories are NOT in context, or the last-seen memory timestamp is stale, fetch via get_memories(character_id=...)
   d. Generate dialogue for that speaker

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
        tiers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Tool handler: retrieve memories for the chosen speaker.
        
        Args:
            character_id: Character ID to query
            tiers: List of tier names to retrieve. Defaults to all four tiers.
            
        Returns:
            Dict mapping tier name → memory data
        """
        if tiers is None:
            tiers = ["events", "summaries", "digests", "cores"]

        logger.info("Fetching memories for speaker {} (tiers: {})", character_id, tiers)
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
        character_ids: str | list[str] | None = None,
        character_id: str | None = None,
        action: str = "read",
        content: dict[str, Any] | None = None,
        field: str | None = None,
        value: Any = None,
    ) -> dict[str, Any]:
        """Tool handler: read, write, or update background for character(s).

        Supports batch reads: ``character_ids`` can be a list of up to
        ``_MAX_BATCH_SIZE`` IDs.  For backward compatibility, also accepts
        the old singular ``character_id`` parameter.  Write/update actions
        require exactly one character.

        Args:
            character_ids: Character ID(s) to operate on (list or single string).
            character_id: **Deprecated** singular alias kept for backward compat.
            action: One of "read", "write", "update".
            content: Full background content (for "write").
            field: Field name to update (for "update").
            value: New value for the field (for "update").

        Returns:
            Background data dict. For batch reads: ``{char_id: data, ...}``.
        """
        # --- normalise IDs -------------------------------------------------
        ids: list[str] = _normalise_character_ids(character_ids, character_id)
        if not ids:
            return {"error": "character_ids (or character_id) is required"}
        if len(ids) > _MAX_BATCH_SIZE:
            return {"error": f"Batch size limit: {_MAX_BATCH_SIZE} NPCs max"}
        # De-duplicate while preserving order
        ids = list(dict.fromkeys(ids))
        logger.debug("background batch query for {} characters", len(ids))

        if action == "read":
            batch = BatchQuery()
            for cid in ids:
                batch.add(
                    f"bg_{cid}",
                    resource="memory.background",
                    params={"character_id": cid},
                )

            result = await self.state_client.execute_batch(batch, timeout=10.0)

            backgrounds: dict[str, Any] = {}
            for cid in ids:
                qid = f"bg_{cid}"
                if result.ok(qid):
                    backgrounds[cid] = result[qid] or {}
                else:
                    error_msg = result.error(qid) or "unknown error"
                    logger.warning("background read failed for {}: {}", cid, error_msg)
                    backgrounds[cid] = {"error": error_msg}
            return backgrounds

        # Write/update require exactly one character
        if len(ids) > 1:
            return {"error": f"'{action}' action only supports a single character"}

        single_id = ids[0]

        if action == "write":
            if content is None:
                return {"error": "content is required for write action"}

            mutations = [
                {
                    "op": "set",
                    "resource": "memory.background",
                    "params": {"character_id": single_id},
                    "data": content,
                }
            ]
            success = await self.state_client.mutate_batch(mutations, timeout=10.0)
            return {"success": success, "action": "write", "character_id": single_id}

        elif action == "update":
            if field is None or value is None:
                return {"error": "field and value are required for update action"}

            mutations = [
                {
                    "op": "update",
                    "resource": "memory.background",
                    "params": {"character_id": single_id},
                    "ops": {"$set": {field: value}},
                }
            ]
            success = await self.state_client.mutate_batch(mutations, timeout=10.0)
            return {"success": success, "action": "update", "character_id": single_id, "field": field}

        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _handle_get_character_info(
        self,
        character_ids: str | list[str] | None = None,
        character_id: str | None = None,
    ) -> dict[str, Any]:
        """Tool handler: retrieve detailed character info for one or more NPCs.

        Sends ``query.character_info`` sub-queries for each ID in a single
        ``BatchQuery``.  Accepts both the new ``character_ids`` list and the
        old singular ``character_id`` for backward compatibility.

        Args:
            character_ids: Character ID(s) to query (list or single string).
            character_id: **Deprecated** singular alias kept for backward compat.

        Returns:
            Dict mapping character ID → info dict (or error dict).
        """
        ids: list[str] = _normalise_character_ids(character_ids, character_id)
        if not ids:
            return {"error": "character_ids (or character_id) is required"}
        if len(ids) > _MAX_BATCH_SIZE:
            return {"error": f"Batch size limit: {_MAX_BATCH_SIZE} NPCs max"}
        ids = list(dict.fromkeys(ids))
        logger.debug("get_character_info batch query for {} characters", len(ids))

        batch = BatchQuery()
        for cid in ids:
            batch.add(
                f"ci_{cid}",
                resource="query.character_info",
                params={"id": cid},
            )

        try:
            result = await self.state_client.execute_batch(batch, timeout=10.0)
        except Exception as e:
            logger.warning("get_character_info batch query failed: {}", e)
            return {"error": f"Failed to query character info: {e}"}

        infos: dict[str, Any] = {}
        for cid in ids:
            qid = f"ci_{cid}"
            if result.ok(qid):
                infos[cid] = result[qid] or {}
            else:
                error_msg = result.error(qid) or "unknown error"
                logger.warning("get_character_info failed for {}: {}", cid, error_msg)
                infos[cid] = {"error": f"Character info query failed: {error_msg}"}
        return infos

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

            def _fmt_single(data: dict[str, Any]) -> str:
                char = data.get("character", {})
                squad = data.get("squad_members", [])
                parts_inner: list[str] = [f"**Character:** {_fmt_char(char)}"]
                if squad:
                    parts_inner.append(f"**Squad Members ({len(squad)}):**")
                    for i, m in enumerate(squad, 1):
                        parts_inner.append(f"{i}. {_fmt_char(m)}")
                else:
                    parts_inner.append("**Squad:** No squad members.")
                return "\n\n".join(parts_inner)

            # Batch format: {char_id: {character: ..., squad_members: ...}}
            # Detect batch vs legacy by checking for 'character' key (legacy)
            if "character" in result:
                # Legacy single-character format (backward compat)
                return _fmt_single(result)

            sections: list[str] = []
            for cid, data in result.items():
                if isinstance(data, dict) and "error" in data:
                    sections.append(f"**{cid}:** Error — {data['error']}")
                elif isinstance(data, dict):
                    sections.append(f"--- {cid} ---\n{_fmt_single(data)}")
                else:
                    sections.append(f"**{cid}:** {data}")
            return "\n\n".join(sections)

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

    def _get_llm_client(self, session_id: str | None) -> LLMClient:
        """Return the LLM client for a given session.

        Lifecycle:
        - If a session_registry is configured and the session already has an
          ``llm_client``, return it.
        - If the session exists but has no client yet, create one via the
          factory and store it on the session for reuse.
        - Falls back to ``self.llm_client`` when no registry/factory is
          available (backward-compat).
        """
        if session_id and self.session_registry and self.llm_client_factory:
            session = self.session_registry.get_session(session_id)
            if session.llm_client is None:
                session.llm_client = self.llm_client_factory()
                logger.info("Created per-session LLM client for session {}", session_id)
            return session.llm_client
        return self.llm_client

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
                "op": "append",
                "resource": "memory.events",
                "params": {"character_id": str(char_id)},
                "data": [{"text": witness_text}],
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
        *,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        """Handle an event and generate dialogue using tool-based conversation.
        
        Args:
            event: Event data from game.event topic
            candidates: List of candidate speakers
            world: World description string
            traits: Traits map {character_id → {personality_id, backstory_id}}
            session_id: WebSocket session for per-tenant LLM client
            
        Returns:
            Tuple of (speaker_id, dialogue_text)
            
        Raises:
            ValueError: If no candidates or invalid event data
            TimeoutError: If LLM calls timeout
        """
        # Resolve per-session LLM client (falls back to singleton)
        llm_client = self._get_llm_client(session_id)
        if not candidates:
            raise ValueError("No candidates provided for dialogue")
        
        # Filter out player (game_id "0") — player is never a dialogue candidate
        npc_candidates = [c for c in candidates if str(c.get("game_id", "")) != "0"]
        if not npc_candidates:
            logger.warning("All candidates are player (game_id=0), skipping dialogue")
            return ("0", "")
        candidates = npc_candidates
        
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
        # Inject full formatted content so the LLM can assess freshness and
        # decide whether an additional get_memories() call is necessary.
        logger.debug(f"Pre-fetching memories for speaker {speaker_id}")
        try:
            speaker_memories = await self._handle_get_memories(
                speaker_id,
                tiers=["events", "summaries"],  # Recent context
            )
            
            formatted = self._format_tool_result("get_memories", speaker_memories)
            has_content = any(bool(v) for v in speaker_memories.values())
            
            if has_content:
                memory_context = (
                    f"[Pre-fetched memories for speaker {speaker_id}]\n{formatted}"
                )
                logger.debug(f"Pre-fetched memories for {speaker_id} ({len(formatted)} chars)")
                # Append as system context so LLM sees them before tool loop
                messages.insert(1, Message(role="system", content=memory_context))
        except Exception as e:
            logger.warning(f"Failed to pre-fetch memories for {speaker_id}: {e}")
        
        # Tool-calling loop: call LLM with tools, execute tool calls, repeat
        logger.debug("Starting tool-calling loop for dialogue generation")

        # Build LLM options (reasoning, etc.)
        llm_opts = LLMOptions(reasoning=self.reasoning) if self.reasoning else None

        async def _tool_executor(tc: ToolCall) -> str:
            logger.debug(f"Executing tool call: {tc.name}({tc.arguments})")
            result = await self._execute_tool_call(tc.name, tc.arguments)
            return self._format_tool_result(tc.name, result)

        response: LLMToolResponse = await llm_client.complete_with_tool_loop(
            messages,
            tools=TOOLS,
            tool_executor=_tool_executor,
            opts=llm_opts,
            max_iterations=self.max_tool_iterations,
        )

        dialogue_text = (response.text or "").strip()
        if dialogue_text:
            logger.info(f"LLM raw response ({len(dialogue_text)} chars): {dialogue_text[:200]}")
        else:
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

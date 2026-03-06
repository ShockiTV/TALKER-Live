"""Two-step conversation manager for NPC dialogue.

Implements a deterministic 2-step flow:
1. **Speaker picker** (ephemeral): inject candidate backgrounds + event,
   ask the LLM to choose a speaker, then remove all picker messages.
2. **Dialogue generation** (persistent): inject chosen speaker's memory
   context + event, generate dialogue, keep messages in history.

No LLM tools are exposed — Python fetches all data deterministically
and injects it as message content.
"""

import json
from typing import Any, Callable, TYPE_CHECKING

from loguru import logger

from ..llm import LLMClient, Message
from ..llm.models import LLMOptions, ReasoningOptions
from ..state.client import StateQueryClient
from ..state.batch import BatchQuery
from ..prompts.factions import resolve_faction_name
from ..prompts.dialogue import build_dialogue_user_message
from ..prompts.picker import (
    build_event_description,
    parse_picker_response,
)
from ..prompts.world_context import (
    build_world_context,
    build_world_context_split,
    add_static_context_to_block,
    build_dynamic_world_line,
    get_all_story_ids,
)
from ..state.models import SceneContext
from .context_block import ContextBlock

if TYPE_CHECKING:
    from ..transport.session_registry import SessionRegistry
    from .background_generator import BackgroundGenerator


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


def filter_events_for_speaker(
    events: list[dict[str, Any]],
    speaker_id: str,
) -> list[dict[str, Any]]:
    """Filter events to only those where speaker_id is a witness.

    An event is considered witnessed by a speaker if speaker_id appears in
    the event's ``witnesses`` list (game_id field) or matches the actor/victim.

    Args:
        events: List of event dicts with ``context`` and optional ``witnesses``.
        speaker_id: Character ID of the speaker.

    Returns:
        Filtered list of events where the speaker is a witness.
    """
    result: list[dict[str, Any]] = []
    for event in events:
        witnesses = event.get("witnesses", [])
        # Check witnesses list
        for w in witnesses:
            if isinstance(w, dict) and str(w.get("game_id", "")) == speaker_id:
                result.append(event)
                break
        else:
            # Also check actor/victim (they implicitly witness the event)
            context = event.get("context", {})
            actor = context.get("actor") or context.get("killer")
            victim = context.get("victim")
            if isinstance(actor, dict) and str(actor.get("game_id", "")) == speaker_id:
                result.append(event)
            elif isinstance(victim, dict) and str(victim.get("game_id", "")) == speaker_id:
                result.append(event)
    return result


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


_MAX_BATCH_SIZE = 10


# ---------------------------------------------------------------------------
# Static system prompt (no dynamic content — cache-friendly)
# ---------------------------------------------------------------------------

STATIC_SYSTEM_PROMPT = """You are generating dialogue for NPCs in the Zone (STALKER universe).

**Dialogue Guidelines:**
- Keep dialogue concise and realistic (1-3 sentences typical for reactions)
- Use authentic STALKER-universe language and tone
- Characters should react naturally based on their personality, faction, and memories
- Dialogue should reflect the character's emotional state and relationship to the event
- Avoid breaking character or adding meta-commentary"""


# ---------------------------------------------------------------------------
# Tagged system message builders (used for deduplication)
# ---------------------------------------------------------------------------

def build_event_system_msg(event: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    """Build a tagged ``EVT:`` system message with witness list.

    Format::

        EVT:{ts} — {EVENT_TYPE}: {actor} {verb} {victim}
        Witnesses: Name1(id1), Name2(id2), ...

    Args:
        event: Event data dict with ``type``, ``context``, and ``timestamp``.
        candidates: Candidate speaker dicts (used for witness list).

    Returns:
        Tagged system message content string.
    """
    ts = event.get("timestamp", 0)
    event_type = event.get("type", "unknown")
    event_name = _resolve_event_display_name(event_type)

    context = event.get("context", {})
    actor = context.get("actor") or context.get("killer")
    victim = context.get("victim")

    actor_name = actor.get("name", "Unknown") if isinstance(actor, dict) else str(actor) if actor else None
    victim_name = victim.get("name", "Unknown") if isinstance(victim, dict) else str(victim) if victim else None

    if actor_name and victim_name:
        verb = _VERB_MAP.get(event_name, "affected")
        desc = f"{actor_name} {verb} {victim_name}"
    elif actor_name:
        desc = actor_name
    else:
        desc = ""

    # Build witness list from candidates
    witnesses = []
    for cand in candidates:
        name = cand.get("name", "Unknown")
        cid = cand.get("game_id", "?")
        witnesses.append(f"{name}({cid})")
    witness_line = f"Witnesses: {', '.join(witnesses)}"

    if desc:
        return f"EVT:{ts} — {event_name}: {desc}\n{witness_line}"
    return f"EVT:{ts} — {event_name}\n{witness_line}"


def build_bg_system_msg(char_id: str, name: str, faction: str, bg_text: str) -> str:
    """Build a tagged ``BG:`` system message.

    Format::

        BG:{char_id} — {name} ({faction})
        {background_text}

    Args:
        char_id: Character ID string.
        name: Character display name.
        faction: Human-readable faction name.
        bg_text: Formatted background text.

    Returns:
        Tagged system message content string.
    """
    return f"BG:{char_id} — {name} ({faction})\n{bg_text}"


def build_mem_system_msg(char_id: str, start_ts: int, tier: str, text: str) -> str:
    """Build a tagged ``MEM:`` system message.

    Format::

        MEM:{char_id}:{start_ts} — [{tier}] {text}

    Args:
        char_id: Character ID string.
        start_ts: Memory item timestamp.
        tier: Tier label (e.g. ``SUMMARIES``, ``DIGESTS``, ``CORES``).
        text: Memory narrative text.

    Returns:
        Tagged system message content string.
    """
    return f"MEM:{char_id}:{start_ts} — [{tier}] {text}"


class ConversationManager:
    """Two-step deterministic dialogue manager with cache-friendly message layout.

    Architecture (four-layer message structure):
    - ``_messages[0]`` — **system**: Static dialogue rules (never changes).
    - ``_messages[1]`` — **user**: Context block Markdown (BGs + MEMs,
      append-only via ``ContextBlock``).
    - ``_messages[2]`` — **assistant**: ``"Ready."`` synthetic ack.
    - ``_messages[3+]`` — Dialogue turns (picker ephemeral, dialogue persistent).

    Character backgrounds and memories are stored in the ``ContextBlock``
    which renders to Markdown in ``_messages[1]``.  Weather, time, and
    location are included in per-turn instruction messages (Layer 4).

    Flow:
    1. Ensure all candidates have backgrounds (via BackgroundGenerator)
    2. Add candidate BGs + MEMs to ContextBlock, update ``_messages[1]``
    3. Pick speaker (ephemeral — messages removed after)
    4. Generate dialogue (persistent — keeps messages in history)
    5. Inject witness events + schedule compaction
    6. Return (speaker_id, dialogue_text)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        state_client: StateQueryClient,
        *,
        session_registry: "SessionRegistry | None" = None,
        llm_client_factory: Callable[[], LLMClient] | None = None,
        background_generator: "BackgroundGenerator | None" = None,
        fast_llm_client: LLMClient | None = None,
        compaction_engine: Any = None,
        compaction_scheduler: Any = None,
        llm_timeout: float = 60.0,
        reasoning: ReasoningOptions | None = None,
    ):
        """Initialize conversation manager.

        Args:
            llm_client: Fallback LLM client (or factory-produced per session)
            state_client: State query client for batch queries / mutations
            session_registry: Optional session registry for per-session LLM clients
            llm_client_factory: Optional factory to create per-session LLM clients
            background_generator: Optional BackgroundGenerator (created internally if None)
            fast_llm_client: Optional fast/cheap LLM client for background generation
            compaction_engine: Optional CompactionEngine (kept for backward compat)
            compaction_scheduler: Optional CompactionScheduler for budget-limited compaction
            llm_timeout: Timeout for each LLM call in seconds
            reasoning: Reasoning options for models that support extended thinking
        """
        self.llm_client = llm_client
        self.state_client = state_client
        self.session_registry = session_registry
        self.llm_client_factory = llm_client_factory
        self.compaction_engine = compaction_engine
        self.compaction_scheduler = compaction_scheduler
        self.llm_timeout = llm_timeout
        self.reasoning = reasoning

        # Background generator for missing backgrounds
        if background_generator is not None:
            self.background_generator = background_generator
        else:
            from .background_generator import BackgroundGenerator
            self.background_generator = BackgroundGenerator(
                llm_client, state_client, fast_llm_client=fast_llm_client,
            )

        # Four-layer message structure:
        # [0] system: static rules  [1] user: context block  [2] assistant: "Ready."
        self._messages: list[Message] = [
            Message(role="system", content=STATIC_SYSTEM_PROMPT),
            Message(role="user", content=""),
            Message(role="assistant", content="Ready."),
        ]

        # Append-only context block for BG/MEM deduplication and rendering
        self._context_block = ContextBlock()

        # Cached world context split (populated on first event)
        self._world_split: Any = None
    
    def _build_system_prompt(self, world: str = "") -> str:
        """Return the static system prompt with Zone setting and dialogue guidelines.

        The system prompt contains only timeless dialogue rules — no weather,
        time, location, inhabitants, or other dynamic content.  This ensures
        the first message is byte-identical across LLM calls for cache hits.

        Args:
            world: Ignored (kept for backward compatibility).

        Returns:
            Static system prompt string.
        """
        return STATIC_SYSTEM_PROMPT
    
    # ------------------------------------------------------------------
    # Memory helpers (internal — no longer exposed as LLM tools)
    # ------------------------------------------------------------------

    async def _fetch_memories(
        self,
        character_id: str,
        tiers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Retrieve memories for a character.

        Args:
            character_id: Character ID to query.
            tiers: Tier names to retrieve.  Defaults to all four.

        Returns:
            Dict mapping tier name -> memory data (list of entries).
        """
        if tiers is None:
            tiers = ["events", "summaries", "digests", "cores"]

        logger.info("Fetching memories for {} (tiers: {})", character_id, tiers)
        batch = BatchQuery()
        for tier in tiers:
            batch.add(f"mem_{tier}", resource=f"memory.{tier}", params={"character_id": character_id})

        result = await self.state_client.execute_batch(batch, timeout=10.0)

        memories: dict[str, Any] = {}
        for tier in tiers:
            qid = f"mem_{tier}"
            if result.ok(qid):
                memories[tier] = result[qid]
            else:
                err = result.error(qid) or "unknown error"
                logger.warning("get_memories failed for {}.{}: {}", character_id, tier, err)
                memories[tier] = []
        return memories

    # ------------------------------------------------------------------
    # Memory formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _format_memories(memories: dict[str, Any]) -> tuple[str, int]:
        """Format memory tier data as human-readable text.

        Returns:
            Tuple of (formatted_text, latest_timestamp).
        """
        parts: list[str] = []
        latest_ts = 0

        for tier, entries in memories.items():
            if not entries:
                continue
            header = f"[{tier.upper()}] {len(entries)} entries:"
            items: list[str] = []
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        ts = entry.get("timestamp", entry.get("ts", 0))
                        if isinstance(ts, (int, float)) and ts > latest_ts:
                            latest_ts = int(ts)
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

        text = "\n\n".join(parts) if parts else "No memories available."
        return text, latest_ts

    @staticmethod
    def _format_background(bg: dict[str, Any] | None) -> str:
        """Format a background dict as readable text.

        Args:
            bg: Background dict with traits/backstory/connections, or None.

        Returns:
            Formatted background text.
        """
        if not bg:
            return "No background on record."
        parts: list[str] = []
        traits = bg.get("traits", [])
        if traits:
            parts.append(f"Traits: {', '.join(str(t) for t in traits)}")
        backstory = bg.get("backstory", "")
        if backstory:
            parts.append(f"Backstory: {backstory}")
        connections = bg.get("connections", [])
        if connections:
            parts.append(f"Connections: {', '.join(str(c) for c in connections)}")
        return "\n".join(parts) if parts else "No background on record."

    # ------------------------------------------------------------------
    # Memory diff injection
    # ------------------------------------------------------------------

    async def _fetch_full_memory(self, character_id: str) -> tuple[str, int]:
        """Fetch all memory tiers for a first-time speaker.

        Returns:
            (formatted_text, latest_timestamp)
        """
        memories = await self._fetch_memories(character_id)
        return self._format_memories(memories)

    async def _fetch_diff_memory(self, character_id: str, since_ts: int) -> tuple[str, int]:
        """Fetch only events newer than *since_ts* for a returning speaker.

        Returns:
            (formatted_text, latest_timestamp)  — latest_ts may equal
            *since_ts* when there is nothing new.
        """
        # Fetch events tier only (diff-relevant)
        memories = await self._fetch_memories(character_id, tiers=["events"])
        events = memories.get("events", [])

        # Filter to entries newer than since_ts
        new_events = []
        latest_ts = since_ts
        for entry in events if isinstance(events, list) else []:
            ts = entry.get("timestamp", entry.get("ts", 0)) if isinstance(entry, dict) else 0
            if isinstance(ts, (int, float)) and ts > since_ts:
                new_events.append(entry)
                if ts > latest_ts:
                    latest_ts = int(ts)

        if not new_events:
            return "No new memories since your last dialogue.", since_ts

        formatted = {"events": new_events}
        text, _ = self._format_memories(formatted)
        return f"Additional events since last time you spoke:\n{text}", latest_ts

    async def _inject_speaker_memory(
        self,
        speaker: dict[str, Any],
    ) -> str:
        """Add memory items to ContextBlock for the chosen speaker.

        For first-time speakers: fetches all compacted memory tiers
        (summaries, digests, cores) and adds each to the context block.

        For returning speakers: adds only un-tracked memory items.

        Updates ``_messages[1]`` with refreshed context block Markdown.

        Args:
            speaker: The chosen speaker candidate dict.

        Returns:
            Personal narrative text for inclusion in the dialogue user message.
        """
        char_id = str(speaker.get("game_id", ""))
        name = speaker.get("name", "Unknown")

        # Detect if this character has previously had memories injected
        is_returning = any(
            cid == char_id for cid, _ in self._context_block._mem_keys
        )

        # Fetch compacted memories (not events — those go in per-turn messages)
        memories = await self._fetch_memories(char_id, tiers=["summaries", "digests", "cores"])

        new_items: list[tuple[str, str]] = []

        for tier, entries in memories.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                ts = int(entry.get("timestamp", entry.get("ts", 0)))
                text = entry.get("description", entry.get("text", str(entry)))
                if not text:
                    continue

                if self._context_block.add_memory(char_id, name, ts, tier.upper(), text):
                    new_items.append((tier, text))

        # Update _messages[1] with refreshed context block
        self._messages[1] = Message(
            role="user", content=self._context_block.render_markdown(),
        )

        if new_items:
            return "\n".join(f"[{tier.upper()}] {text}" for tier, text in new_items)

        if is_returning:
            return "No new memories since your last dialogue."

        # First-time speaker with no compacted memories
        return ""

    # ------------------------------------------------------------------
    # Speaker picker (ephemeral)
    # ------------------------------------------------------------------

    async def _run_speaker_picker(
        self,
        candidates: list[dict[str, Any]],
        event: dict[str, Any],
        llm_client: LLMClient,
        dynamic_world_line: str = "",
    ) -> dict[str, Any]:
        """Run the ephemeral speaker picker step.

        Builds a user message with the triggering event description and
        candidate IDs.  No witness events from the event store are included.
        Weather/time/location are included inline.

        After the LLM responds, both the user message and assistant response
        are removed from history (ephemeral).

        Falls back to the first candidate on parse failure.

        Args:
            candidates: Candidate dicts (with backgrounds populated).
            event: Event data dict.
            llm_client: LLM client to use.
            dynamic_world_line: Per-turn weather/time/location string.

        Returns:
            The chosen candidate dict.
        """
        if len(candidates) == 1:
            logger.debug("Single candidate — skipping picker")
            return candidates[0]

        # Build picker message with event description + candidate IDs (no witness events)
        event_desc = build_event_description(event)
        candidate_ids_list = [str(c.get("game_id", "")) for c in candidates]
        ids_str = ", ".join(candidate_ids_list)

        parts: list[str] = []
        if dynamic_world_line:
            parts.append(dynamic_world_line)
        parts.append(event_desc)
        parts.append(f"Candidates: {ids_str}")
        parts.append(
            "Pick the character who would most naturally react to this event. "
            "Respond with ONLY their character ID."
        )
        picker_content = "\n".join(parts)
        picker_msg = Message(role="user", content=picker_content)

        # Remember pre-injection count so we can cleanly remove
        pre_count = len(self._messages)

        self._messages.append(picker_msg)

        llm_opts = LLMOptions(reasoning=self.reasoning) if self.reasoning else None

        try:
            response = await llm_client.complete(self._messages, opts=llm_opts)
        except Exception as e:
            logger.error("Speaker picker LLM call failed: {}", e)
            # Remove injected message on failure
            del self._messages[pre_count:]
            return candidates[0]

        # Append assistant response temporarily (for context accuracy)
        self._messages.append(Message(role="assistant", content=response))

        # Parse response
        candidate_ids = {str(c.get("game_id", "")) for c in candidates}
        picked_id = parse_picker_response(response, candidate_ids)

        # Remove ephemeral messages (1 user + 1 assistant)
        del self._messages[pre_count:]

        if picked_id is None:
            logger.warning("Picker response '{}' did not match any candidate — falling back to first", response.strip()[:100])
            return candidates[0]

        for cand in candidates:
            if str(cand.get("game_id", "")) == picked_id:
                logger.info("Picker chose speaker: {} ({})", cand.get("name"), picked_id)
                return cand

        # Safety fallback
        return candidates[0]

    # ------------------------------------------------------------------
    # Dialogue generation (persistent)
    # ------------------------------------------------------------------

    async def _run_dialogue_generation(
        self,
        speaker: dict[str, Any],
        event: dict[str, Any],
        llm_client: LLMClient,
        dynamic_world_line: str = "",
        witness_events: list[dict[str, Any]] | None = None,
    ) -> str:
        """Run the persistent dialogue generation step.

        Adds speaker MEMs to the context block, then builds a user message
        with the event description, weather/time/location, and only
        speaker-witnessed events.  Both the user message and assistant
        response are kept in conversation history.

        Args:
            speaker: The chosen speaker dict (with background populated).
            event: Event data dict.
            llm_client: LLM client to use.
            dynamic_world_line: Per-turn weather/time/location string.
            witness_events: Events where this speaker is a witness.

        Returns:
            Generated dialogue text.
        """
        # Add memories to context block and get personal narrative
        narrative = await self._inject_speaker_memory(speaker)

        speaker_name = speaker.get("name", "Unknown")
        speaker_id = str(speaker.get("game_id", ""))

        # Build triggering event description
        event_desc = build_event_description(event)

        # Build witness events text (only events where speaker is a witness)
        witness_text = ""
        if witness_events:
            witness_lines = [build_witness_text(e) for e in witness_events]
            witness_text = "\n".join(witness_lines)

        # Assemble dialogue user message
        parts: list[str] = []
        if dynamic_world_line:
            parts.append(dynamic_world_line)
        parts.append(event_desc)
        if witness_text:
            parts.append(f"\n**Recent events witnessed by {speaker_name}:**\n{witness_text}")
        parts.append(f"\nReact as **{speaker_name}** (ID: {speaker_id}).")
        if narrative:
            parts.append(f"\n**Personal memories:**\n{narrative}")
        parts.append(
            f"\nGenerate {speaker_name}'s dialogue — just the spoken words, nothing else."
        )
        user_content = "\n".join(parts)

        self._messages.append(Message(role="user", content=user_content))

        llm_opts = LLMOptions(reasoning=self.reasoning) if self.reasoning else None

        try:
            response = await llm_client.complete(self._messages, opts=llm_opts)
        except Exception as e:
            logger.error("Dialogue generation LLM call failed: {}", e)
            # Remove the user message on failure
            self._messages.pop()
            return ""

        dialogue_text = response.strip()

        # Keep assistant response in history (persistent)
        self._messages.append(Message(role="assistant", content=dialogue_text))

        return dialogue_text

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

    def rebuild_context_block(self) -> None:
        """Rebuild the ContextBlock from scratch after compaction.

        Creates a new empty ``ContextBlock``, re-adds all known backgrounds
        from the old block, and replaces ``_messages[1]``.  Memory items are
        NOT re-added — the caller should re-add compacted memory items after
        calling this method.

        Also re-adds static world context entries if ``_world_split`` is cached.
        """
        old_bgs = self._context_block.get_all_backgrounds()
        self._context_block = ContextBlock()

        # Re-add all backgrounds
        for bg in old_bgs:
            self._context_block.add_background(bg.char_id, bg.name, bg.faction, bg.text)

        # Re-add static world context items if available
        if self._world_split is not None:
            add_static_context_to_block(self._context_block, self._world_split)

        # Update _messages[1]
        self._messages[1] = Message(
            role="user", content=self._context_block.render_markdown(),
        )
        logger.debug("Context block rebuilt ({} items)", self._context_block.item_count)

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
        """Handle an event using the deterministic 2-step dialogue flow.

        Four-layer message layout:
        1. Filter candidates, fetch world context split
        2. Add candidate BGs to ContextBlock, update ``_messages[1]``
        3. Run speaker picker (ephemeral — messages removed after)
        4. Add speaker MEMs to ContextBlock, run dialogue generation
        5. Inject witness events + schedule compaction

        Args:
            event: Event data from game.event topic
            candidates: List of candidate speakers
            world: World description string (from Lua, used as fallback)
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

        # Fetch world context split (static → context block, dynamic → per-turn)
        dynamic_world_line = world  # fallback to Lua-provided world string
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

            # Build structured world context
            world_split = build_world_context_split(scene_ctx, alive_status=alive_status)
            self._world_split = world_split

            # Add static items to context block (inhabitants, factions, info portions)
            add_static_context_to_block(self._context_block, world_split)

            # Build dynamic per-turn line (weather, time, location)
            dyn = build_dynamic_world_line(world_split)
            if dyn:
                dynamic_world_line = dyn
        except Exception as e:
            logger.warning(f"Failed to enrich world context: {e}")

        # Ensure all candidates have backgrounds
        try:
            await self.background_generator.ensure_backgrounds(candidates)
        except Exception as e:
            logger.warning(f"Background generation failed: {e}")

        # Add candidate backgrounds to context block
        for cand in candidates:
            char_id = str(cand.get("game_id", ""))
            if char_id and not self._context_block.has_background(char_id):
                bg_text = self._format_background(cand.get("background"))
                name = cand.get("name", "Unknown")
                faction = resolve_faction_name(cand.get("faction", "unknown"))
                self._context_block.add_background(char_id, name, faction, bg_text)

        # Update context block user message (_messages[1])
        self._messages[1] = Message(
            role="user", content=self._context_block.render_markdown(),
        )

        # Step 1: Speaker picker (ephemeral — messages removed after)
        speaker = await self._run_speaker_picker(
            candidates, event, llm_client, dynamic_world_line=dynamic_world_line,
        )
        speaker_id = str(speaker.get("game_id", "unknown"))
        logger.info("Selected speaker: {} ({})", speaker.get("name"), speaker_id)

        # Fetch witness events for the chosen speaker
        witness_events: list[dict[str, Any]] = []
        try:
            ev_batch = (
                BatchQuery()
                .add("events", "query.memory.events",
                     params={"character_id": speaker_id})
            )
            ev_result = await self.state_client.execute_batch(ev_batch, timeout=10.0)
            if ev_result.ok("events"):
                raw_events = ev_result["events"]
                if isinstance(raw_events, list):
                    witness_events = raw_events
        except Exception as e:
            logger.warning(f"Failed to fetch witness events for {speaker_id}: {e}")

        # Step 2: Dialogue generation (persistent — injects MEM + keeps messages)
        dialogue_text = await self._run_dialogue_generation(
            speaker, event, llm_client,
            dynamic_world_line=dynamic_world_line,
            witness_events=witness_events,
        )

        if not dialogue_text:
            logger.warning("LLM returned empty dialogue text")
            return (speaker_id, "")

        logger.info(f"Generated dialogue for {speaker_id}: {dialogue_text[:80]}...")

        # Post-dialogue: inject witness events for all alive candidates
        await self._inject_witness_events(event, candidates)

        # Schedule budget-limited compaction for all candidates
        if self.compaction_scheduler:
            candidate_ids = {str(c.get("game_id")) for c in candidates if c.get("game_id")}
            import asyncio
            asyncio.create_task(self.compaction_scheduler.schedule(candidate_ids))

        return (speaker_id, dialogue_text)

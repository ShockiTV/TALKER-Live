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
    parse_picker_response,
)
from ..prompts.world_context import build_world_context, get_all_story_ids
from ..state.models import SceneContext
from .dedup_tracker import DeduplicationTracker

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
    """Two-step deterministic dialogue manager with deduplicated system messages.

    Architecture:
    - System prompt: Zone setting, world state, notable inhabitants,
      dialogue guidelines.  No per-character persona.
    - Tagged system messages: EVT: (events), BG: (backgrounds), MEM: (memories)
      — injected once and deduplicated via ``DeduplicationTracker``.
    - Step 1 — **Speaker picker** (ephemeral): single pointer user message
      referencing EVT:{ts} and listing candidate IDs → LLM returns character
      ID → remove picker user message + assistant response.
    - Step 2 — **Dialogue generation** (persistent): pointer user message
      with EVT:{ts}, character ID, and personal narrative → LLM returns
      dialogue → keep both messages in history.

    Flow:
    1. Ensure all candidates have backgrounds (via BackgroundGenerator)
    2. Inject EVT: system message for triggering event
    3. Inject BG: system messages for candidate backgrounds
    4. Pick speaker (ephemeral pointer, or skip if single candidate)
    5. Inject MEM: system messages for speaker's compacted memories
    6. Generate dialogue (persistent pointer)
    7. Inject witness events + schedule compaction
    8. Return (speaker_id, dialogue_text)
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

        # Persistent conversation history (system prompt set on first event)
        self._messages: list[Message] = []

        # Deduplication tracker replacing _memory_timestamps
        self._tracker = DeduplicationTracker()
    
    def _build_system_prompt(self, world: str) -> str:
        """Build system prompt with Zone setting, world context, and dialogue guidelines.

        The system prompt does NOT include per-character persona, faction
        description, or tool instructions.  Character-specific context is
        injected per-turn in the dialogue step.

        Args:
            world: World description (location, time, weather, inhabitants, etc.)

        Returns:
            Complete system prompt string.
        """
        return f"""You are generating dialogue for NPCs in the Zone (STALKER universe).

**Current Context:** {world}

**Dialogue Guidelines:**
- Keep dialogue concise and realistic (1-3 sentences typical for reactions)
- Use authentic STALKER-universe language and tone
- Characters should react naturally based on their personality, faction, and memories
- Dialogue should reflect the character's emotional state and relationship to the event
- Avoid breaking character or adding meta-commentary"""
    
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
        """Inject MEM: system messages and build personal narrative for the chosen speaker.

        For first-time speakers: fetches all compacted memory tiers
        (summaries, digests, cores), injects each as a ``MEM:`` system
        message, and returns the full narrative text.

        For returning speakers: injects only un-tracked memory items and
        returns narrative of new items only.  Returns a no-change message
        when nothing is new.

        Args:
            speaker: The chosen speaker candidate dict.

        Returns:
            Personal narrative text for inclusion in the dialogue user message.
        """
        char_id = str(speaker.get("game_id", ""))

        # Detect if this character has previously had memories injected
        is_returning = self._tracker.has_mem_for_character(char_id)

        # Fetch compacted memories (not events — those are EVT: system messages)
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

                if not self._tracker.is_mem_injected(char_id, ts):
                    content = build_mem_system_msg(char_id, ts, tier.upper(), text)
                    self._messages.append(Message(role="system", content=content))
                    self._tracker.mark_mem(char_id, ts)
                    new_items.append((tier, text))

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
    ) -> dict[str, Any]:
        """Run the ephemeral speaker picker step.

        Injects a single pointer user message referencing the event by
        timestamp and listing candidate IDs.  All factual context (event
        details, candidate backgrounds) is already present as system
        messages.  After the LLM responds, both the user message and
        assistant response are removed from history.

        Falls back to the first candidate on parse failure.

        Args:
            candidates: Candidate dicts (with backgrounds populated).
            event: Event data dict.
            llm_client: LLM client to use.

        Returns:
            The chosen candidate dict.
        """
        if len(candidates) == 1:
            logger.debug("Single candidate — skipping picker")
            return candidates[0]

        # Build pointer-based picker message
        event_ts = event.get("timestamp", 0)
        candidate_ids_list = [str(c.get("game_id", "")) for c in candidates]
        ids_str = ", ".join(candidate_ids_list)
        picker_content = f"Pick speaker for EVT:{event_ts}. Candidates: {ids_str}"
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
    ) -> str:
        """Run the persistent dialogue generation step.

        Injects speaker MEM: system messages, then builds a pointer-based
        user message referencing EVT:{ts} and the character ID with personal
        narrative.  Both the user message and assistant response are kept in
        conversation history.  Event details and backgrounds are NOT inlined
        — they are already present as system messages.

        Args:
            speaker: The chosen speaker dict (with background populated).
            event: Event data dict.
            llm_client: LLM client to use.

        Returns:
            Generated dialogue text.
        """
        # Inject MEM: system messages and get personal narrative
        narrative = await self._inject_speaker_memory(speaker)

        speaker_name = speaker.get("name", "Unknown")
        speaker_id = str(speaker.get("game_id", ""))
        event_ts = event.get("timestamp", 0)

        user_content = build_dialogue_user_message(
            speaker_name=speaker_name,
            speaker_id=speaker_id,
            event_ts=event_ts,
            narrative=narrative,
        )

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

        Flow:
        1. Filter candidates, enrich world context
        2. Set/rebuild system prompt
        3. Ensure all candidates have backgrounds
        4. Inject EVT: system message for the triggering event
        5. Inject BG: system messages for candidate backgrounds
        6. Run speaker picker (ephemeral — messages removed after)
        7. Run dialogue generation (persistent — injects MEM: + keeps messages)
        8. Inject witness events + schedule compaction

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

        # Set (or rebuild) the system prompt — always first message
        system_prompt = self._build_system_prompt(world)
        if self._messages:
            self._messages[0] = Message(role="system", content=system_prompt)
        else:
            self._messages = [Message(role="system", content=system_prompt)]

        # Ensure all candidates have backgrounds
        try:
            await self.background_generator.ensure_backgrounds(candidates)
        except Exception as e:
            logger.warning(f"Background generation failed: {e}")

        # Inject EVT: system message for the triggering event
        event_ts = event.get("timestamp", 0)
        if not self._tracker.is_event_injected(event_ts):
            evt_content = build_event_system_msg(event, candidates)
            self._messages.append(Message(role="system", content=evt_content))
            self._tracker.mark_event(event_ts)

        # Inject BG: system messages for each candidate's background
        for cand in candidates:
            char_id = str(cand.get("game_id", ""))
            if char_id and not self._tracker.is_bg_injected(char_id):
                bg_text = self._format_background(cand.get("background"))
                name = cand.get("name", "Unknown")
                faction = resolve_faction_name(cand.get("faction", "unknown"))
                bg_content = build_bg_system_msg(char_id, name, faction, bg_text)
                self._messages.append(Message(role="system", content=bg_content))
                self._tracker.mark_bg(char_id)

        # Step 1: Speaker picker (ephemeral — messages removed after)
        speaker = await self._run_speaker_picker(candidates, event, llm_client)
        speaker_id = str(speaker.get("game_id", "unknown"))
        logger.info("Selected speaker: {} ({})", speaker.get("name"), speaker_id)

        # Step 2: Dialogue generation (persistent — injects MEM: + keeps messages)
        dialogue_text = await self._run_dialogue_generation(speaker, event, llm_client)

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

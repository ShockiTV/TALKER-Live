## Context

The current `ConversationManager` in `dialogue/conversation.py` uses an LLM tool-calling loop: it exposes `get_memories`, `background`, and `get_character_info` tools, then lets the LLM decide what to fetch and when. In practice the LLM usage is predictable — it reads backgrounds, picks a speaker, reads memories, generates dialogue — but the tool-loop mechanism adds 2-6 round-trips per event, requires tool-calling model support, and produces unpredictable behavior (models sometimes re-fetch data already in context, skip fetching, or hallucinate tool calls).

The pre-seeded unique NPC backgrounds (via `unique_backgrounds.lua`) cover ~120 story characters, but generic NPCs still lack backgrounds entirely. When the tool-loop encounters a null background it must spend a tool call round generating one — wasting context and introducing variability.

## Goals / Non-Goals

**Goals:**
- Replace the tool-calling loop with a deterministic 2-step flow: speaker selection → dialogue generation
- Ensure all candidates have backgrounds before speaker selection begins (background generation for missing characters)
- Support efficient memory injection via diff tracking — only inject new memories for returning speakers
- Keep the main conversation persistent across events within a session (dialogue pairs accumulate)
- Eliminate the tool-calling model requirement — any instruction-following model works
- Maintain existing data flow integrity (witness injection, compaction scheduling, TTS dispatch)

**Non-Goals:**
- Changing the Lua wire protocol or event payload structure
- Modifying memory store architecture or compaction logic
- Adding conversation history pruning/windowing (separate concern, future work)
- Changing how `query.world` or `query.characters_alive` data is fetched (pre-fetch batch stays)
- Removing `background(action="write/update")` mutation capability from Python — the background generator needs it

## Decisions

### 1. Two-step flow with ephemeral speaker picker messages

**Decision**: The `handle_event()` method runs two sequential LLM calls against the same persistent conversation:

1. **Speaker picker**: Inject candidate backgrounds + event description + "pick speaker" instruction as temporary messages. Call `complete()`. Parse speaker ID. Remove all injected messages and the response.
2. **Dialogue generation**: Inject chosen speaker's memories (full or diff) + event description + "react as this NPC" instruction as permanent messages. Call `complete()`. Keep both user message and assistant response in history.

**Rationale**: Running both steps in the same conversation means the LLM has accumulated session context (prior dialogue turns) for both decisions. Removing the picker messages keeps the history clean — only event+dialogue pairs accumulate, no selection noise.

**Alternative considered**: Two completely separate conversations — one for picking, one for dialogue. Rejected because the picker benefits from seeing prior dialogue turns (a character who just spoke is less likely to speak again), and maintaining two parallel conversation histories is wasteful.

### 2. Background generation as a separate blocking LLM call

**Decision**: Before speaker selection, Python batch-reads `memory.background` for all candidates. If any return null, Python gathers character info (via `get_character_info` batch query) for the missing characters plus their squad members, then runs a separate one-shot LLM conversation:

- System prompt: GM-style background generator instructions
- User message: JSON payload with all characters (those with backgrounds included for reference, those without marked for generation), squad membership
- Response: JSON array of generated backgrounds
- Persist each generated background via `state.mutate.batch`

This call blocks — the event waits for backgrounds to complete before proceeding to the speaker picker.

**Rationale**: The speaker picker needs all backgrounds to make informed decisions. The background generation context is different from dialogue context (it's world-building, not roleplay), so a separate conversation with its own system prompt is cleaner. The blocking cost (~3-5s) only occurs once per new character; subsequent events skip it.

**Alternative considered**: Fire-and-forget async generation (current event proceeds with partial backgrounds). Rejected because the picker can't fairly evaluate candidates without seeing their backgrounds.

### 3. JSON-in, JSON-out for background generation

**Decision**: The background generator receives structured JSON as user content and returns structured JSON:

Input:
```json
{
  "characters": [
    { "id": "12467", "name": "Wolf", "faction": "Loners", "rank": "veteran", "gender": "male",
      "background": { "traits": [...], "backstory": "...", "connections": [...] } },
    { "id": "34221", "name": "Petrov", "faction": "Loners", "rank": "novice", "gender": "male",
      "squad": "Wolf's squad", "background": null }
  ]
}
```

Output:
```json
[
  { "id": "34221", "background": { "traits": [...], "backstory": "...", "connections": [...] } }
]
```

**Rationale**: JSON is unambiguous for both input and output parsing. Existing backgrounds serve as style examples for the generator. The LLM sees squad relationships and faction context. The main model handles this since it's creative work.

### 4. Memory diff tracking per session

**Decision**: `ConversationManager` maintains a `dict[str, int]` mapping `character_id → last_injected_timestamp` per session. When injecting memories for the chosen speaker:
- If the character has no entry (first time speaking): inject full memory dump (all tiers)
- If the character has an entry: inject only events/summaries with timestamp > last seen value

After injection, update the tracking dict with the latest timestamp from the injected data.

**Rationale**: Repeated speakers (e.g., companion Wolf who reacts to many events) would bloat the conversation with redundant memory context. Diff injection keeps the conversation efficient while ensuring the LLM always has current context.

**Alternative considered**: Re-inject full memories every time and rely on the model's attention to distinguish new vs old. Rejected because it wastes tokens and context window, especially for characters with long histories.

### 5. Message structure for speaker picker (ephemeral)

**Decision**: The speaker picker injection consists of:
1. One `user` message containing all candidate backgrounds as JSON entries
2. One `user` message containing the event description (same format as dialogue step)
3. One `user` message: "Pick the character who would most naturally react to this event. Respond with only their character ID."
4. One `assistant` response: the character ID

All four messages are removed after parsing the response.

**Rationale**: Separate messages let the LLM process backgrounds and event context independently. The terse instruction ("respond with only their character ID") constrains output to a parseable format. JSON candidate data avoids narrative framing overhead.

### 6. Message structure for dialogue generation (persistent)

**Decision**: The dialogue injection consists of:
1. One `user` message: speaker's memory context (full or diff) + event description + "React as [name] to this event."
2. One `assistant` response: the dialogue text

Both messages are kept in conversation history permanently.

**Rationale**: Combining memory + event + instruction in a single user message keeps the conversation history linear and easy to reason about. No `[SPEAKER: id]` prefix needed since the speaker was already decided in the picker step.

### 7. System prompt remains stable per session, includes ongoing persona

**Decision**: The system prompt contains Zone-setting context, world state, notable inhabitants, and generic dialogue guidelines (tone, length, style). It does NOT contain per-character persona — that comes from the memory/background injection in each turn. The system prompt is rebuilt when world context changes (map transition) but is otherwise stable.

**Rationale**: In the old tool-based flow, the system prompt included the first candidate's personality since the system assumed a single speaker. With the 2-step flow, the speaker changes per event, so persona belongs in the per-turn context, not the system prompt.

### 8. Retaining background read/write via state queries (not tools)

**Decision**: The `_handle_background()` method remains as internal Python logic for reading/writing backgrounds via `state.mutate.batch`. It is no longer exposed as an LLM tool — Python calls it directly during the background generation step.

**Rationale**: The state query infrastructure works well. We just remove the tool-calling indirection — Python knows when backgrounds are needed and handles it deterministically.

## Risks / Trade-offs

- **First-encounter latency** (~3-5s for background generation): Mitigated by the fact that it's one-time per character. Unique NPCs already have seeded backgrounds. Only generic NPCs trigger this.
- **Loss of LLM agency in information gathering**: The tool-based approach let the LLM request exactly what it needed. The deterministic approach may inject more data than needed (full backgrounds for all candidates) or miss edge cases. Mitigated by the observation that tool usage was already formulaic.
- **Speaker picker quality depends on background completeness**: If background generation produces low-quality backgrounds, the picker makes worse decisions. Mitigated by using the main model for generation and providing existing backgrounds as style reference.
- **Conversation history growth**: Without windowing, the persistent conversation grows indefinitely. For a typical play session (~50 events, ~2 messages each = ~100 messages), this is manageable. Longer sessions may need pruning — out of scope for this change.
- **Two LLM calls per event instead of one (sometimes)**: The tool-based flow could complete in 1 call if the LLM chose not to use tools. The 2-step flow always makes 2 calls. However, the tool-based flow often made 3-5 calls, so average cost should decrease.

## MODIFIED Requirements

### Dialogue Generator Service

The system MUST provide `ConversationManager` class as the sole dialogue generation path, replacing `DialogueGenerator`. There SHALL be no `SpeakerSelector` — speaker selection is inline within the single LLM turn.

The `ConversationManager` class MUST provide:
- `async handle_event(event, session_id)` method as main entry point
- Access to state query client for fetching Lua state
- Access to LLM client with tool-calling support
- Tool definitions for `get_memories` and `background`
- Publisher for sending display commands

#### Scenario: All dialogue flows through ConversationManager
- **WHEN** any dialogue-triggering event occurs
- **THEN** dialogue generation SHALL be handled by the `ConversationManager`
- **AND** no separate speaker selection LLM call SHALL occur

#### Scenario: Service unavailable during dialogue request
- **WHEN** a dialogue request cannot be fulfilled due to service issues
- **THEN** the request SHALL fail gracefully (no dialogue displayed)
- **AND** there SHALL be no fallback to Lua-based generation

### Dialogue Request Flow

The system MUST handle dialogue in a single LLM turn:
1. Pre-fetch state batch (world, dead NPCs, candidate backgrounds)
2. Format event message with candidates and traits
3. Send to LLM with tool definitions
4. Execute tool loop (get_memories, background calls)
5. Extract speaker ID and dialogue text from LLM response
6. Clean response text and publish `dialogue.display`

#### Scenario: Single-turn dialogue generation
- **WHEN** a game event triggers dialogue
- **THEN** ONE LLM conversation turn SHALL handle speaker selection and dialogue generation
- **AND** the LLM SHALL use tools to fetch memory before generating dialogue

#### Scenario: Dialogue generated and displayed
- **WHEN** the LLM completes its turn with dialogue text
- **THEN** speaker_id and dialogue SHALL be extracted
- **AND** `dialogue.display` command SHALL be sent to Lua

### Memory Compression Trigger

The system MUST trigger compaction when any NPC's memory tier exceeds its cap. Compaction runs as background task using the fast model, separate from dialogue generation.

#### Scenario: Compaction triggered after event recording
- **WHEN** an event is recorded and a character's events tier exceeds cap 100
- **THEN** background compaction SHALL be triggered for that character
- **AND** compaction SHALL use `model_name_fast`, not the dialogue model

## REMOVED Requirements

### Speaker Selection Flow
**Reason**: Replaced by inline speaker selection in single LLM turn. The LLM picks the speaker as part of dialogue generation, using candidate traits from the pre-fetch batch.
**Migration**: Speaker selection happens within `ConversationManager` tool-calling turn. No separate `SpeakerSelector` class or LLM call.

### Memory Context Fetching
**Reason**: Replaced by tool-based memory access. The LLM calls `get_memories` tool during its turn instead of Python pre-fetching full memory context.
**Migration**: Memory is fetched via `get_memories` tool call during the LLM turn. Python translates and returns structured tiers.

### Memory Compression Trigger
**Reason**: The old 12-event threshold compression with `memory.update` command is replaced by four-tier compaction cascade with `state.mutate.batch`.
**Migration**: See `compaction-cascade` spec.

### Speaker Selection Prompt Builder
**Reason**: `create_pick_speaker_prompt()` is removed. Speaker selection is inline.
**Migration**: Candidate traits are included in the event message.

### Narrative Update Prompt Builder
**Reason**: `create_update_narrative_prompt()` is removed. Compaction uses its own prompt format.
**Migration**: See `compaction-cascade` spec for compaction prompt requirements.

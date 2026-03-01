## MODIFIED Requirements

### Text Lookup

The system MUST provide `resolve_faction_name(faction_id)` and `resolve_location_name(location_id)` for translating technical identifiers to human-readable text. These are used when constructing tool responses (translating Lua's technical fields for the LLM).

`resolve_personality()` and `resolve_backstory()` are retained for existing code paths but are no longer used by the dialogue prompt builder (backgrounds are now structured `Background` objects, not ID-resolved text).

#### Scenario: Resolve faction ID to display name
- **WHEN** resolve_faction_name("dolg") is called
- **THEN** returns "Duty"

#### Scenario: Resolve location ID to display name
- **WHEN** resolve_location_name("l01_escape") is called
- **THEN** returns "Cordon"

#### Scenario: Unknown location returns ID itself
- **WHEN** resolve_location_name("unknown_level") is called
- **THEN** returns "unknown_level"

## REMOVED Requirements

### Dialogue Prompt Builder
**Reason**: `create_dialogue_request_prompt()` is replaced by the ConversationManager's event message formatting and tool-based memory access. There is no longer a separate prompt builder function for dialogue.
**Migration**: Event formatting is handled by `ConversationManager`. World context and memory are fetched via pre-fetch batch and tools respectively.

### Query Current Scene JIT
**Reason**: Scene context is now fetched in the pre-fetch batch before the event message, not during prompt building.
**Migration**: Pre-fetch batch includes `query.world` — see `tool-based-dialogue` spec.

### Include World Context Section
**Reason**: World context is included in the event message directly, not as a separate prompt section.
**Migration**: Event message formatting includes location, weather, time.

### Speaker Selection Prompt Builder
**Reason**: `create_pick_speaker_prompt()` is removed entirely. Speaker selection is inline.
**Migration**: Candidate list with traits is part of the event message.

### Memory Compression Prompt Builder
**Reason**: `create_compress_memories_prompt()` is replaced by compaction-cascade prompts.
**Migration**: See `compaction-cascade` spec.

### Narrative Update Prompt Builder
**Reason**: `create_update_narrative_prompt()` is removed. No single narrative to update.
**Migration**: See `compaction-cascade` spec for tier-to-tier compaction prompts.

### Disguise awareness instructions in dialogue prompt
**Reason**: Preserved in spirit but moved to ConversationManager's system prompt. Disguise detection is based on Character data, not rendered event text.
**Migration**: The ConversationManager system prompt includes disguise awareness rules. Character data includes `visual_faction` when disguised.

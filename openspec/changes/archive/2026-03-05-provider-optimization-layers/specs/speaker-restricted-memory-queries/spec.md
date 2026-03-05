# Speaker-Restricted Memory Queries

## Overview

The `get_memories` tool is restricted to single-character queries (not batch-enabled) and should only be called AFTER the LLM has chosen a speaker. System prompt instructs the LLM to use backgrounds for speaker selection, then fetch memories only for the chosen speaker. This reduces expensive memory queries from N candidates to 1 speaker.

## Requirements

### MUST

- **M1**: `get_memories` tool schema MUST accept singular `character_id: str` (NOT array)
- **M2**: `get_memories` tool schema MUST make `tiers` parameter optional (if omitted, return all tiers)
- **M3**: Tool description MUST state: "Retrieve memories for THE CHOSEN SPEAKER ONLY. Do NOT use for candidate evaluation—use backgrounds instead."
- **M4**: System prompt MUST include tool usage workflow instructions (see example below)
- **M5**: Handler MUST default `tiers` to all four tiers when parameter is omitted: `["events", "summaries", "digests", "cores"]`
- **M6**: Batch queries MUST be rejected if attempted (schema prevents it, but handler should also validate)

### SHOULD

- **S1**: System prompt SHOULD clearly delineate workflow steps: evaluate candidates → choose speaker → fetch memories → generate dialogue
- **S2**: Tool usage instructions SHOULD emphasize cost/efficiency rationale ("Memories are expensive; use backgrounds for speaker selection")
- **S3**: Handler SHOULD log memory queries at INFO level: "Fetching memories for speaker {char_id} (tiers: {tiers})"

### MAY

- **M1**: Implementation MAY add usage tracking metrics (memory queries per event, tiers requested)
- **M2**: Implementation MAY warn if LLM calls `get_memories` before any `background` calls (indicates workflow violation)

## Non-Requirements

- ❌ Enforcement via code (preventing LLM from calling memories early) — system prompt guidance only
- ❌ Automatic tier selection based on dialogue context
- ❌ Caching of memory query results within a single event

## Validation

### Unit Test Scenarios

1. **Singular character_id**: Call `get_memories(character_id="123")` → returns all tiers
2. **Optional tiers default**: Call `get_memories(character_id="123")` without tiers → returns all 4 tiers
3. **Explicit tiers**: Call `get_memories(character_id="123", tiers=["events", "summaries"])` → returns only specified tiers
4. **Batch rejection**: Schema prevents `character_id: list` (type mismatch)

### Integration Test Scenarios

1. **End-to-end speaker selection flow**: 
   - LLM receives 5 candidates in event message
   - LLM calls `background(character_ids=["1","2","3","4","5"])`
   - LLM chooses speaker "3"
   - LLM calls `get_memories(character_id="3")`
   - LLM generates dialogue for speaker "3"
   - Total tool calls: 2 (not 6)

### Acceptance Criteria

- Tool execution count for typical event: 1-3 (background batch + 1 memory + optional char_info)
- No memory queries for candidates who didn't speak
- LLM follows workflow >95% of time (backgrounds before memories)

## Edge Cases

1. **LLM calls memories before backgrounds**: Still works (not blocked), but sub-optimal
2. **LLM calls memories for multiple candidates sequentially**: Each call is valid, but inefficient (system prompt should prevent this)
3. **Invalid character_id**: Handler returns empty dict or error (same as current behavior)

## Dependencies

- `multi-npc-tool-batching`: Provides batch background queries for speaker selection

## Related Specs

- `multi-npc-tool-batching`: Background tool supports batching; memory tool does not

## System Prompt Example

```text
**Tool Usage Rules:**
1. **background(character_ids)**: Use this to evaluate ALL candidates before choosing a speaker
   - You can fetch backgrounds for multiple characters at once
   - Example: background(character_ids=["0", "npc_123", "npc_456"])
   
2. **get_memories(character_id, tiers)**: ONLY use AFTER choosing the speaker
   - You can ONLY fetch memories for the character you've decided will speak
   - Do NOT fetch memories for candidates you're evaluating
   - Memories are expensive; use backgrounds for speaker selection
   - The `tiers` parameter is optional; omit it to fetch all memory tiers
   
3. **Workflow:**
   a. Read event context + candidate list
   b. Fetch backgrounds for candidates (if needed) via background(character_ids=[...])
   c. Choose speaker based on faction, personality, background
   d. Fetch memories ONLY for chosen speaker via get_memories(character_id=...)
   e. Generate dialogue for that speaker
```

## Tool Schema Example

```json
{
  "type": "function",
  "function": {
    "name": "get_memories",
    "description": "Retrieve memories for THE CHOSEN SPEAKER ONLY. Do NOT use for candidate evaluation—use backgrounds instead.",
    "parameters": {
      "type": "object",
      "properties": {
        "character_id": {
          "type": "string",
          "description": "The character ID of the speaker you've chosen"
        },
        "tiers": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["events", "summaries", "digests", "cores"]
          },
          "description": "Which memory tiers to retrieve. If omitted, returns all tiers."
        }
      },
      "required": ["character_id"]
    }
  }
}
```

## Metrics

- **Tool usage patterns**: Track % of events where memories are called before/after backgrounds
- **Query count**: Average memory queries per event (target: ≤1)
- **Tier usage**: Which tiers are most commonly requested (if explicit)

# Multi-NPC Tool Batching

## Overview

The `background` and `get_character_info` tools accept arrays of character IDs and return dict results, enabling batch queries for multiple NPCs in a single tool execution. This reduces tool call count during speaker selection (fetch backgrounds for all 5 candidates in one call vs. 5 separate calls).

## Requirements

### MUST

- **M1**: `background` tool schema MUST accept `character_ids: list[str]` parameter (was singular `character_id: str`)
- **M2**: `get_character_info` tool schema MUST accept `character_ids: list[str]` parameter
- **M3**: Both tools MUST enforce max batch size of 10 NPCs (return error if len(character_ids) > 10)
- **M4**: Both tools MUST return `dict[str, Any]` where keys are character IDs and values are the query results
- **M5**: `background` tool MUST support batch queries for `action="read"` only; write/update actions MUST reject multi-character requests
- **M6**: Handlers MUST accept both singular `str` and `list[str]` for backward compatibility (normalize to list internally)
- **M7**: Batch queries MUST use `BatchQuery` to compose multiple sub-queries into one WebSocket roundtrip
- **M8**: Error responses MUST be included in result dict (e.g., `{"char1": {...}, "char2": {"error": "not found"}}`)

### SHOULD

- **S1**: Tool description SHOULD clearly state batch capability (e.g., "Supports batch reads for up to 10 characters")
- **S2**: Handler SHOULD log batch size at DEBUG level: "background batch query for {N} characters"

### MAY

- **M1**: Implementation MAY increase batch size limit above 10 if performance testing shows it's safe
- **M2**: Implementation MAY add batch support for `background` write/update actions in future iterations

## Non-Requirements

- ❌ `get_memories` tool batching (explicitly excluded; speaker-only via separate spec)
- ❌ Automatic batching of sequential single-char calls (LLM must explicitly use batch parameter)
- ❌ Batch size auto-tuning based on network latency

## Validation

### Unit Test Scenarios

1. **Batch background read**: Call `background(character_ids=["1", "2", "3"], action="read")` → returns `{"1": {...}, "2": {...}, "3": {...}}`
2. **Single-char backward compat**: Call `background(character_ids="1", action="read")` → works (normalized to list)
3. **Batch size limit**: Call with 15 IDs → returns `{"error": "Max 10 characters per batch"}`
4. **Write action batch rejection**: Call `background(character_ids=["1", "2"], action="write", content={...})` → returns error
5. **Error propagation**: Call with one invalid ID → `{"valid_id": {...}, "invalid_id": {"error": "not found"}}`

### Integration Test Scenarios

1. **End-to-end batch query**: `ConversationManager` calls `_handle_background(["1", "2", "3"], "read")` → single `state.query.batch` WS message sent → dict response returned
2. **Batch vs. sequential comparison**: Time 5 sequential calls vs. 1 batch call → batch is significantly faster

### Acceptance Criteria

- LLM can fetch backgrounds for all candidates in one tool call
- Tool execution count reduced from 5 to 1 for typical 5-candidate scenario
- No regressions for existing single-character tool calls

## Edge Cases

1. **Empty character_ids list**: Return empty dict `{}`
2. **Duplicate IDs**: De-duplicate before querying (e.g., `["1", "1", "2"]` → query `["1", "2"]`)
3. **Mixed valid/invalid IDs**: Partial success (valid IDs return data, invalid IDs return errors in same dict)

## Dependencies

- None (extends existing tools)

## Related Specs

- `speaker-restricted-memory-queries`: Defines which tools support batching (backgrounds yes, memories no)

## Tool Schema Examples

### Background Tool (Batch-Enabled)

```json
{
  "type": "function",
  "function": {
    "name": "background",
    "description": "Read, write, or update background information. Supports batch reads for up to 10 characters.",
    "parameters": {
      "type": "object",
      "properties": {
        "character_ids": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Character IDs to query (max 10 per call)"
        },
        "action": {
          "type": "string",
          "enum": ["read", "write", "update"]
        }
      },
      "required": ["character_ids", "action"]
    }
  }
}
```

### Get Character Info Tool (Batch-Enabled)

```json
{
  "type": "function",
  "function": {
    "name": "get_character_info",
    "description": "Get detailed info about characters. Supports batch queries for up to 10 characters.",
    "parameters": {
      "type": "object",
      "properties": {
        "character_ids": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Character IDs to query (max 10 per call)"
        }
      },
      "required": ["character_ids"]
    }
  }
}
```

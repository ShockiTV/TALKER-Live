# Memory Compression System

## Overview

The Memory Compression System provides NPCs with persistent, scalable long-term memory. It uses a three-tier architecture that balances detail for recent events with summarization for older events, preventing context overflow while maintaining narrative continuity.

## Architecture

### Three-Tier Memory System

```
┌─────────────────────────────────────────────────────────────┐
│                    RECENT EVENTS (Tier 1)                   │
│         Raw events from event_store (last ~12 events)       │
│              Full detail, typed event structure             │
├─────────────────────────────────────────────────────────────┤
│                  MID-TERM MEMORY (Tier 2)                   │
│        Auto-compressed summary of previous 12 events        │
│               ~900 character paragraph                      │
├─────────────────────────────────────────────────────────────┤
│                 LONG-TERM MEMORY (Tier 3)                   │
│         Persistent narrative, max 6400 characters           │
│        Updated incrementally via LLM consolidation          │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Events Witnessed → event_store → memory_store.get_new_events()
                                        ↓
                               Check COMPRESSION_THRESHOLD (12)
                                        ↓
                          [< 12: Use as recent events]
                          [≥ 12: Trigger compression]
                                        ↓
                              Python Service (LLM)
                                        ↓
                              memory.update command
                                        ↓
                          memory_store.update_narrative()
```

## Data Structures

### Lua (memory_store.lua)

```lua
-- Per-character memory structure
narrative_memories[character_id] = {
    narrative = "string",           -- Long-term narrative text (max ~6400 chars)
    last_update_time_ms = number,   -- Timestamp of newest compressed event
}

-- Memory context returned for dialogue generation
{
    narrative = "string|nil",       -- Existing narrative or nil
    last_update_time_ms = number,   -- For time gap calculation
    new_events = Event[],           -- Events since last compression
}
```

### Python (MemoryContext model)

```python
@dataclass
class MemoryContext:
    narrative: Optional[str]        # Existing long-term narrative
    last_update_time_ms: int        # Timestamp cursor
    new_events: list[Event]         # Uncompressed events
```

## Compression Trigger

### Threshold

- **COMPRESSION_THRESHOLD = 12** events
- Defined in both `memory_store.lua` and `dialogue/generator.py`
- When `len(new_events) >= 12`, compression is triggered

### Trigger Points

1. **During dialogue generation** (`DialogueGenerator._generate_dialogue_for_speaker`)
   - Checks memory context before generating dialogue
   - Spawns compression as background task (non-blocking)

2. **On save load** (migration path)
   - If saved data exceeds threshold, marks for immediate compression

## Compression Process

### Step 1: Memory Context Query

Python requests memory context from Lua via ZMQ state query:

```python
memory_ctx = await self.state.query_memories(speaker_id)
# Returns: { narrative, last_update_time_ms, new_events }
```

### Step 2: Threshold Check

```python
if len(memory_ctx.new_events) < COMPRESSION_THRESHOLD:
    return  # No compression needed
```

### Step 3: Prompt Selection

**Bootstrap (no existing narrative):**
- Use `create_compress_memories_prompt()`
- Output: Single ~900 char paragraph summarizing all events

**Update (existing narrative):**
- Use `create_update_narrative_prompt()`
- Merges new events into existing narrative
- Handles overlap detection between narrative end and event start

### Step 4: Time Gap Injection

Before building prompts, `inject_time_gaps()` is called:
- Compares consecutive event timestamps
- If gap exceeds `time_gap_hours` (default: 12 hours), injects GAP event
- GAP events help LLM establish timeline transitions

```python
sorted_events = inject_time_gaps(events, last_update_time_ms=last_update_time_ms)
```

### Step 5: LLM Call

```python
response = await self.llm.complete(
    messages,
    LLMOptions(temperature=0.3, max_tokens=2000, timeout=self.llm_timeout)
)
new_narrative = response.strip()
```

### Step 6: Publish Update

```python
await self.publisher.publish("memory.update", {
    "character_id": speaker_id,
    "narrative": new_narrative,
    "last_event_time_ms": newest_time,  # Moves the cursor forward
})
```

### Step 7: Lua Handler

```lua
-- talker_zmq_command_handlers.script
memory_store:update_narrative(character_id, narrative, last_event_time_ms)
```

## Prompt Specifications

### Compress Memories Prompt

**Purpose:** Bootstrap - convert raw events into initial mid-term memory

**Constraints:**
- Output: Single continuous paragraph
- Max: 900 characters
- Perspective: Third person, neutral
- Style: Dry biography/history textbook
- Chronology: Preserved exactly

**Filtering:**
- Junk events (artifacts, anomalies, reloads, weapon jams) excluded
- Remove reputation and weapon information

### Update Narrative Prompt

**Purpose:** Incrementally update existing long-term memory with new events

**Constraints:**
- Output: Max 6400 characters
- Must detect and merge overlapping content
- No conclusions or summaries at the end
- Third person perspective
- Factual, no hallucination

**Length Management:**
- If input narrative > 5500 chars: Edit/condense FIRST
- If output > 6400 chars: Re-examine and aggressively compress

## Concurrency Control

```python
# Per-character locks prevent concurrent compression
self._memory_locks: dict[str, asyncio.Lock] = {}

async def _maybe_compress_memory(self, speaker_id, memory_ctx):
    lock = self._get_memory_lock(speaker_id)
    if lock.locked():
        return  # Already in progress
    async with lock:
        await self._compress_memory(speaker_id, memory_ctx)
```

## Time Gap Events

### Structure

```python
Event(
    type="GAP",
    context={"hours": 15, "message": "TIME GAP: Approximately 15 hours have passed since the last event."},
    game_time_ms=<timestamp>,
    flags={},
)
```

### Injection Logic

```python
def inject_time_gaps(events, last_update_time_ms=0, time_gap_hours=12):
    # Compare consecutive event timestamps
    # If delta > time_gap_hours * MS_PER_HOUR, inject GAP event
    # Also checks gap from last_update_time_ms to first event
```

### Default Threshold

- `DEFAULT_TIME_GAP_HOURS = 12` (configurable via MCM `time_gap` field)
- `MS_PER_HOUR = 3,600,000`

## ZMQ Commands

### memory.update (Python → Lua)

```json
{
    "character_id": "12345",
    "narrative": "Updated narrative text...",
    "last_event_time_ms": 1706620800000
}
```

### state.query (memories)

Request (Python → Lua):
```json
{
    "request_id": "uuid",
    "query_type": "memories",
    "character_id": "12345"
}
```

Response (Lua → Python):
```json
{
    "request_id": "uuid",
    "data": {
        "narrative": "Existing narrative...",
        "last_update_time_ms": 1706620000000,
        "new_events": [...]
    }
}
```

## Persistence

### Save Format

```lua
-- Saved to game state via talker_game_persistence
saved_data.narrative_memories = {
    ["12345"] = {
        narrative = "Long-term memory text...",
        last_update_time_ms = 1706620800000,
    },
    -- ...more characters
}
```

### Migration (Legacy Format)

Old format stored individual memory entries as arrays. Migration logic:
- If entry is array format → migrate to new structure
- If entry count ≥ threshold → trigger immediate compression
- If entry count < threshold → concatenate into narrative

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `COMPRESSION_THRESHOLD` | 12 | Events before compression triggers |
| `time_gap` | 12 | Hours threshold for GAP event injection |
| `llm_timeout` | 60 | Seconds to wait for LLM response |

## Error Handling

- LLM failures logged, compression retried on next dialogue generation
- Empty narrative responses ignored (no update)
- Per-character locks prevent race conditions
- Background task execution prevents blocking dialogue generation

## Files

### Lua
- `bin/lua/domain/repo/memory_store.lua` - Memory storage and retrieval
- `gamedata/scripts/talker_zmq_command_handlers.script` - memory.update handler

### Python
- `talker_service/src/talker_service/dialogue/generator.py` - Compression orchestration
- `talker_service/src/talker_service/prompts/builder.py` - Prompt construction
- `talker_service/src/talker_service/prompts/helpers.py` - Time gap injection
- `talker_service/src/talker_service/state/client.py` - State queries

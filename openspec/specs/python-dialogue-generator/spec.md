# python-dialogue-generator

## Overview

Python orchestrator that handles the full dialogue generation flow: event reception → speaker selection → memory management → prompt building → LLM call → display command.

## Requirements

### ADDED: Dialogue Generator Service

The system MUST provide `DialogueGenerator` class with:
- `async generate(event, is_important)` method as main entry point
- Access to state query client for fetching Lua state
- Access to LLM client for AI completions
- Access to prompt builder for prompt construction
- Publisher for sending display commands

### ADDED: Speaker Selection Flow

The system MUST implement speaker selection that:
- Receives witnesses from event data
- Filters speakers by cooldown (3 second default)
- If single speaker available, selects directly
- If multiple speakers, calls LLM with pick_speaker prompt
- Validates selected speaker ID against witness list
- Sets speaker cooldown after selection

### ADDED: Memory Context Fetching

The system MUST fetch memory context by:
- Sending `memories.get` query to Lua with character_id
- Receiving narrative + new_events in response
- Handling query timeout (30 second default)
- Returning empty context on failure (graceful degradation)

### ADDED: Memory Compression Trigger

The system MUST trigger memory compression when:
- New events count exceeds COMPRESSION_THRESHOLD (12)
- Acquires lock to prevent concurrent updates for same character
- Calls LLM with compression/update_narrative prompts
- Sends `memory.update` command to Lua with new narrative
- Releases lock after completion

### ADDED: Dialogue Request Flow

The system MUST request dialogue by:
- Building dialogue prompt with speaker + memory context
- Calling LLM for completion
- Cleaning/improving response text
- Sending `dialogue.display` command to Lua

### ADDED: Request-Response Correlation

The system MUST use correlation IDs:
- Generate unique request_id for each dialogue flow
- Include request_id in all queries and commands
- Track in-flight requests for timeout handling
- Log request_id for debugging

### ADDED: Error Handling

The system MUST handle errors by:
- Catching LLM timeouts, returning no dialogue
- Catching query timeouts, using empty context
- Logging errors with request_id
- Never crashing service on individual dialogue failure

## Scenarios

#### Full dialogue generation flow

WHEN a game.event is received with is_important=true
THEN speaker selection runs (filters cooldowns, picks via LLM if needed)
AND memory context is fetched for selected speaker
AND dialogue prompt is built and sent to LLM
AND dialogue.display command is sent to Lua with generated text

#### Single available speaker (fast path)

WHEN event has only one witness not on cooldown
THEN speaker is selected without LLM call
AND dialogue generation proceeds directly

#### Memory compression triggered

WHEN new_events count >= 12 for a character
THEN compression lock is acquired
AND LLM generates compressed summary
AND memory.update command is sent to Lua
AND lock is released

#### LLM timeout during dialogue

WHEN LLM call exceeds 60 seconds
THEN timeout error is caught
AND no dialogue.display command is sent
AND error is logged with request_id

#### Concurrent compression prevented

WHEN compression is already in progress for character X
THEN second compression request for X is skipped
AND log indicates "lock already held"

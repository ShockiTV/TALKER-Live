# python-prompt-builder

## Overview

Python port of `bin/lua/infra/AI/prompt_builder.lua` that constructs prompts for dialogue generation, speaker selection, and memory compression.

## Requirements

### ADDED: Dialogue Prompt Builder

The system MUST provide `create_dialogue_request_prompt(speaker, memory_context)` that:
- Generates prompt matching Lua's `create_dialogue_request_prompt` output structure
- Includes all system message sections (CORE DIRECTIVE, FORMAT, FORBIDDEN, etc.)
- Injects character anchor with name, rank, faction, personality, backstory
- Injects memory context (narrative + new events)
- Injects scene context (location, nearby characters, disguise)
- Returns list of message dicts with role/content

### ADDED: Speaker Selection Prompt Builder

The system MUST provide `create_pick_speaker_prompt(events, witnesses, mid_term_memory)` that:
- Generates prompt matching Lua's `create_pick_speaker_prompt` output
- Describes witnesses with IDs in format `[ID: N] description`
- Includes up to 8 most recent events
- Instructs model to return JSON with speaker ID

### ADDED: Memory Compression Prompt Builder

The system MUST provide `create_compress_memories_prompt(events, speaker)` that:
- Generates prompt matching Lua's `create_compress_memories_prompt` output
- Filters junk events (artifacts, anomalies, reloads)
- Instructs 900 character limit for output
- Uses third-person perspective

### ADDED: Narrative Update Prompt Builder

The system MUST provide `create_update_narrative_prompt(speaker, narrative, events)` that:
- Generates prompt matching Lua's `create_update_narrative_prompt` output
- Handles bootstrap case (empty narrative)
- Enforces 6400 character output limit
- Includes retention priorities (relationships, character development)

### ADDED: Message Model

The system MUST define `Message` dataclass with:
- `role: str` (system, user, assistant)
- `content: str`
- Serialization to dict format for LLM APIs

### ADDED: Character Context Helpers

The system MUST provide helper functions:
- `describe_character(char)` - format character for prompt
- `describe_event(event)` - format event for prompt
- `get_faction_description(faction)` - faction lore text
- `get_faction_relations(faction, mentioned)` - relation context

## Scenarios

#### Build dialogue prompt with full context

WHEN create_dialogue_request_prompt is called with speaker and memory_context
THEN the result contains CHARACTER ANCHOR section with speaker details
AND contains LONG-TERM MEMORIES section if narrative exists
AND contains CURRENT EVENTS section with recent events
AND all messages have role and content fields

#### Build speaker selection prompt

WHEN create_pick_speaker_prompt is called with events and witnesses
THEN the result contains CANDIDATES section with witness IDs
AND contains EVENTS section with up to 8 events
AND instructs JSON output format with id field

#### Build compression prompt filtering junk

WHEN create_compress_memories_prompt is called with events including artifacts
THEN artifact events are excluded from the prompt
AND non-junk events appear in chronological order

#### Handle empty narrative (bootstrap)

WHEN create_update_narrative_prompt is called with empty narrative
THEN the prompt uses bootstrapping instructions
AND does not reference CURRENT_MEMORY section

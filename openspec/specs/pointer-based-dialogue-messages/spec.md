# pointer-based-dialogue-messages

## Purpose

Picker and dialogue user messages become lightweight pointers that reference system-message content by event timestamp and character ID, instead of inlining full event descriptions and backgrounds.

## Requirements

### Requirement: Picker user message is a pointer

#### Scenario: Building the picker prompt for an event

WHEN the picker step assembles its user message  
THEN the message references the event by timestamp: `"Pick speaker for EVT:{ts}"`  
AND lists candidate character IDs (not full profiles): `"Candidates: {id1}, {id2}, ..."`  
AND does NOT inline event text or candidate backgrounds  
AND relies on the already-injected system messages for context

---

### Requirement: Dialogue user message is a pointer with personal narrative

#### Scenario: Building the dialogue prompt for the chosen speaker

WHEN the dialogue step assembles its user message for character `{id}`  
THEN the message includes:  
- Reference to the triggering event: `EVT:{ts}`  
- Character ID  
- Personal narrative memories (summaries/digests/cores text — character's subjective perspective)  
- Instruction to respond in character  
AND does NOT inline the event description (already a system message)  
AND does NOT inline the background (already a system message)

#### Scenario: Speaker has no personal narrative memories yet

WHEN the speaker has no compacted memories  
THEN the user message omits the personal memories section  
AND still references the event and character ID

---

### Requirement: All factual context comes from system messages

#### Scenario: LLM processes the full message array

WHEN the LLM receives the conversation history  
THEN event facts are available from `EVT:` system messages  
AND character backgrounds are available from `BG:` system messages  
AND character memories are available from `MEM:` system messages  
AND the user message only adds the reaction instruction and personal perspective

# prompt-deduplication-tracker

**Status:** draft  
**Change:** deduplicated-prompt-architecture

A `DeduplicationTracker` class that maintains three injection-state sets — events, backgrounds, and memories — to prevent duplicate system messages in the LLM conversation window. Supports full rebuild from surviving messages after pruning.

---

### Requirement: Tracker maintains three independent dedup sets

#### Scenario: Checking if an event is already injected

WHEN `is_event_injected(ts: int)` is called  
AND the event timestamp exists in `_injected_event_ts`  
THEN it returns True  
AND the event is NOT re-injected as a system message

#### Scenario: Checking if a background is already injected

WHEN `is_bg_injected(char_id: str)` is called  
AND the character ID exists in `_injected_bg_ids`  
THEN it returns True

#### Scenario: Checking if a memory is already injected

WHEN `is_mem_injected(char_id: str, start_ts: int)` is called  
AND the tuple `(char_id, start_ts)` exists in `_injected_mem_ids`  
THEN it returns True

---

### Requirement: Tracker records newly injected items

#### Scenario: Recording an event injection

WHEN `mark_event(ts: int)` is called  
THEN the timestamp is added to `_injected_event_ts`  
AND subsequent `is_event_injected(ts)` returns True

#### Scenario: Recording a background injection

WHEN `mark_bg(char_id: str)` is called  
THEN the character ID is added to `_injected_bg_ids`

#### Scenario: Recording a memory injection

WHEN `mark_mem(char_id: str, start_ts: int)` is called  
THEN the tuple is added to `_injected_mem_ids`

---

### Requirement: Tracker rebuilds state from surviving messages

#### Scenario: Messages are pruned and tracker must resync

WHEN `rebuild_from_messages(messages: list[Message])` is called  
THEN all three sets are cleared  
AND each system message is scanned by tag prefix:  
- `EVT:{ts}` → add ts to `_injected_event_ts`  
- `BG:{char_id}` → add char_id to `_injected_bg_ids`  
- `MEM:{char_id}:{start_ts}` → add (char_id, start_ts) to `_injected_mem_ids`  
AND items no longer in messages are automatically excluded

#### Scenario: Non-system messages are ignored during rebuild

WHEN `rebuild_from_messages()` encounters user or assistant messages  
THEN they are skipped without error

---

### Requirement: Tracker is instantiated per conversation

#### Scenario: New ConversationManager is created

WHEN a `ConversationManager` is constructed  
THEN it holds a single `DeduplicationTracker` instance  
AND all three sets start empty

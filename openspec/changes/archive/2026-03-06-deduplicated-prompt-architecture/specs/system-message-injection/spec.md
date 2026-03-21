# system-message-injection

**Status:** draft  
**Change:** deduplicated-prompt-architecture

Shared factual context — events, character backgrounds, and compacted memories — are injected as tagged `[system]` messages into the LLM conversation window. Each message has a prefix tag used as a dedup key. Messages persist across turns and are only re-injected if missing after pruning.

---

### Requirement: Events are injected as system messages with witness lists

#### Scenario: A new event arrives that is not yet in the messages

WHEN `handle_event()` processes an event  
AND the dedup tracker reports it is NOT injected  
THEN a system message is appended with content:  
`EVT:{game_time_ms} — {EVENT_TYPE}: {event_description}\nWitnesses: {name1}({id1}), {name2}({id2}), ...`  
AND the tracker marks the event timestamp as injected

#### Scenario: An event already exists in the messages

WHEN `handle_event()` processes an event  
AND the dedup tracker reports it IS already injected  
THEN no system message is added for that event

---

### Requirement: Backgrounds are injected as system messages

#### Scenario: A character's background is needed and not yet injected

WHEN a character is referenced (as picker candidate or dialogue speaker)  
AND the tracker reports their background is NOT injected  
THEN a system message is appended with content:  
`BG:{char_id} — {name} ({faction})\n{background_text}`  
AND the tracker marks the character ID as injected

#### Scenario: Background already present

WHEN a character's background is already injected  
THEN no additional system message is added

---

### Requirement: Compacted memories are injected as system messages

#### Scenario: A character's memory tiers need injection for dialogue

WHEN the dialogue step resolves the speaker  
AND the speaker has compacted memories (summaries/digests/cores)  
AND a memory item's (char_id, start_ts) is NOT in the tracker  
THEN a system message is appended per item:  
`MEM:{char_id}:{start_ts} — [{tier_label}] {narrative_text}`  
AND the tracker marks each (char_id, start_ts) as injected

#### Scenario: Memory item already present

WHEN a memory item is checked and already tracked  
THEN it is skipped

---

### Requirement: Event system messages persist through the picker step

#### Scenario: Picker selects a speaker

WHEN the picker user question and assistant response are removed after selection  
THEN event system messages injected before the picker remain in the conversation  
AND they are available for the dialogue generation step without re-injection

---

### Requirement: Tag format is strictly enforced

#### Scenario: System message is created

WHEN any tagged system message is appended  
THEN its content starts with exactly one of: `EVT:`, `BG:`, `MEM:`  
AND the tag and payload are separated by ` — ` (space-em-dash-space)  
AND the tag value matches the dedup key used by the tracker

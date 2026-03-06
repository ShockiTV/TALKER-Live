# two-step-dialogue-flow (Delta)

> **Change**: `cache-friendly-prompt-layout`
> **Operation**: MODIFIED

---

### MODIFIED: System prompt rebuilt every turn → static system prompt

**Was**: `_build_system_prompt()` called on every `handle_event()`, output written to `_messages[0]`, including world context (weather, time, location, inhabitants).

**Now**: `_messages[0]` is set once at construction time with static dialogue rules only. It SHALL NOT be modified during the session.

#### Scenario: System prompt set once

WHEN `ConversationManager` is constructed
THEN `_messages[0]` SHALL be set to static dialogue rules
AND `_build_system_prompt()` SHALL NOT be called on subsequent events

---

### MODIFIED: Picker step receives no witness events

**Was**: Picker step received all events from the event store.

**Now**: The picker step SHALL receive only the triggering event description (type, actor, victim, location) plus candidate character IDs. Witness events from the event store SHALL NOT be included in the picker prompt.

#### Scenario: Picker prompt content

WHEN `_run_speaker_picker()` is called
THEN the picker user message SHALL contain only the triggering event description and candidate IDs
AND it SHALL NOT include witness events from `event_store`

---

### MODIFIED: Dialogue step receives only speaker's events

**Was**: Dialogue step received all events from the event store.

**Now**: The dialogue step SHALL include only events where the chosen speaker is listed as a witness.

#### Scenario: Filtered events for dialogue

WHEN `_run_dialogue_generation()` is called with speaker S
AND the event store contains events E1 (witnesses: [S, X]) and E2 (witnesses: [Y, Z])
THEN only E1 SHALL be included in the dialogue prompt
AND E2 SHALL be excluded

---

### MODIFIED: Weather/time/location in per-turn instruction

**Was**: Weather, time-of-day, and location were part of the system prompt.

**Now**: Weather, time-of-day, and location SHALL be included in the per-turn user message (both picker and dialogue instructions).

#### Scenario: Event instruction includes world state

WHEN a picker or dialogue user message is built
THEN it SHALL include current weather, time-of-day, and player/event location
AND these values SHALL NOT appear in `_messages[0]` or `_messages[1]`

---

### ADDED: Context block updated before each event

WHEN `handle_event()` is called
THEN backgrounds for all candidates SHALL be added to the `ContextBlock` (if not already present)
AND memories for all candidates SHALL be added to the `ContextBlock` (if not already present)
AND `_messages[1]` SHALL be updated with `context_block.render_markdown()`
BEFORE the picker step runs

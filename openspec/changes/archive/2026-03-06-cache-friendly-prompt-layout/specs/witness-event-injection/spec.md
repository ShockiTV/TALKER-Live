# witness-event-injection (Delta)

> **Change**: `cache-friendly-prompt-layout`
> **Operation**: MODIFIED

---

### UNCHANGED: Event storage in event_store

Event storage, witness tracking, and the event store interface are NOT modified by this change. Events continue to be stored with witness lists as before.

---

### MODIFIED: Event injection is per-step filtered, not global

**Was**: All events from the event store were injected into the prompt for both picker and dialogue steps.

**Now**: Event injection SHALL be filtered per step:

#### Scenario: Picker step — no witness events

WHEN the picker step builds its prompt
THEN it SHALL include only the triggering event description
AND it SHALL NOT include any witness events from the event store

#### Scenario: Dialogue step — speaker-filtered events

WHEN the dialogue step builds its prompt for speaker S
THEN it SHALL query the event store for events where S is a witness
AND only those events SHALL be included in the dialogue instruction
AND events where S is NOT a witness SHALL be excluded

---

### MODIFIED: Events are ephemeral per-turn content

**Was**: Events were injected as persistent system messages tracked by `DeduplicationTracker._event_ids`.

**Now**: Events SHALL be included inline in the per-turn user message (Layer 4). They are NOT added to the `ContextBlock` and are NOT deduplicated across turns — each turn's instruction contains the relevant events for that turn's step.

#### Scenario: Events not in context block

WHEN events are rendered for a dialogue turn
THEN they SHALL appear in the user message at index 3+ (Layer 4)
AND they SHALL NOT appear in `_messages[1]` (the context block)

---

### ADDED: Speaker witness filter function

A helper function SHALL be provided to filter events by speaker witness status:

WHEN `filter_events_for_speaker(events, speaker_id)` is called
THEN it SHALL return only events where `speaker_id` is in the event's witness list

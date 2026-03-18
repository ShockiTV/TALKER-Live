# pointer-based-dialogue-messages (Delta)

> **Change**: `trigger-and-event-linking`
> **Operation**: MODIFIED

---

## MODIFIED Requirements

### Requirement: Picker user message is a pointer

The picker user message SHALL reference the triggering event by `[ts]` timestamp and include the full unified event list with witness annotations, instead of relying on separate system messages.

#### Scenario: Building the picker prompt for an event

- **WHEN** the picker step assembles its user message for triggering event with `ts=1709912345`
- **THEN** the message SHALL include a `**Recent events in area:**` section with all deduplicated candidate events in `[ts] TYPE — description (witnesses: ...)` format
- **AND** the message SHALL reference the triggering event as `React to event [1709912345].`
- **AND** the message SHALL list candidate IDs: `Candidates: {id1}, {id2}, ...`
- **AND** the event list SHALL be sorted by `ts` ascending

#### Scenario: Picker message does not inline event description separately

- **WHEN** the picker step assembles its user message
- **THEN** the triggering event SHALL appear only in the unified event list (identified by its `ts`)
- **AND** no separate inline event description block SHALL be present

---

### Requirement: Dialogue user message is a pointer with personal narrative

The dialogue user message SHALL reference the triggering event by `[ts]` and include the chosen speaker's filtered event list with witness annotations.

#### Scenario: Building the dialogue prompt for the chosen speaker

- **WHEN** the dialogue step assembles its user message for speaker "Echo" (ID: 12345) reacting to event `ts=1709912345`
- **THEN** the message SHALL include a `**Recent events witnessed by Echo:**` section with events filtered to those Echo witnessed
- **AND** each event line SHALL use `[ts] TYPE — description (witnesses: ...)` format
- **AND** the message SHALL reference the triggering event as `React to event [1709912345] as **Echo** (ID: 12345).`
- **AND** the message SHALL include personal narrative memories if available
- **AND** the message SHALL NOT inline the event description separately from the event list

#### Scenario: Speaker has no personal narrative memories yet

- **WHEN** the speaker has no compacted memories
- **THEN** the user message SHALL omit the personal memories section
- **AND** SHALL still reference the event by `[ts]` and include the event list

---

### Requirement: All factual context comes from system messages

#### Scenario: LLM processes the full message array

- **WHEN** the LLM receives the conversation history
- **THEN** character backgrounds SHALL be available from `BG:` system messages
- **AND** character memories SHALL be available from `MEM:` system messages
- **AND** event facts SHALL be available from the per-turn event list in the user message (not system messages)
- **AND** the user message adds the reaction instruction, event list, and personal perspective

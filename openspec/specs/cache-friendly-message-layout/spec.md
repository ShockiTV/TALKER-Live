# cache-friendly-message-layout

> **Status**: NEW capability introduced by `cache-friendly-prompt-layout`

Defines the four-layer message structure used for all LLM calls, optimised for prefix caching.

---

### Requirement: Four-layer message structure

Every LLM call assembled by `ConversationManager` SHALL use exactly this message layout:

| Index | Role | Content | Description |
|-------|------|---------|-------------|
| 0 | `system` | Static dialogue rules | Timeless NPC rules: tone, length, style. No weather, time, location, or character data. |
| 1 | `user` | Context block Markdown | Output of `ContextBlock.render_markdown()`. Contains all BG + MEM items. |
| 2 | `assistant` | `"Ready."` | Synthetic acknowledgement establishing turn alternation. |
| 3+ | `user`/`assistant` | Dialogue turns | Per-step instructions and LLM responses. |

#### Scenario: Message list for a fresh conversation

WHEN a new `ConversationManager` is constructed
THEN `_messages` SHALL contain exactly 3 messages: system (index 0), empty context user (index 1), assistant "Ready." (index 2)

#### Scenario: After adding context items

WHEN backgrounds or memories are added via the `ContextBlock`
THEN `_messages[1].content` SHALL be updated to `context_block.render_markdown()`
AND `_messages[0]` and `_messages[2]` SHALL NOT change

---

### Requirement: Static system prompt

The system message at index 0 SHALL contain only static dialogue rules that never change during a session. It MUST NOT include:
- Weather or time-of-day
- Player location or level name
- Character names, backgrounds, or faction standings
- Inhabitant lists
- Any data that changes between LLM calls

#### Scenario: System prompt content across multiple events

WHEN `handle_event()` is called multiple times within one session
THEN `_messages[0].content` SHALL be byte-identical across all calls

---

### Requirement: Weather, time, and location in per-turn instruction

Weather, time-of-day, and location information SHALL be included in the per-turn user message (Layer 4) that describes the triggering event.

#### Scenario: Dialogue instruction includes world state

WHEN a dialogue turn user message is built
THEN it SHALL include current weather description, time-of-day, and location name
AND these SHALL NOT appear in `_messages[0]` (system) or `_messages[1]` (context block)

---

### Requirement: Synthetic assistant acknowledgement

`_messages[2]` SHALL always be `Message(role="assistant", content="Ready.")`.

#### Scenario: Assistant ack never changes

WHEN any number of events are processed
THEN `_messages[2].content` SHALL remain `"Ready."`

---

### Requirement: Dialogue turns append after the ack

Dialogue turn messages (picker instructions, picker responses, dialogue instructions, dialogue responses) SHALL be appended starting at index 3.

#### Scenario: First event adds turn messages

WHEN the first event triggers dialogue generation
THEN the picker instruction SHALL be at index 3
AND the picker response at index 4
AND the dialogue instruction at index 5
AND the dialogue response at index 6

#### Scenario: Second event appends after first

WHEN a second event triggers dialogue
THEN its picker instruction SHALL be at index 7
AND so on, maintaining strict user/assistant alternation

---

### Requirement: Context update preserves prefix stability

WHEN new background or memory items are added between events
THEN only `_messages[1]` SHALL be modified
AND the modification SHALL be append-only (new Markdown lines at the end of existing content)
AND all other messages SHALL remain byte-identical

#### Scenario: Prefix cache efficiency

GIVEN `_messages[0]` is 150 tokens and `_messages[1]` is 900 tokens
WHEN a new BG adds 80 tokens to `_messages[1]`
THEN the first 1024 tokens of the serialized message array are unchanged
AND an OpenAI-style prefix cache SHALL hit on at least one 1024-token chunk

---

### Requirement: Picker messages are ephemeral

Picker instruction and response messages SHALL be included in the message list during the picker step but MUST be removed before the dialogue step.

#### Scenario: Picker messages cleaned up

WHEN the picker step completes and returns a speaker
THEN the picker instruction and response messages SHALL be removed from `_messages`
AND the dialogue instruction SHALL be appended at the position where the picker instruction was

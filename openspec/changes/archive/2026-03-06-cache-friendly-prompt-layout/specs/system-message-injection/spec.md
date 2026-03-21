# system-message-injection (Delta)

> **Change**: `cache-friendly-prompt-layout`
> **Operation**: MODIFIED

---

### REMOVED: Individual system messages for context injection

**Was**: Background and memory context were injected as additional `[system]` messages inserted into `_messages` with tags like `[Background: Name]` and `[Memory: Name @ts]`.

**Now**: All context injection uses the single `[user]` context block at `_messages[1]`. There SHALL be exactly one `[system]` message in the conversation (index 0, static rules).

#### Scenario: No additional system messages

WHEN any number of backgrounds and memories have been injected
THEN `_messages` SHALL contain exactly one message with `role="system"` at index 0
AND all context data SHALL be in `_messages[1]` with `role="user"`

---

### MODIFIED: Tag format replaced by Markdown headers

**Was**: System messages used tag format: `[Background: Name (Faction)]`, `[Memory: Name @ts]`.

**Now**: Context items use Markdown format in the user context block:
- Backgrounds: `## Name (Faction) [id:char_id]`
- Memories: `[TIER] Name [id:char_id] @ts: text`

#### Scenario: Background rendering

WHEN a background for character "Wolf" (faction "Loners", id "wolf_01") is rendered
THEN the context block SHALL contain:
```
## Wolf (Loners) [id:wolf_01]
Wolf's background text here.
```

---

### MODIFIED: Single system message for provider compatibility

**Was**: Multiple system messages could cause issues with Ollama, Gemini, and budget OpenRouter endpoints.

**Now**: Exactly one `[system]` message at index 0. All other messages use `[user]` or `[assistant]` roles. This SHALL be compatible with all LLM providers.

#### Scenario: Provider compatibility

WHEN the message list is serialized for any LLM provider
THEN only `_messages[0]` SHALL have `role="system"`
AND all subsequent messages SHALL alternate `user`/`assistant`

# prompt-deduplication-tracker (Delta)

> **Change**: `cache-friendly-prompt-layout`
> **Operation**: MODIFIED

---

### REMOVED: Standalone DeduplicationTracker class

**Was**: `DeduplicationTracker` maintained three separate sets (`_event_ids`, `_bg_ids`, `_mem_keys`) and was used by `ConversationManager` to check whether items had been injected as system messages.

**Now**: Deduplication responsibility is absorbed by `ContextBlock`. The `DeduplicationTracker` class SHALL be removed.

#### Scenario: No DeduplicationTracker import

WHEN `ConversationManager` is constructed
THEN it SHALL NOT instantiate a `DeduplicationTracker`
AND it SHALL use `ContextBlock.has_background()` and `ContextBlock.has_memory()` for dedup checks

---

### MODIFIED: Dedup sets move into ContextBlock

**Was**: `_bg_ids: set[str]` and `_mem_keys: set[tuple[str, int]]` lived in `DeduplicationTracker`.

**Now**: These sets SHALL live inside `ContextBlock` as `_bg_ids` and `_mem_keys`. The behaviour (O(1) lookup, add-returns-bool) SHALL be identical.

#### Scenario: Background dedup via ContextBlock

WHEN `context_block.add_background("wolf_01", ...)` is called twice
THEN the first call SHALL return `True` and add the item
AND the second call SHALL return `False` and not modify the block

---

### MODIFIED: Event dedup handled differently

**Was**: `DeduplicationTracker._event_ids` tracked which events had been injected as system messages.

**Now**: Events are NOT stored in the context block (they are per-turn ephemeral content in Layer 4). Event dedup is handled by the `event_store` itself — events are looked up fresh per step with filtering by speaker witness status.

#### Scenario: Events not tracked in context block

WHEN events are included in a dialogue turn
THEN they SHALL NOT be added to the `ContextBlock`
AND they SHALL NOT affect `_bg_ids` or `_mem_keys`

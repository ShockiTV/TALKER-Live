# context-block-builder

> **Status**: NEW capability introduced by `cache-friendly-prompt-layout`

Defines `ContextBlock`, the single append-only data structure that holds all background and memory items for a conversation, with set-based dedup and Markdown rendering.

---

### Requirement: ContextBlock stores items in insertion order

The `ContextBlock` class SHALL maintain an ordered list of typed items (`ContextItem` dataclasses). Each item is either a `BackgroundItem` or a `MemoryItem`.

#### Scenario: Adding a background item

WHEN `add_background(char_id, name, faction, text)` is called
AND `char_id` is NOT already in the background set
THEN a `BackgroundItem` SHALL be appended to `_items`
AND `char_id` SHALL be added to `_bg_ids`
AND the method SHALL return `True`

#### Scenario: Duplicate background is rejected

WHEN `add_background(char_id, name, faction, text)` is called
AND `char_id` IS already in `_bg_ids`
THEN `_items` SHALL NOT be modified
AND the method SHALL return `False`

---

### Requirement: Memory items are tracked by (char_id, ts) pairs

#### Scenario: Adding a memory item

WHEN `add_memory(char_id, name, ts, tier, text)` is called
AND `(char_id, ts)` is NOT already in the memory set
THEN a `MemoryItem` SHALL be appended to `_items`
AND `(char_id, ts)` SHALL be added to `_mem_keys`
AND the method SHALL return `True`

#### Scenario: Duplicate memory is rejected

WHEN `add_memory(char_id, name, ts, tier, text)` is called
AND `(char_id, ts)` IS already in `_mem_keys`
THEN `_items` SHALL NOT be modified
AND the method SHALL return `False`

---

### Requirement: Dedup query methods

The `ContextBlock` SHALL expose two query methods:

- `has_background(char_id) → bool` — returns `True` if `char_id` in `_bg_ids`
- `has_memory(char_id, ts) → bool` — returns `True` if `(char_id, ts)` in `_mem_keys`

These methods MUST be O(1) set lookups.

---

### Requirement: Markdown rendering preserves insertion order

#### Scenario: Rendering mixed items

WHEN `render_markdown()` is called on a `ContextBlock` containing backgrounds and memories in insertion order [BG-A, MEM-A-1, BG-B, MEM-B-1, MEM-A-2]
THEN the output SHALL contain items in that exact order
AND background items SHALL render as:
```
## Name (Faction) [id:char_id]
background text
```
AND memory items SHALL render as:
```
[TIER] Name [id:char_id] @ts: memory text
```

#### Scenario: Empty block renders empty string

WHEN `render_markdown()` is called on an empty `ContextBlock`
THEN the output SHALL be an empty string

---

### Requirement: Append-only property for cache stability

The `ContextBlock` SHALL NOT support removal or reordering of individual items. The only way to produce a shorter block is to construct a new `ContextBlock` instance and re-add desired items.

#### Scenario: Compaction rebuild

WHEN memory compaction produces new compressed summaries
THEN the caller MUST create a new `ContextBlock`
AND re-add all backgrounds and new memory items
AND replace the old context block entirely

---

### Requirement: Missing items query

The `ContextBlock` SHALL expose a `missing(char_ids: list[str]) → list[str]` method that returns character IDs from the input list that do NOT have a background entry.

#### Scenario: Some characters missing backgrounds

WHEN `missing(["a", "b", "c"])` is called
AND `_bg_ids` contains `{"a", "c"}`
THEN the method SHALL return `["b"]`

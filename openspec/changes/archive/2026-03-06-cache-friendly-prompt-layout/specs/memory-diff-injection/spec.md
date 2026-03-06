# memory-diff-injection (Delta)

> **Change**: `cache-friendly-prompt-layout`
> **Operation**: MODIFIED

---

### MODIFIED: Memory injection moves from system messages to ContextBlock

**Was**: New or updated memories were injected as individual `[system]` messages with tags like `[Memory: Name @ts]`, with the `DeduplicationTracker` preventing duplicates.

**Now**: Memories SHALL be added via `context_block.add_memory(char_id, name, ts, tier, text)`. The `ContextBlock` handles dedup internally via `_mem_keys`. Rendered output appears in `_messages[1]` as Markdown.

#### Scenario: Memory injection via ContextBlock

WHEN a new memory for character "wolf_01" at ts=1000 is available
THEN `context_block.add_memory("wolf_01", "Wolf", 1000, "recent", text)` SHALL be called
AND the memory SHALL appear in the Markdown output of `render_markdown()`

---

### MODIFIED: Diff detection uses ContextBlock.has_memory()

**Was**: Diff detection compared incoming memories against `DeduplicationTracker._mem_keys`.

**Now**: Diff detection SHALL use `context_block.has_memory(char_id, ts)` to determine whether a memory item is already present.

#### Scenario: Only new memories added

WHEN memories [M1(ts=100), M2(ts=200)] exist in the block
AND incoming memories are [M1(ts=100), M2(ts=200), M3(ts=300)]
THEN only M3 SHALL be added to the context block

---

### MODIFIED: Compaction replaces entire context block

**Was**: When memory compaction occurred, old system messages were removed and new ones injected.

**Now**: When memory compaction produces new compressed summaries, the entire `ContextBlock` SHALL be rebuilt from scratch (new instance, re-add all backgrounds, add new memory items). The old context block is discarded.

#### Scenario: Compaction rebuild

WHEN compaction compresses memories M1+M2+M3 into M_compressed
THEN a new `ContextBlock` SHALL be created
AND all existing backgrounds SHALL be re-added
AND M_compressed (with new timestamp) SHALL be added as the memory item
AND `_messages[1]` SHALL be replaced with the new block's `render_markdown()`

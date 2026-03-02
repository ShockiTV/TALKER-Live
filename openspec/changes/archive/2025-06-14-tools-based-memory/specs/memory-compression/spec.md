## REMOVED Requirements

### Three-tier memory architecture
**Reason**: Replaced by four-tier compaction cascade (events→summaries→digests→cores). The old three tiers (recent events, mid-term summary, long-term narrative) are superseded.
**Migration**: Memory is now stored in four structured tiers per NPC in `memory_store`. Compaction is handled by the Python `compaction-cascade` system.

### Threshold-based compression trigger
**Reason**: Replaced by per-tier cap-based compaction in Python. The old 12-event threshold in Lua is removed.
**Migration**: Compaction triggers when any tier exceeds its cap (events: 100, summaries: 10, digests: 5, cores: 5). Compaction logic lives in Python, not Lua.

### Bootstrap compression for new memories
**Reason**: Replaced by compaction cascade. There is no separate bootstrap path — the same events→summaries compaction handles first compression.
**Migration**: First compaction for a character is the same as any other: 10 events → 1 summary via LLM call.

### Incremental narrative update
**Reason**: Replaced by tier-to-tier compaction. There is no incremental update of a single narrative blob.
**Migration**: Each tier compacts to the next: events→summaries→digests→cores. Each step is a separate LLM call.

### Narrative character limit
**Reason**: Replaced by per-tier caps. There is no single narrative with a character limit.
**Migration**: Each tier has its own cap (count-based, not character-based). Compressed text size is guided by compaction prompts.

### Non-blocking compression
**Reason**: Preserved in spirit but moved to Python-side compaction-cascade spec.
**Migration**: See `compaction-cascade` spec for non-blocking compaction requirements.

### Per-character concurrency control
**Reason**: Preserved in spirit but moved to Python-side compaction-cascade spec.
**Migration**: See `compaction-cascade` spec for per-character lock requirements.

### Memory update via ZMQ command
**Reason**: Replaced by `state.mutate.batch` WS topic. The `memory.update` command with flat narrative is removed.
**Migration**: Python writes compaction results via `state.mutate.batch` with delete+append pattern.

### Lua memory store update
**Reason**: Replaced by `state.mutate.batch` handler in Lua. The `memory.update` command handler is removed.
**Migration**: Lua handles `state.mutate.batch` mutations for all memory tiers.

### Junk event filtering
**Reason**: Preserved in spirit but moved to Python prompt construction. Events are stored regardless; filtering happens at compaction prompt time.
**Migration**: The compaction prompt builder excludes junk events from the rendered text sent to the LLM.

### Chronological ordering
**Reason**: Preserved implicitly via seq-ordered storage. Seq numbers are monotonically increasing.
**Migration**: Events are naturally ordered by seq. Compaction reads oldest-first.

### Third-person perspective
**Reason**: Preserved in compaction prompt instructions.
**Migration**: The compaction prompt in `compaction-cascade` spec instructs third-person perspective.

### Save format persistence
**Reason**: Replaced by four-tier-memory-store persistence. The flat `narrative_memories` save format is superseded.
**Migration**: See `four-tier-memory-store` spec for save/load with `memories_version = "3"`.

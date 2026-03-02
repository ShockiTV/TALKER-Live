# memory-compression

## Purpose

Memory compression for NPC memories. Previously defined a three-tier architecture (recent events, mid-term summary, long-term narrative). All requirements have been superseded by the four-tier compaction cascade system.

## Requirements

All requirements previously in this spec have been moved:
- Compaction logic → see `compaction-cascade` spec
- Memory storage tiers → see `four-tier-memory-store` spec
- Persistence format → see `talker-persistence` spec (v3 format)

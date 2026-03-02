## MODIFIED Requirements

### Requirement: Memory store versioning

The memory_store persistence format SHALL use version 3 (v3). Format:

```
{
  "version": 3,
  "characters": {
    "<character_id>": {
      "events": [ {seq, timestamp, type, context}, ... ],
      "summaries": [ {seq, tier, start_ts, end_ts, text, source_count}, ... ],
      "digests": [ {seq, tier, start_ts, end_ts, text, source_count}, ... ],
      "cores": [ {seq, tier, start_ts, end_ts, text, source_count}, ... ],
      "background": { text, updated_ts } | null,
      "next_seq": <integer>
    }
  }
}
```

#### Scenario: v3 save
- **WHEN** memory_store:save() is called with 2 characters
- **THEN** saved JSON SHALL have `"version": 3` and the `characters` object with per-character tiers

#### Scenario: v3 load
- **WHEN** loading a v3 save file with 2 characters
- **THEN** each character's tiers SHALL be restored with correct seq numbers

#### Scenario: v2 → v3 migration
- **WHEN** loading a v2 memory_store save (`{version: 2, characters: {id: {narrative, last_update_time_ms}}}`)
- **THEN** the narrative text SHALL be placed into `cores[0]` as `{seq: 0, tier: "core", start_ts: 0, end_ts: last_update_time_ms, text: narrative, source_count: 0}`
- **AND** all other tiers SHALL be empty arrays
- **AND** `next_seq` SHALL be 1

#### Scenario: v1 format migration
- **WHEN** loading a v1 memory_store save (flat key-value without version)
- **THEN** each entry SHALL be migrated through v1→v2→v3 chain

### Requirement: Backstory store versioning

The backstory store persistence format SHALL remain at version 1 (unchanged by this change).

### Requirement: Personality store versioning

The personality store persistence format SHALL remain at version 1 (unchanged by this change).

### Requirement: Level store versioning

The level store persistence format SHALL remain at version 1 (unchanged by this change).

### Requirement: Timer store versioning

The timer store persistence format SHALL remain at version 1 (unchanged by this change).

## REMOVED Requirements

### Requirement: Event store versioning
**Reason**: The global event_store is eliminated. Events are now stored per-NPC inside the memory_store as the events tier.
**Migration**: Event store persistence (v2 format: `{version: 2, events: [...]}`) no longer needs to be saved or loaded. The v2→v3 memory_store migration handles any necessary data transfer. The `talker_game_files.load_event_store` / `talker_game_files.save_event_store` functions can be removed.

### Requirement: Event store save/load lifecycle
**Reason**: With no global event_store, there is no separate event_store save file to manage.
**Migration**: Remove event_store persistence hooks from game save/load callbacks. Memory_store v3 persistence covers all memory data.

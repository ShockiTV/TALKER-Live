# global-unique-timestamp

## Purpose

Replaces per-character monotonic `seq` counter in `memory_store_v2` with a global `unique_ts()` function that returns a collision-free millisecond timestamp, serving as the sole identity key for all memory items (events, summaries, digests, cores).

## Requirements

### Requirement: unique_ts returns monotonically increasing values

#### Scenario: Two events created in the same game tick

WHEN `unique_ts()` is called twice in the same tick  
AND `engine.get_game_time_ms()` returns the same value both times  
THEN the second call returns `previous_value + 1`  
AND both values are globally unique within the session

#### Scenario: Normal event creation across ticks

WHEN `unique_ts()` is called in a later tick  
AND `engine.get_game_time_ms()` returns a value greater than the last assigned timestamp  
THEN the returned value equals the raw `game_time_ms`

---

### Requirement: unique_ts replaces per-character seq in memory_store_v2

#### Scenario: Storing an event

WHEN `store_event(char_id, event)` is called  
THEN the event's timestamp field is the value from `unique_ts()`  
AND no per-character `next_seq` counter is incremented  
AND the event is stored in the character's recent tier keyed by the unique timestamp

#### Scenario: Storing a compacted item (summary/digest/core)

WHEN a compacted item is created from compressing N events  
THEN the item's `start_ts` is the minimum unique_ts of the source items  
AND the item's `end_ts` is the maximum unique_ts of the source items  
AND `start_ts` serves as the dedup key for that compacted item

#### Scenario: Fan-out of a global event

WHEN `store_global_event(event)` fans out to multiple characters  
THEN a single `unique_ts()` value is assigned once  
AND all character copies share the same timestamp

---

### Requirement: Save/load migration from seq to unique_ts

#### Scenario: Loading a save with per-character seq data (v3 format)

WHEN `load_save_data()` encounters v3 format data with per-character `next_seq` fields  
THEN each existing item's seq-based identifier is replaced with a unique_ts value  
AND collision resolution applies the same bump logic  
AND the `next_seq` field is removed from persisted state

---

### Requirement: unique_ts state resets on new game / load

#### Scenario: Game is loaded from a save

WHEN a save file is loaded  
THEN `_last_ts` is reset  
AND subsequent `unique_ts()` calls start fresh from `game_time_ms`

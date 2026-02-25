# Spec: Memory Query Migration

## Purpose

Defines the migration of memory context construction from Lua to Python, using store queries for events and memories.

## Requirements

### Requirement: Python-side Memory Context Construction
The system SHALL construct the `MemoryContext` entirely within the Python service (`generator.py`) by querying the Lua `store.events` and `store.memories` separately using the universal store query language.

#### Scenario: Constructing memory context for dialogue
- **WHEN** the Python service needs to generate dialogue for a speaker
- **THEN** it queries `store.memories` for the speaker's narrative and `last_update_time_ms`
- **THEN** it queries `store.events` for events witnessed by the speaker that occurred after `last_update_time_ms`
- **THEN** it combines these results into a `MemoryContext` object

### Requirement: Querying Events by Witness
The system SHALL use the `$elemMatch` operator in the universal store query language to filter events in `store.events` based on the `witnesses` array.

#### Scenario: Fetching new events for a speaker
- **WHEN** the Python service queries `store.events` for a specific speaker
- **THEN** the query MUST include a filter like `{"witnesses": {"$elemMatch": {"game_id": speaker_id}}}`
- **THEN** the query MUST include a filter like `{"game_time_ms": {"$gt": last_update_time_ms}}`
- **THEN** the Lua filter engine SHALL return only events where the speaker is in the `witnesses` array and the event occurred after the specified time.

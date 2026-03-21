# Spec: Memory System

## Purpose

Defines the responsibilities of the Lua memory store and its separation from Python-side memory context construction.

## Requirements

### Requirement: Memory Store Responsibilities

The Lua `memory_store` SHALL store per-NPC structured memory with five fields: `events` (list of structured events), `summaries` (list of compressed memories), `digests` (list of compressed memories), `cores` (list of compressed memories), and `background` (structured table or nil). It SHALL provide a unified DSL with `append`, `delete`, `set`, `update`, `query` operations. It SHALL also maintain a `global_event_buffer` for emission/psy-storm backfill.

The `memory_store` SHALL NOT store flat narrative blobs. The `narrative` and `last_update_time_ms` fields are removed.

#### Scenario: Retrieving memory from Lua
- **WHEN** the Python service queries `memory.events` for a character
- **THEN** the Lua `memory_store` SHALL return the character's structured events list
- **AND** SHALL NOT return a flat `narrative` string

#### Scenario: memory_store does not store narrative blobs
- **WHEN** any code queries the memory_store
- **THEN** there SHALL be no `narrative` or `last_update_time_ms` fields on character memory entries

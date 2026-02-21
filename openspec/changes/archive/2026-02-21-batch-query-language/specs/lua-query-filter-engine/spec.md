# lua-query-filter-engine

## Purpose

Generic recursive filter evaluator for Lua tables, supporting MongoDB-style comparison, set, string, existence, array, and logical operators, plus sort, limit, and field projection. Pure Lua with no game dependencies.

## Requirements

### Requirement: Filter engine module location

The filter engine SHALL be located at `bin/lua/infra/query/filter_engine.lua` and SHALL have zero dependencies on game APIs or `gamedata/scripts/` modules. It SHALL depend only on the Lua 5.1 standard library.

#### Scenario: Module loads without game environment
- **WHEN** `filter_engine.lua` is required from a standalone Lua 5.1 interpreter
- **THEN** the module SHALL load successfully without errors
- **AND** all filter functions SHALL be available

### Requirement: Dotted field path resolution

The filter engine SHALL resolve dotted field paths (e.g., `"context.victim.faction"`) by traversing nested tables. Numeric path segments SHALL be treated as integer keys for array access.

#### Scenario: Resolve nested field
- **WHEN** evaluating filter `{"context.victim.faction": "bandit"}` against `{context = {victim = {faction = "bandit"}}}`
- **THEN** the filter SHALL match (return true)

#### Scenario: Resolve missing nested field
- **WHEN** evaluating filter `{"context.weapon": "AK-74"}` against `{context = {}}`
- **THEN** the resolved value SHALL be nil
- **AND** the filter SHALL not match

#### Scenario: Resolve numeric array index
- **WHEN** evaluating filter `{"witnesses.0.name": "Wolf"}` against `{witnesses = {{name = "Wolf"}}}`
- **THEN** numeric segment `0` SHALL map to Lua index `1`
- **AND** the filter SHALL match

### Requirement: Comparison operators

The filter engine SHALL support `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte` operators for comparing field values.

#### Scenario: Implicit $eq shorthand
- **WHEN** filter is `{"type": "death"}`
- **THEN** it SHALL be equivalent to `{"type": {"$eq": "death"}}`

#### Scenario: $gt on numeric field
- **WHEN** filter is `{"game_time_ms": {"$gt": 50000}}` and document has `game_time_ms = 60000`
- **THEN** the filter SHALL match

#### Scenario: $lte on numeric field
- **WHEN** filter is `{"game_time_ms": {"$lte": 50000}}` and document has `game_time_ms = 60000`
- **THEN** the filter SHALL NOT match

#### Scenario: $ne excludes matching value
- **WHEN** filter is `{"type": {"$ne": "idle"}}` and document has `type = "idle"`
- **THEN** the filter SHALL NOT match

### Requirement: Set operators

The filter engine SHALL support `$in` and `$nin` operators for checking membership in a list of values.

#### Scenario: $in matches any value in list
- **WHEN** filter is `{"type": {"$in": ["death", "injury"]}}` and document has `type = "injury"`
- **THEN** the filter SHALL match

#### Scenario: $in does not match absent value
- **WHEN** filter is `{"type": {"$in": ["death", "injury"]}}` and document has `type = "idle"`
- **THEN** the filter SHALL NOT match

#### Scenario: $nin excludes listed values
- **WHEN** filter is `{"type": {"$nin": ["idle", "reload"]}}` and document has `type = "death"`
- **THEN** the filter SHALL match

### Requirement: String operator ($regex)

The filter engine SHALL support `$regex` for matching field values against Lua patterns (not PCRE). An optional `$regex_flags` field with value `"i"` SHALL enable case-insensitive matching by lowercasing both the value and the pattern before evaluation.

#### Scenario: $regex matches Lua pattern
- **WHEN** filter is `{"name": {"$regex": "^Stalker_"}}` and document has `name = "Stalker_42"`
- **THEN** the filter SHALL match

#### Scenario: $regex with case-insensitive flag
- **WHEN** filter is `{"name": {"$regex": "wolf", "$regex_flags": "i"}}` and document has `name = "Wolf"`
- **THEN** the filter SHALL match (both lowered before comparison)

#### Scenario: $regex does not match non-matching pattern
- **WHEN** filter is `{"name": {"$regex": "^bandit"}}` and document has `name = "Wolf"`
- **THEN** the filter SHALL NOT match

### Requirement: Existence operator

The filter engine SHALL support `$exists` to check whether a field is present (non-nil) or absent (nil).

#### Scenario: $exists true on present field
- **WHEN** filter is `{"context.weapon": {"$exists": true}}` and document has `context.weapon = "AK-74"`
- **THEN** the filter SHALL match

#### Scenario: $exists true on absent field
- **WHEN** filter is `{"context.weapon": {"$exists": true}}` and document has no `context.weapon`
- **THEN** the filter SHALL NOT match

#### Scenario: $exists false on absent field
- **WHEN** filter is `{"context.weapon": {"$exists": false}}` and document has no `context.weapon`
- **THEN** the filter SHALL match

### Requirement: Array operators

The filter engine SHALL support `$elemMatch`, `$size`, and `$all` for array field queries.

#### Scenario: $elemMatch matches element satisfying sub-filter
- **WHEN** filter is `{"witnesses": {"$elemMatch": {"game_id": "123", "faction": "duty"}}}`
- **AND** document has `witnesses = {{game_id = "123", faction = "duty"}, {game_id = "456", faction = "bandit"}}`
- **THEN** the filter SHALL match (first element satisfies all sub-conditions)

#### Scenario: $elemMatch fails when no element matches all conditions
- **WHEN** filter is `{"witnesses": {"$elemMatch": {"game_id": "123", "faction": "bandit"}}}`
- **AND** document has `witnesses = {{game_id = "123", faction = "duty"}, {game_id = "456", faction = "bandit"}}`
- **THEN** the filter SHALL NOT match (no single element satisfies both conditions)

#### Scenario: $size checks array length
- **WHEN** filter is `{"witnesses": {"$size": 2}}` and document has 2 witnesses
- **THEN** the filter SHALL match

#### Scenario: $size fails on wrong length
- **WHEN** filter is `{"witnesses": {"$size": 3}}` and document has 2 witnesses
- **THEN** the filter SHALL NOT match

#### Scenario: $all checks array contains all values
- **WHEN** filter is `{"tags": {"$all": ["combat", "mutant"]}}` and document has `tags = {"combat", "zone", "mutant"}`
- **THEN** the filter SHALL match

#### Scenario: $all fails when not all values present
- **WHEN** filter is `{"tags": {"$all": ["combat", "mutant"]}}` and document has `tags = {"combat", "zone"}`
- **THEN** the filter SHALL NOT match

### Requirement: Logical operators

The filter engine SHALL support `$and`, `$or`, and `$not` for composing filter conditions. Top-level filter keys SHALL be implicitly ANDed.

#### Scenario: Implicit AND at top level
- **WHEN** filter is `{"type": "death", "game_time_ms": {"$gt": 50000}}`
- **AND** document has `type = "death"` and `game_time_ms = 60000`
- **THEN** the filter SHALL match (both conditions true)

#### Scenario: Implicit AND fails when one condition fails
- **WHEN** filter is `{"type": "death", "game_time_ms": {"$gt": 50000}}`
- **AND** document has `type = "death"` and `game_time_ms = 40000`
- **THEN** the filter SHALL NOT match

#### Scenario: $or matches when any sub-filter matches
- **WHEN** filter is `{"$or": [{"type": "death"}, {"type": "injury"}]}`
- **AND** document has `type = "injury"`
- **THEN** the filter SHALL match

#### Scenario: $or fails when no sub-filter matches
- **WHEN** filter is `{"$or": [{"type": "death"}, {"type": "injury"}]}`
- **AND** document has `type = "idle"`
- **THEN** the filter SHALL NOT match

#### Scenario: $and with explicit sub-filters
- **WHEN** filter is `{"$and": [{"game_time_ms": {"$gt": 50000}}, {"game_time_ms": {"$lt": 90000}}]}`
- **AND** document has `game_time_ms = 70000`
- **THEN** the filter SHALL match

#### Scenario: $not negates sub-condition
- **WHEN** filter is `{"type": {"$not": {"$in": ["idle", "reload"]}}}`
- **AND** document has `type = "death"`
- **THEN** the filter SHALL match

#### Scenario: Nested logical operators
- **WHEN** filter is `{"$and": [{"game_time_ms": {"$gt": 50000}}, {"$or": [{"type": "death"}, {"type": "injury"}]}]}`
- **AND** document has `type = "death"` and `game_time_ms = 60000`
- **THEN** the filter SHALL match (nested recursion works)

### Requirement: Pipeline orchestrator (`execute_pipeline`)

The filter engine SHALL provide a pipeline orchestrator function `execute_pipeline(source_iter, filter, sort, limit)` that selects an execution strategy based on which stages are present, minimizing intermediate memory allocations.

The `source_iter` parameter SHALL be an **iterator function** (called repeatedly, returns next document or nil) rather than a pre-materialized array. This allows callers to provide pre-narrowed iterators (e.g., event_store scanning from a binary-search position).

The orchestrator SHALL return an array of document references (not copies), ready for projection.

#### Strategy: sort + limit → fused top-N scan

- **WHEN** both `sort` and `limit` are present
- **THEN** the pipeline SHALL scan `source_iter` in a single pass, maintaining a bounded sorted buffer of at most `limit` elements
- **AND** for each document from the iterator, if it passes the filter:
  - If buffer size < limit → insert at sorted position (binary insertion)
  - Else if document's sort value beats the buffer's worst element → evict worst, insert
  - Else → skip (document cannot make the top N)
- **AND** peak memory SHALL be O(limit) document references

#### Scenario: Top-N scan with limit=3 from 100 matching docs
- **WHEN** sort is `{"game_time_ms": -1}`, limit is 3, and 100 documents pass the filter
- **THEN** result SHALL contain exactly the 3 documents with the highest `game_time_ms`
- **AND** at no point SHALL more than 3 document references be held in the buffer

#### Strategy: limit only (no sort) → early-termination scan

- **WHEN** `limit` is present but `sort` is nil
- **THEN** the pipeline SHALL stop scanning `source_iter` after `limit` documents pass the filter
- **AND** peak memory SHALL be O(limit) document references

#### Scenario: Early termination with limit=5
- **WHEN** limit is 5, no sort, and source has 1000 documents with 500 matching the filter
- **THEN** result SHALL contain exactly 5 documents (the first 5 that match in iteration order)
- **AND** scanning SHALL stop after the 5th match (remaining ~995 documents not visited)

#### Strategy: sort only (no limit) → sort all matches

- **WHEN** `sort` is present but `limit` is nil
- **THEN** the pipeline SHALL collect all matching document references and sort them
- **AND** sort SHALL use the specified field and direction (1 ascending, -1 descending)

#### Scenario: Sort ascending by game_time_ms
- **WHEN** sort spec is `{"game_time_ms": 1}` and matches have times 300, 100, 200
- **THEN** result order SHALL be 100, 200, 300

#### Scenario: Sort descending by game_time_ms
- **WHEN** sort spec is `{"game_time_ms": -1}` and matches have times 300, 100, 200
- **THEN** result order SHALL be 300, 200, 100

#### Strategy: filter only (no sort, no limit) → collect all matches

- **WHEN** neither `sort` nor `limit` is present
- **THEN** the pipeline SHALL collect all documents from `source_iter` that pass the filter

#### Scenario: Limit larger than matches
- **WHEN** limit is 50 and only 5 documents pass the filter
- **THEN** result SHALL contain all 5 documents

### Requirement: Field projection

The filter engine SHALL provide a projection function that returns documents containing only the specified field paths. When `fields` is nil or empty, full documents SHALL be returned unchanged.

#### Scenario: Project specific fields
- **WHEN** fields is `["type", "game_time_ms"]` and document has `{type = "death", game_time_ms = 50000, context = {...}, witnesses = [...]}`
- **THEN** projected result SHALL be `{type = "death", game_time_ms = 50000}`

#### Scenario: Project nested dotted path
- **WHEN** fields is `["context.victim.name", "type"]` and document has nested context
- **THEN** projected result SHALL be `{type = "death", context = {victim = {name = "Wolf"}}}`

#### Scenario: No fields means full document
- **WHEN** fields is nil
- **THEN** the original document SHALL be returned unchanged

## Requirements

### Requirement: game.event handler indexes before dialogue

The Python `handlers/events.py` game event handler SHALL index the event into Neo4j (fire-and-forget async task) BEFORE invoking dialogue generation. If the event carries `flags.index_only = true`, dialogue generation SHALL be skipped entirely after indexing.

#### Scenario: Normal event is indexed then generates dialogue
- **WHEN** `game.event` arrives without `index_only`
- **THEN** Neo4j ingest task is created first, then dialogue generation proceeds

#### Scenario: index_only event skips dialogue
- **WHEN** `game.event` arrives with `flags.index_only = true`
- **THEN** Neo4j ingest task is created and dialogue generation is NOT triggered

#### Scenario: Ingest failure is non-blocking
- **WHEN** the Neo4j ingest task raises an exception
- **THEN** the exception is logged and dialogue generation proceeds unaffected

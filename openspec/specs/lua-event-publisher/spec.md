# lua-event-publisher

## Purpose

Extends `bin/lua/infra/ws/publisher.lua` to handle state query responses and integrate with command handlers.

## Requirements

### Requirement: send_game_event function

`send_game_event(event, candidates, world, traits)` SHALL serialize and send a `game.event` WebSocket message with:
- `event` – serialized event object (type, context, game_time_ms, witnesses)
- `candidates` – array of serialized nearby NPC Character objects
- `world` – serialized scene context (location, time, weather, etc.)
- `traits` – map of `character_id` → `{personality_id, backstory_id}` for all candidates

The function SHALL NOT accept an `is_important` parameter.

#### Scenario: Publish death event with full context
- **WHEN** `send_game_event(death_event, {npc1, npc2}, world_ctx, traits_map)` is called
- **THEN** a WS message SHALL be sent with topic `game.event`
- **AND** payload SHALL contain `event`, `candidates`, `world`, `traits`
- **AND** payload SHALL NOT contain `is_important`

#### Scenario: traits map includes all candidates
- **WHEN** sending a game event with 3 candidates
- **THEN** `traits` SHALL have entries for all 3 candidate character IDs

### Requirement: State response function

`send_state_response(request_id, results)` SHALL serialize and send a `state.response` WebSocket message. This function handles responses to both `state.query.batch` and `state.mutate.batch` requests.

#### Scenario: Respond to mutation batch
- **WHEN** `send_state_response("mut-1", {{ok=true}, {ok=true}})` is called
- **THEN** a WS message SHALL be sent with topic `state.response` and the `r` field set to `"mut-1"`

### Requirement: Error response function

The error response function SHALL remain unchanged.

#### Scenario: Send error response
- **WHEN** character query fails (not found)
- **THEN** send_error_response is called
- **AND** message includes request_id
- **AND** success=false with error message

### Requirement: Query Response Topic Constant

The system MUST define topic constant `publisher.topics.STATE_RESPONSE = "state.response"`.

#### Scenario: Topic constant available
- **WHEN** publisher module is loaded
- **THEN** STATE_RESPONSE topic constant SHALL be defined

### Requirement: Serialization Helpers

The serialization helpers MUST handle memory context, event lists, and character objects.

#### Scenario: Serialize event list
- **WHEN** events.recent query returns 10 events
- **THEN** all events are serialized to JSON
- **AND** typed events preserve type + context fields

#### Scenario: Response includes request_id
- **WHEN** any state response is sent
- **THEN** request_id from original query is included

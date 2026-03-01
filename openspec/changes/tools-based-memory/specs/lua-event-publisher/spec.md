## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: is_important parameter in send_game_event
**Reason**: Speaker selection is no longer decided Lua-side. The `is_important` flag is eliminated from the wire protocol. Python selects the speaker via LLM tool calls.
**Migration**: Remove `is_important` from `send_game_event` signature and from the serialized payload.

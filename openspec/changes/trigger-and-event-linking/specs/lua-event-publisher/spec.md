# lua-event-publisher (Delta)

> **Change**: `trigger-and-event-linking`
> **Operation**: MODIFIED

---

## MODIFIED Requirements

### Requirement: send_game_event function

`send_game_event(event, candidates, world, traits)` SHALL serialize and send a `game.event` WebSocket message with:
- `event` – serialized event object (type, context, game_time_ms, **ts**, witnesses)
- `candidates` – array of serialized nearby NPC Character objects
- `world` – serialized scene context (location, time, weather, etc.)
- `traits` – map of `character_id` → `{personality_id, backstory_id}` for all candidates

The serialized event object SHALL include the `ts` field from the source event.

#### Scenario: Publish death event with ts included
- **WHEN** `send_game_event(death_event, {npc1, npc2}, world_ctx, traits_map)` is called
- **THEN** a WS message SHALL be sent with topic `game.event`
- **AND** `payload.event.ts` SHALL equal the source event's `ts` value
- **AND** payload SHALL contain `event`, `candidates`, `world`, `traits`

#### Scenario: ts is the unique timestamp from event creation
- **WHEN** the source event was created with `ts = unique_ts()`
- **THEN** `payload.event.ts` SHALL be that exact integer timestamp
- **AND** it SHALL match the `ts` stored in all witnesses' memory via `memory_store_v2:store_event()`

### Requirement: Serialization Helpers

The serialization helpers MUST handle memory context, event lists, and character objects. The event serializer SHALL include the `ts` field.

#### Scenario: Serialize event includes ts
- **WHEN** `serialize_event(event)` is called on a typed event with `ts=1709912345`
- **THEN** the returned table SHALL include `ts = 1709912345`
- **AND** all other fields (type, context, game_time_ms, world_context, witnesses, flags) SHALL remain unchanged

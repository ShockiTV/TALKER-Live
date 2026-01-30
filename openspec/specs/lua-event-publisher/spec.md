# lua-event-publisher

## Purpose

Extends `bin/lua/infra/zmq/publisher.lua` to handle state query responses and integrate with command handlers.

## Requirements

### Publisher Module

The publisher module MUST provide event publishing and state response capabilities for ZMQ communication.

#### Scenario: Publish game event
- **WHEN** send_game_event(event, is_important) is called
- **THEN** event SHALL be serialized and published to game.event topic

### State Response Function

The system MUST provide `send_state_response(request_id, type, data)` that publishes to `state.response` topic with correlation ID.

#### Scenario: Send successful memory response
- **WHEN** Lua queries memory_store successfully
- **THEN** send_state_response is called with memory context
- **AND** message includes request_id
- **AND** success=true in payload

### Error Response Function

The system MUST provide `send_error_response(request_id, type, error_msg)` for reporting query failures.

#### Scenario: Send error response
- **WHEN** character query fails (not found)
- **THEN** send_error_response is called
- **AND** message includes request_id
- **AND** success=false with error message

### Query Response Topic Constant

The system MUST define topic constant `publisher.topics.STATE_RESPONSE = "state.response"`.

#### Scenario: Topic constant available
- **WHEN** publisher module is loaded
- **THEN** STATE_RESPONSE topic constant SHALL be defined

### Serialization Helpers

The serialization helpers MUST handle memory context, event lists, and character objects.

#### Scenario: Serialize event list
- **WHEN** events.recent query returns 10 events
- **THEN** all events are serialized to JSON
- **AND** typed events preserve type + context fields

#### Scenario: Response includes request_id
- **WHEN** any state response is sent
- **THEN** request_id from original query is included

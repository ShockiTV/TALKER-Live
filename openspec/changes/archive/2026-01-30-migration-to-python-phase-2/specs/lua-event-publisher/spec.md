# lua-event-publisher (MODIFIED)

## Overview

Extends existing `bin/lua/infra/zmq/publisher.lua` to handle state query responses and integrate with new command handlers.

## Requirements

### MODIFIED: Publisher Module

The existing publisher module MUST be extended with:
- `send_state_response(request_id, type, data)` function
- `send_error_response(request_id, type, error)` function
- Integration with state query handlers

### ADDED: State Response Function

The system MUST provide `send_state_response(request_id, type, data)` that:
- Publishes to `state.response` topic
- Includes request_id for correlation
- Sets success=true in payload
- Serializes data appropriately

### ADDED: Error Response Function

The system MUST provide `send_error_response(request_id, type, error_msg)` that:
- Publishes to `state.response` topic
- Includes request_id for correlation
- Sets success=false in payload
- Includes error message

### ADDED: Query Response Topic Constant

The system MUST add topic constant:
- `publisher.topics.STATE_RESPONSE = "state.response"`

### MODIFIED: Serialization Helpers

The existing serialization helpers MUST be extended to handle:
- Memory context (narrative + events)
- Event lists with all fields
- Character objects with visual_faction

## Scenarios

#### Send successful memory response

WHEN Lua queries memory_store successfully
THEN send_state_response is called with memory context
AND message includes request_id
AND success=true in payload
AND Python receives correlated response

#### Send error response

WHEN character query fails (not found)
THEN send_error_response is called
AND message includes request_id
AND success=false with error message
AND Python QueryError is raised

#### Serialize event list

WHEN events.recent query returns 10 events
THEN all events are serialized to JSON
AND typed events preserve type + context fields
AND legacy events include content field

#### Response includes request_id

WHEN any state response is sent
THEN request_id from original query is included
AND Python correlation matches correctly

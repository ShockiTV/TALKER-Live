# python-zmq-router (delta)

## MODIFIED Requirements

### Requirement: Initialize with both sockets

The `ZMQRouter` class MUST accept an optional `context` parameter. When provided, the router SHALL use that context instance instead of creating its own `zmq.asyncio.Context`. When not provided, the router SHALL create its own context as before (backward-compatible).

#### Scenario: Initialize with both sockets

- **WHEN** `ZMQRouter(sub_endpoint, pub_endpoint)` is called with no `context` argument
- **THEN** SUB socket connects to the given sub_endpoint
- **AND** PUB socket binds to the given pub_endpoint
- **AND** the router creates its own `zmq.asyncio.Context` internally

#### Scenario: Initialize with shared context

- **WHEN** `ZMQRouter(sub_endpoint, pub_endpoint, context=shared_ctx)` is called
- **THEN** the router SHALL use `shared_ctx` for all socket creation
- **AND** SHALL NOT create a new `zmq.asyncio.Context`
- **AND** on shutdown, SHALL NOT call `context.term()` (caller owns the context)

#### Scenario: PUB socket binds

- **WHEN** router starts
- **THEN** PUB socket binds to the configured pub_endpoint

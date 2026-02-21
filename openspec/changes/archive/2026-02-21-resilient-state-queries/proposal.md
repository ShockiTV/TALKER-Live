## Why

When the player opens the main menu (ESC) during an in-flight dialogue generation, the game engine freezes all `CreateTimeEvent` timers — including ZMQ command polling. Python's state queries (memories, character, world context) cannot get responses from Lua, hit the 30-second timeout, and the entire dialogue generation silently fails. The player returns to the game, sees a "service disconnected/reconnected" notification, and the dialogue they triggered is permanently lost.

## What Changes

- Add a retry/deferral layer in the Python service that detects state query timeouts caused by Lua being unresponsive (menu pause) and parks the pending dialogue generation request instead of discarding it
- Add heartbeat-aware resume logic that detects when Lua comes back online (heartbeat received after a gap) and flushes parked requests by re-triggering their dialogue generation
- Add a configurable retry policy (max retries, backoff) to prevent infinite retry loops for genuinely broken queries vs temporary pauses
- Improve the dialogue generator's error handling to distinguish between transient failures (Lua paused) and permanent failures (bad data, LLM error), only retrying the former

## Capabilities

### New Capabilities
- `dialogue-retry-queue`: Queue for parking and retrying dialogue generation requests that failed due to transient state query timeouts, with heartbeat-aware flush and configurable retry policy

### Modified Capabilities
- `python-state-query-client`: State query timeout now raises a distinguishable transient error (vs permanent), enabling callers to decide whether to retry
- `python-dialogue-generator`: Dialogue generation catches transient state query failures and defers to the retry queue instead of silently discarding

## Impact

- `talker_service/src/talker_service/dialogue/generator.py` — catch transient errors, delegate to retry queue
- `talker_service/src/talker_service/state/client.py` — raise typed exception on timeout (e.g., `StateQueryTimeout` vs generic `TimeoutError`)
- `talker_service/src/talker_service/dialogue/retry_queue.py` — new module: retry queue with heartbeat-aware flush
- `talker_service/src/talker_service/handlers/events.py` — wire heartbeat handler to trigger retry queue flush
- `talker_service/tests/` — new tests for retry queue, updated tests for generator error handling
- Zero Lua changes
- Low risk: retry logic is additive, existing happy-path behavior unchanged

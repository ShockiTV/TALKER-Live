## Context

The Python service's dialogue generation pipeline requires multiple synchronous state queries to Lua (memories, character details, world context) during each dialogue flow. These queries use ZMQ pub/sub with request-response correlation — Python publishes `state.query.*`, waits for `state.response` with a matching `request_id`, with a 30-second timeout.

The STALKER Anomaly engine freezes all `CreateTimeEvent` timers when the player opens the main menu (ESC). Since ZMQ command polling on the Lua side is driven by `CreateTimeEvent`, Lua cannot receive or respond to state queries while paused. This causes all in-flight state queries to hit the 30-second timeout, and the dialogue generation silently fails in the `except Exception` catch-all at the generator level.

The heartbeat gap during pause also triggers the service status check, resulting in a false "service disconnected / reconnected" notification cycle when the player returns to the game.

**Current error path:**
1. Event arrives → Python starts `_generate_dialogue_for_speaker()`
2. Player opens menu → Lua timers freeze
3. `query_memories()` → publishes `state.query.memories` → waits 30s → `TimeoutError`
4. Generator catches exception → `logger.error("Dialogue generation failed")` → done
5. Player returns → heartbeat resumes → disconnect/reconnect notifications
6. Dialogue is permanently lost

## Goals / Non-Goals

**Goals:**
- Dialogue generation requests that fail due to Lua being unresponsive (menu pause) SHALL be retried when Lua comes back online
- State query timeouts SHALL raise a distinguishable exception type (`StateQueryTimeout`) so callers can differentiate transient failures from permanent ones
- Retries SHALL be bounded by max attempts to prevent infinite retry loops on genuinely broken queries
- The retry mechanism SHALL be triggered by heartbeat resumption (proof that Lua is back)
- Existing happy-path behavior SHALL be completely unchanged
- Zero Lua-side changes

**Non-Goals:**
- State response caching (future enhancement, not in scope)
- Changing the ZMQ transport layer or polling mechanism
- Fixing the Lua-side freeze (engine limitation, not addressable)
- Retrying LLM failures (those are permanent — bad prompt, model error, rate limit)
- Retrying state queries that return error responses from Lua (those are data errors, not connectivity)

## Decisions

### 1. New `StateQueryTimeout` exception type in state client

**Rationale**: The current `TimeoutError` is generic Python. Callers cannot distinguish "Lua is paused" from other timeout causes. A dedicated `StateQueryTimeout(TimeoutError)` subclass preserves backward compatibility (existing `except TimeoutError` still catches it) while allowing the generator to specifically catch and defer transient failures.

**Alternative considered**: Using a boolean flag on a generic exception — rejected because exception types are the idiomatic Python pattern for error discrimination.

### 2. Retry queue as a standalone module (`dialogue/retry_queue.py`)

**Rationale**: The retry queue is a cross-cutting concern that sits between event handlers and the dialogue generator. A standalone module with a simple class (`DialogueRetryQueue`) keeps it testable and decoupled. The queue stores the original event dict and metadata (attempt count, timestamp, generation method name) needed to re-invoke the generator.

**Alternative considered**: Adding retry logic inside `DialogueGenerator._generate_dialogue_for_speaker()` — rejected because it would mix retry scheduling with dialogue logic, and the generator shouldn't know about heartbeat awareness.

### 3. Heartbeat-triggered flush

**Rationale**: When a heartbeat arrives after a gap (detected by comparing current time to last heartbeat time exceeding a threshold), Python knows Lua is responsive again. The heartbeat handler calls `retry_queue.flush()`, which re-submits all parked requests as `asyncio.create_task()` calls. This reuses the existing heartbeat infrastructure without adding new signaling mechanisms.

**Threshold**: A heartbeat gap of `>= 2x heartbeat_interval` (configurable, default heartbeat is every few seconds) indicates Lua was paused. The flush is triggered on the first heartbeat after such a gap.

**Alternative considered**: Polling-based retry with exponential backoff — rejected because it would fire retries blindly without knowing if Lua is back, wasting state queries that would just timeout again.

### 4. Retry queue items store the event dict + generation method

**Rationale**: The queue needs to re-invoke either `generate_from_event(event_dict)` or `generate_from_instruction(speaker_id, event_dict)` depending on which path originally failed. Storing a simple dataclass with `method` (enum: "event" or "instruction"), `event_dict`, optional `speaker_id`, `attempt_count`, and `enqueued_at` timestamp is sufficient.

### 5. Max retries = 5, no max age, no queue size limit

**Rationale**: A request that has been retried 5 times and still fails is likely a permanent issue, not a pause. There is no max age constraint because game time does not advance during a menu pause — the event context is equally valid whether the player paused for 10 seconds or 10 minutes. There is no queue size limit because the queue can only grow from in-flight requests at the moment of pause, and Lua stops sending events while paused, so the queue is naturally bounded to a handful of items (typically 1-3).

**Alternative considered**: Max age of 120 seconds — rejected because wall-clock time is irrelevant when game state is frozen. Max queue size of 10 — rejected as unnecessary given the natural bound.

### 6. Generator catches `StateQueryTimeout` specifically and defers

**Rationale**: In `_generate_dialogue_for_speaker()`, the first state query is `query_memories()`. If this raises `StateQueryTimeout`, the generator catches it and enqueues the request to the retry queue instead of logging and discarding. Other exceptions (LLM errors, data errors, `ConnectionError`) are still caught and discarded as before — they're not transient.

The catch is placed at the method level (wrapping all three state queries), not per-query, because if memories fail due to pause, character and world queries will also fail.

### 7. Retry queue injected into generator via constructor

**Rationale**: The `DialogueGenerator` constructor already accepts `state_client`, `publisher`, and `speaker_selector`. Adding an optional `retry_queue` parameter follows the same dependency injection pattern. If `retry_queue` is None, timeout failures are handled as before (logged and discarded) — preserving backward compatibility for tests.

## Risks / Trade-offs

**[Double-fire if heartbeat arrives during active generation]** → Mitigated by removing items from the queue before re-invoking. The `flush()` method atomically drains the queue, so concurrent flushes don't double-process.

**[Queue memory during long pause]** → Non-issue. The queue only contains in-flight requests from the moment of pause. Lua stops sending events while paused, so the queue cannot grow. Typical size is 1-3 items.

**[Speaker cooldown state may have changed]** → Acceptable. The retried generation re-runs speaker selection, which re-checks cooldowns. If the original speaker is now on cooldown from another dialogue, a different speaker may be selected, or no dialogue generated. This is correct behavior.

**[Test isolation]** → The retry queue is optional (None default in generator). Existing tests don't need modification. New tests mock the generator and test the queue independently.

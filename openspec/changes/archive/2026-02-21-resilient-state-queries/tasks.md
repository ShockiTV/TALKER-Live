## 1. Add StateQueryTimeout exception

- [x] 1.1 Create `StateQueryTimeout(TimeoutError)` exception class in `talker_service/src/talker_service/state/client.py` with `topic` and `character_id` optional attributes
- [x] 1.2 Update `_send_query()` to catch `TimeoutError` from the future and re-raise as `StateQueryTimeout` with the query topic and params
- [x] 1.3 Add tests for `StateQueryTimeout`: verify it's a subclass of `TimeoutError`, verify attributes are set, verify existing `except TimeoutError` still catches it

## 2. Create DialogueRetryQueue

- [x] 2.1 Create `talker_service/src/talker_service/dialogue/retry_queue.py` with `RetryItem` dataclass (method: str, event_dict: dict, speaker_id: str | None, attempt_count: int) and `DialogueRetryQueue` class with configurable `max_retries` (default 5)
- [x] 2.2 Implement `enqueue(method, event_dict, speaker_id=None, attempt_count=1)` — appends item to queue
- [x] 2.3 Implement `flush(generator)` — atomically drains queue, filters out max-retry items with warning logs, re-submits valid items via `asyncio.create_task()` calling the appropriate generator method, increments attempt_count
- [x] 2.4 Implement `notify_heartbeat(now: float)` — tracks heartbeat timestamps, detects gap >= 2x interval, triggers flush when gap detected
- [x] 2.5 Add `size` property and `clear()` method

## 3. Wire retry queue into DialogueGenerator

- [x] 3.1 Add optional `retry_queue: DialogueRetryQueue | None = None` parameter to `DialogueGenerator.__init__()`, store as `self.retry_queue`
- [x] 3.2 In `_generate_dialogue_for_speaker()`, wrap the state query block in a `try/except StateQueryTimeout` that enqueues to `self.retry_queue` if available, otherwise logs and returns as before
- [x] 3.3 In `generate_from_event()`, catch `StateQueryTimeout` from `_pick_speaker()` (which also makes state queries) and enqueue if retry_queue available
- [x] 3.4 In `generate_from_instruction()`, catch `StateQueryTimeout` from the generation call and enqueue with method="instruction" and speaker_id

## 4. Wire heartbeat to retry queue flush

- [x] 4.1 In `talker_service/src/talker_service/handlers/events.py`, add module-level `_retry_queue` variable with `set_retry_queue()` injector function
- [x] 4.2 In `handle_heartbeat()`, call `_retry_queue.notify_heartbeat(time.time())` if retry queue is set
- [x] 4.3 In `__main__.py`, create `DialogueRetryQueue` instance, pass to `DialogueGenerator` constructor, and inject into event handlers via `set_retry_queue()`

## 5. Tests

- [x] 5.1 Test `DialogueRetryQueue.enqueue`: items stored, attempt count preserved
- [x] 5.2 Test `DialogueRetryQueue.flush`: valid items re-submitted, max-retry items discarded with log, queue empty after flush
- [x] 5.3 Test `DialogueRetryQueue.notify_heartbeat`: no flush on normal heartbeat, flush triggered on gap >= 2x interval
- [x] 5.4 Test `DialogueRetryQueue` concurrent flush safety: two flush calls process items exactly once
- [x] 5.5 Test `DialogueGenerator` with retry queue: `StateQueryTimeout` enqueues instead of discarding, other exceptions still logged and discarded
- [x] 5.6 Test `DialogueGenerator` without retry queue (backward compat): `StateQueryTimeout` logged and discarded as before
- [x] 5.7 Run full test suite to verify no regressions

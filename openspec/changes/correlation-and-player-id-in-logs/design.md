## Decisions

### D1: Monotonic req_id assigned at WS router dispatch

A per-inbound-message `req_id` is assigned in `_process_message` and passed to the handler as a third positional argument. This lets every log line produced during a single request's lifecycle share the same ID.

**Why not UUID**: Monotonic integers are shorter in log lines, cheaper to generate, and sufficient since the service runs as a single process.

**Why at dispatch, not in handler**: Ensures the ID exists before any handler code runs, and centralises assignment in one place.

### D2: Handler signature becomes (payload, session_id, req_id)

All registered handlers change from `(payload, session_id)` to `(payload, session_id, req_id)`. This is a breaking internal change but all handlers are wired in `__main__.py` so the blast radius is contained.

### D3: dialogue_id stays inside the generator, assigned earlier

`dialogue_id` is conceptually different from `req_id` — a single `game.event` request might produce zero or one dialogues, and the `dialogue_id` is used on the wire (sent to Lua in the payload). We move its assignment from `_publish_dialogue` to the start of `_generate_dialogue_for_speaker` so all dialogue-pipeline logs can include it.

### D4: Consistent log prefix format

```
[R:{req_id}]                           — transport/dispatch level
[R:{req_id} S:{session_id}]            — handler entry, config, audio, heartbeat
[R:{req_id} S:{session_id} D#{did}]    — dialogue pipeline (speaker, LLM, publish)
[D#{did}]                              — retained only where req_id is unavailable (background tasks like memory compression triggered from asyncio.create_task)
```

When `session_id == "__default__"`, the `S:` segment is omitted for brevity.

### D5: req_id threaded through generator via parameter

`generate_from_event`, `generate_from_instruction`, and their callees accept `req_id: int | None = None`. This avoids global/contextvar complexity while keeping the change mechanical.

### D6: No Lua changes

The `req_id` is a Python service logging concern only. It is not included in WS payloads or Lua-side logs. Lua already has `[D#N]` prefixed logs keyed off the `dialogue_id` field in payloads, which remains unchanged.

## Risks & Trade-offs

| Risk | Mitigation |
|------|-----------|
| Handler signature change breaks tests | All handler mocks/tests updated in tasks; blast radius is ~6 handler functions + test wiring |
| Verbose log lines with three-segment prefix | S: segment omitted for default session; entire prefix is ~15 chars max |
| req_id counter overflow | Python int is arbitrary-precision; no practical limit |
| Memory compression logs lack req_id because they run in background tasks | Accept this — use `[D#N]` only for those; req_id is attached to the originating request log |

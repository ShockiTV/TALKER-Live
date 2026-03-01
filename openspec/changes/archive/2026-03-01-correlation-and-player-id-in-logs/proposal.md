## Why

Python service log lines are inconsistent: `_publish_dialogue` uses `[D#N]` correlation prefixes but upstream steps (event handling, speaker selection, LLM calls, memory compression) do not. session_id appears in some transport-level logs but never in the dialogue pipeline. When debugging a multi-session or multi-event scenario, it's impossible to correlate log lines across the full event→speaker→dialogue→publish chain without manual timestamp matching. Additionally, there is no per-request correlation ID — when two `game.event` messages arrive simultaneously, their interleaved log lines are indistinguishable.

## What Changes

- Introduce a per-request correlation ID (`req_id`) assigned at WS router dispatch time. This monotonic counter tags every log line produced while handling a single inbound message, enabling full lifecycle tracing from receipt through publish.
- Thread `dialogue_id` earlier in the pipeline — assign it at the start of `_generate_dialogue_for_speaker` (before state queries) and pass it through LLM calls, memory compression, and publish, so every log line in the chain carries `[D#N]`.
- Add `session_id` to key log lines so multi-session logs can be filtered by player.
- Adopt a consistent prefix format: `[R:N S:session D#M]` for lines that have all three contexts, with shorter prefixes when fewer contexts are available (e.g. `[R:N S:session]` for event receipt, `[R:N D#M]` for dialogue generation in default session).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `python-dialogue-generator`: Thread `dialogue_id` and `req_id` through the full generation pipeline and include correlation prefixes in all log lines from speaker selection through publish.

## Impact

- **talker_service/src/talker_service/transport/ws_router.py** — assign monotonic `req_id` at dispatch, pass to handlers
- **talker_service/src/talker_service/handlers/events.py** — accept and log `req_id`, pass to generator
- **talker_service/src/talker_service/dialogue/generator.py** — accept `req_id` param, assign `dialogue_id` earlier, log with `[R:N D#M]` prefix in all methods, include session_id in key log lines
- **talker_service/src/talker_service/handlers/config.py** — log `req_id` on config update/sync
- **talker_service/src/talker_service/handlers/audio.py** — log `req_id` on audio chunk handling
- **Python tests** — update any tests that assert on handler signatures or log output

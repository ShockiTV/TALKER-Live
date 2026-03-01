## Context

The mic capture system spans three layers: bridge (Python audio capture + VAD), service (Python STT + transcription), and Lua (game UI + state). Before this change, pressing the capture key during an active transcription session caused race conditions — stale audio contaminated new sessions, Lua state got stuck in wrong states when VAD auto-stopped capture, and the HUD showed incorrect status during overlapping capture+transcription.

The system was originally designed around a single-session model: one capture at a time, session-scoped handlers that cleaned up on `mic.result`. The toggle pattern (press to start, press to stop, press again while transcribing to start new) was not supported.

## Goals / Non-Goals

**Goals:**
- Support toggle-key interaction: idle→capture, capture→stop+transcribe, transcribing→new capture (overlap)
- Prevent stale audio from contaminating new sessions via session_id tracking at every layer
- Handle VAD silence auto-stop correctly — Lua must transition state even without a key press
- Display correct HUD status: "RECORDING" always wins over background transcription status
- Keep the mic channel usable for non-session-scoped handlers (permanent `on()` registration)

**Non-Goals:**
- Multi-tenant mic support (still single-player, single-mic)
- Changing the STT provider or transcription pipeline
- Modifying the WS proxy behaviour for non-mic topics
- Changing TTS playback or voice generation

## Decisions

### 1. Monotonic session_id at bridge layer
**Decision**: Bridge AudioStreamer assigns a monotonic integer `session_id` to each capture session. This ID propagates through `mic.audio.chunk`, `mic.audio.end`, `mic.result`, and `mic.status` payloads.

**Rationale**: Session IDs are the simplest way to correlate audio chunks with the correct session. Monotonic integers (vs UUIDs) are cheaper and provide natural ordering — the service can trivially detect stale data by comparing `session_id < _active_session_id`.

**Alternative considered**: UUID per session — rejected because ordering matters for stale detection and integers are simpler to compare.

### 2. Three-state toggle machine in recorder.lua
**Decision**: `recorder.lua` implements a three-state machine: `idle`, `capturing`, `transcribing`. The `toggle()` function moves between states based on current state. Permanent `bridge_channel.on()` handlers replace session-scoped `start_session()`.

**Rationale**: Toggle semantics match the user's mental model (one key does everything). Permanent handlers avoid the complexity of session-scoped cleanup — the state machine itself handles what to do with each incoming message based on current state.

**Alternative considered**: Keep session-scoped handlers with auto-cleanup — rejected because overlapping sessions (new capture while old transcription runs) requires handlers that survive across sessions.

### 3. Bridge publishes `mic.stopped` for VAD auto-stop only
**Decision**: When VAD detects silence and ends capture, the bridge publishes `mic.stopped` (with `reason: "vad"`) to Lua. Manual stops via key press do NOT trigger `mic.stopped` — Lua already knows it initiated the stop.

**Rationale**: Without `mic.stopped`, Lua's state machine would stay in `capturing` after VAD auto-stop, with no way to transition to `transcribing`. Only VAD needs this notification; manual stop is handled synchronously in `toggle()`.

### 4. HUD priority — RECORDING suppresses mic.status during capture
**Decision**: The `mic.status` handler in recorder.lua checks `_state == STATE_CAPTURING` and suppresses status updates. This ensures "RECORDING" (set by `toggle()`) is never overwritten by a background "TRANSCRIBING" status from a concurrent session.

**Rationale**: The user expects to see "RECORDING" while holding/pressing the key. Background transcription status arriving mid-capture would be confusing.

### 5. Thin microphone.lua wrapper
**Decision**: `microphone.lua` is a pure hardware abstraction — `start_capture()`, `stop_capture()`, `is_recording()`, `on_stopped()`. No state machine, no session management, no callbacks.

**Rationale**: Separation of concerns. The recorder owns the session lifecycle; the microphone just knows about hardware state. This makes both testable independently.

### 6. Remove `mic.cancel` topic
**Decision**: `mic.cancel` removed from bridge `LOCAL_TOPICS` and Lua API. Bridge's internal `cancel()` method kept only for shutdown cleanup.

**Rationale**: There is no cancel key in the game. The only code path that used cancel was unreachable. Keeping dead code increases confusion and maintenance burden.

## Risks / Trade-offs

**[Risk] Overlapping STT requests could overload the service** → Mitigated by session_id tracking — the service discards stale audio buffers when a new session starts, so at most one transcription runs at a time.

**[Risk] `mic.stopped` arrives after user already pressed key to stop** → Mitigated by `_stopped` flag in bridge — if manual stop was called, `mic.stopped` is not published. The flag is set synchronously before the capture loop checks it.

**[Trade-off] Permanent handlers vs session-scoped** → Permanent handlers are simpler but mean the recorder must guard against unexpected messages in wrong states (e.g., `mic.result` arriving in `idle` state). Handled by state checks in each handler.

## Context

The microphone system (`mic_python`) currently communicates with the game (Lua) via temp-file polling: Lua writes commands to `%TEMP%\talker_mic_io_commands`, a watchdog observer in Python detects the file change, and results are written back to `%TEMP%\talker_mic_io_transcription`. The game polls these files at 100ms intervals.

Meanwhile, all other game↔service communication uses ZeroMQ PUB/SUB on ports 5555 (Lua PUB) and 5556 (Python service PUB). The mic system is the only remaining file-based IPC path.

The mic_python process needs to remain a separate local process because: (1) audio capture requires hardware access to the local microphone, (2) transcription providers like Whisper API send audio directly to external APIs — routing through a remote server would add unnecessary latency and bandwidth, (3) mic_python's dependencies (sounddevice, faster-whisper) are hardware-specific and shouldn't be on a remote server.

## Goals / Non-Goals

**Goals:**
- Replace temp-file IPC between Lua and mic_python with ZMQ PUB/SUB
- mic_python becomes an independent ZMQ peer alongside talker_service
- Push-based status/result delivery instead of file polling
- Maintain all existing audio capture and transcription functionality unchanged
- Support mic_python running locally while talker_service runs remotely

**Non-Goals:**
- Merging mic_python into talker_service (explicitly rejected — different deployment targets)
- Changing the audio recording logic (recorder.py)
- Changing transcription providers (whisper_api, whisper_local, gemini_proxy)
- Adding new MCM settings for mic (existing settings sufficient)
- Streaming audio over ZMQ (mic_python captures and transcribes locally, sends text)

## Decisions

### 1. Independent ZMQ Peer Topology (over routing through talker_service)

mic_python will be an independent ZMQ peer that directly subscribes to Lua's PUB socket and publishes on its own port:

```
Lua PUB :5555 ──► talker_service SUB (existing)
               ──► mic_python SUB    (NEW: connects to :5555)

talker_service PUB :5556 ──► Lua SUB (existing, unchanged)
mic_python PUB :5557     ──► Lua SUB (NEW: second SUB socket in bridge)
```

**Why not route through talker_service?** That would create a hard dependency between mic_python and the talker_service — mic should work regardless of whether the service is local, remote, or even running. The mic is purely a local input device; it doesn't need the AI service to capture and transcribe audio.

**Why a separate port (5557) instead of sharing 5556?** ZMQ PUB sockets must be bound, not shared. Two processes can't bind the same port. mic_python needs its own PUB socket.

### 2. ZMQ Topic Format (consistent with existing conventions)

New topics follow the existing `<namespace>.<action>` pattern:

| Topic | Direction | Payload |
|---|---|---|
| `mic.start` | Lua → mic_python | `{ lang: string, prompt: string }` |
| `mic.stop` | Lua → mic_python | `{}` |
| `mic.status` | mic_python → Lua | `{ status: "LISTENING" \| "TRANSCRIBING" }` |
| `mic.result` | mic_python → Lua | `{ text: string }` |

Messages use the existing wire format: `<topic> <json-payload>` (no envelope wrapping — mic_python is a simple peer, not using the `{topic, payload, timestamp}` envelope that the bridge uses for talker_service messages). This keeps mic_python minimal.

**Alternative considered**: Using the envelope format `{topic, payload, timestamp}`. Rejected because mic_python is intentionally simple and the envelope adds complexity for no benefit (mic doesn't need timestamps or correlation IDs).

### 3. Dual SUB Socket in bridge.lua (over single SUB with multiple connections)

bridge.lua will manage two independent SUB sockets:
- **Primary SUB** → connects to talker_service PUB on :5556 (existing)
- **Mic SUB** → connects to mic_python PUB on :5557 (new)

Both are polled in `poll_commands()` with `ZMQ_DONTWAIT` — no blocking, no performance impact.

**Why not `zmq_connect()` twice on the same SUB socket?** ZMQ SUB sockets can connect to multiple endpoints, but we want different topic filtering and independent lifecycle management. The mic SUB socket should only subscribe to `mic.` topics and have separate failure handling from the talker_service SUB socket.

### 4. Synchronous ZMQ Loop in mic_python (over asyncio)

mic_python will use a simple synchronous `zmq.Context()` with blocking `recv()` (with timeout). No asyncio, no threading for ZMQ.

**Why?** The mic system is inherently sequential: wait for command → record → transcribe → send result. The recorder already uses its own background thread for audio capture. Adding asyncio would increase complexity with no benefit.

### 5. Topic-Based Subscription Filter (mic_python subscribes only to `mic.`)

mic_python's SUB socket will use `sub.subscribe(b"mic.")` instead of subscribing to all topics. This means it ignores game.event, config.sync, etc. — it only receives mic commands.

## Risks / Trade-offs

**[Port conflict]** → Port 5557 could conflict with other software. Mitigation: Make it configurable (command-line arg to mic_python, config in bridge.lua). Default 5557.

**[Dual SUB polling overhead]** → Polling two SUB sockets per game frame. Mitigation: Both use ZMQ_DONTWAIT; unmeasurably fast when no messages pending. ZMQ is designed for this.

**[mic_python not running]** → If mic_python isn't started, mic.start messages go nowhere (no SUB subscriber on :5555 for mic.* topics), and bridge.lua's mic SUB socket on :5557 has nothing to connect to. Mitigation: This is fine — ZMQ handles absent peers gracefully. The mic SUB socket will simply never receive messages. The game should display the status from the mic system (LISTENING/TRANSCRIBING), and if no status arrives, the UI should timeout and reset.

**[Message ordering / duplication]** → ZMQ PUB/SUB has at-most-once delivery. A mic.result could be lost if the game drops the message. Mitigation: Acceptable for mic — the user simply speaks again. No retry mechanism needed.

## Open Questions

None — the design is straightforward and all decisions were discussed during exploration.

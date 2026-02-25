## 1. Setup & Dependencies

- [x] 1.1 Add Whisper and PyTorch dependencies to `talker_service/pyproject.toml` (as optional `[stt]` extras)
- [x] 1.2 Add `webrtcvad` (or equivalent VAD library) to `talker_bridge` dependencies
- [x] 1.3 Remove Whisper and PyTorch dependencies from `talker_bridge` (formerly `mic_python`)

## 2. `talker_bridge` — WS Proxy

- [x] 2.1 Rename `mic_python` directory to `talker_bridge`; update launch scripts and documentation references
- [ ] 2.2 Implement upstream WS client connection from `talker_bridge` to `talker_service` (port 5557)
- [ ] 2.3 Implement transparent WS message proxying: Lua→service and service→Lua (forward all non-mic topics as-is)
- [ ] 2.4 Handle `mic.start` and `mic.cancel` topics locally (do not proxy to service)
- [ ] 2.5 Proxy `mic.result` and `mic.status` (TRANSCRIBING) from `talker_service` downstream to Lua

## 3. `talker_bridge` — Audio Capture & Streaming

- [ ] 3.1 Implement local VAD (using `webrtcvad` or energy-based threshold) for silence/end-of-speech detection
- [ ] 3.2 On `mic.start`: begin audio capture, send `mic.status` LISTENING to Lua
- [ ] 3.3 Stream base64-encoded audio chunks to `talker_service` as `mic.audio.chunk` messages (with sequence numbers)
- [ ] 3.4 On VAD silence detection or `mic.cancel`: send `mic.audio.end` (with context type) to `talker_service`
- [ ] 3.5 Remove old transcription logic and STT imports from `talker_bridge`

## 4. `talker_service` — STT Integration

- [ ] 4.1 Create `stt` package in `talker_service/src/talker_service/stt/`
- [ ] 4.2 Move `whisper_local.py` and `whisper_api.py` from `mic_python` to the new `stt` package
- [ ] 4.3 Add WS handler for `mic.audio.chunk` topic — buffer incoming audio chunks in order
- [ ] 4.4 Add WS handler for `mic.audio.end` topic — finalize buffer and trigger transcription
- [ ] 4.5 Send `mic.status` TRANSCRIBING and `mic.result` back through WS after transcription completes
- [ ] 4.6 Wire the transcription result to trigger the standard dialogue generation flow (`player.dialogue` or `player.whisper` based on context type)

## 5. Lua — Single Connection Migration

- [ ] 5.1 Remove `service-channel` (direct Lua→`talker_service` connection on port 5557)
- [ ] 5.2 Update `mic-channel` to carry all traffic (rename to bridge-channel or similar)
- [ ] 5.3 Route all outbound topics (`game.event`, `player.dialogue`, `config.update`, etc.) through the single bridge connection
- [ ] 5.4 Route all inbound topics (`dialogue.display`, `memory.update`, `state.query.batch`, etc.) from the bridge connection to existing handlers

## 6. Build & Packaging

- [ ] 6.1 Update `talker_bridge` build script to generate standalone `.exe` without heavy dependencies (no PyTorch/Whisper)
- [ ] 6.2 Rename launch scripts: `launch_mic.bat` → `launch_talker_bridge.bat` (or similar)

## 7. Documentation & Protocol

- [ ] 7.1 Update `docs/ws-api.yaml` to document `mic.audio.chunk`, `mic.audio.end` topics and the bridge proxy architecture
- [ ] 7.2 Update `docs/Python_Service_Setup.md` to explain the new required `talker_bridge` and optional STT dependencies for `talker_service`
- [ ] 7.3 Update `AGENTS.md` architecture section to reflect the bridge proxy architecture
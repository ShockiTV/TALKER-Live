# Local Development Setup — Using VPS Services

When you want to iterate on `talker_service` or `talker_bridge` code locally without deploying to VPS every time, use your VPS TTS and STT services via SSH tunnel.

## Quick Start

### Step 1: Start SSH Tunnel (keep running)

```bash
ssh -L 8100:localhost:8100 -L 8000:localhost:8000 user@your-vps.com
```

This creates:
- **Local port 8100** → tunneled to **VPS tts-service:8100**
- **Local port 8000** → tunneled to **VPS stt-service:8000**

### Step 2: Set Up Local `.env` Files

**For talker_service:**
```bash
cd talker_service
cp .env.local .env
notepad .env  # Fill in your API keys
```

**For talker_bridge:**
```bash
cd talker_bridge/python
cp .env.local .env
# (already configured for localhost:5557, no edits needed)
```

Note: `.env` files go in the **python subdirectory** where the scripts are located.

When you set `SERVICE_WS_URL` in bridge `.env.local`, it **pins** the upstream service URL. The bridge will NOT accept MCM overrides for this URL at runtime. This is server-authority — same pattern as the pins in `talker_service` (e.g., `LLM_PROVIDER` pins).

So your bridge stays connected to `localhost:5557` even if MCM tries to change it. Perfect for local dev!

### Step 3: Run Services

From the repo root, in two separate terminal windows:

**Terminal 1 — Python service:**
```bash
.\launch_talker_service.bat
```

**Terminal 2 — WS bridge:**
```bash
.\launch_talker_bridge.bat
```

You should see:
```
talker_service: WebSocket server running on ws://127.0.0.1:5557
```

```
talker_bridge: Proxying game traffic to ws://127.0.0.1:5557
              TTS: using remote http://localhost:8100
              STT: using remote http://localhost:8000/v1
```

### Step 4: Launch Game

From MO2, launch `Anomaly.exe` directly (not via Anomaly Launcher).

The game will connect to your local `talker_bridge`, which proxies to `talker_service`, which calls out to VPS (TTS/STT).

---

## Understanding Pins vs. MCM Override

The bridge has two modes:

| Mode | Behavior | Use Case |
|------|----------|----------|
| **Pinned** (`.env.local` has SERVICE_WS_URL) | Bridge connects to that URL, MCM cannot change it | Local dev — lock service URL to localhost |
| **Unpinned** (`.env.local` empty or no SERVICE_WS_URL) | Uses default (VPS), MCM can override at runtime | Production — MCM has full control |

**For local dev, you want PINNED** — that's already set in `.env.local`:
```
SERVICE_WS_URL=ws://127.0.0.1:5557/ws  ← Pins to localhost
```

If you need to unpin and test MCM override behavior, comment it out:
```
# SERVICE_WS_URL=ws://127.0.0.1:5557/ws  ← Commented out, unpinned
```

---

**Edit talker_service code:**
```bash
# Make changes in talker_service/src/...
# Then restart:
# Ctrl+C in Terminal 1
# .\launch_talker_service.bat  (restarts)
```

**Edit talker_bridge code:**
```bash
# Make changes in talker_bridge/python/...
# Then restart:
# Ctrl+C in Terminal 2
# .\launch_talker_bridge.bat  (restarts)
```

**Edit Lua code (gamedata/scripts/, bin/lua/):**
```bash
# No restart needed—just reload game save
```

---

## Troubleshooting

### SSH tunnel fails to connect
```bash
ssh -v -L 8100:localhost:8100 -L 8000:localhost:8000 user@your-vps.com
```
(add `-v` for verbose output)

### "ConnectionRefusedError: 8100"
- SSH tunnel is not running
- Or tunnel died silently (reconnect)

### "Cannot connect to LLM provider"
- Check `OPENAI_API_KEY` in `.env`
- Check `LLM_TIMEOUT` (increase if slow network)

### TTS returns garbage audio
- SSH tunnel is laggy
- Check VPS `docker compose logs tts-service`

### STT not working
- Check STT_ENDPOINT in `.env` — should be `http://localhost:8000/v1`
- Check VPS `docker compose logs stt-service`

---

## Cleanup

When done:
1. **Ctrl+C** both terminals
2. **Close SSH tunnel** (Ctrl+C or close terminal)
3. (Leave `.env.local` in place for next session — it's in `.gitignore`)


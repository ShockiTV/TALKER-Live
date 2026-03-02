import sys
import os
import re
import time
import logging
import json
import base64
import io
import threading
import asyncio
import numpy as np
import soundfile as sf
import websockets
from pathlib import Path
from dotenv import load_dotenv

# Load env config with fallback: explicit override > .env.local > .env
env_local = Path(__file__).parent / ".env.local"
env_file = Path(__file__).parent / ".env"
env_override = os.environ.get("TALKER_BRIDGE_ENV_FILE", "").strip()
if env_override:
    load_dotenv(Path(env_override), override=True)
elif env_local.exists():
    load_dotenv(env_local, override=True)
elif env_file.exists():
    load_dotenv(env_file, override=True)

from banner import print_banner

####################################################################################################
# CONFIG
####################################################################################################

logging.basicConfig(
    level=getattr(logging, os.environ.get("BRIDGE_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("talker.log", encoding="utf-8"),
    ],
)

BRIDGE_WS_PORT = 5558       # talker_bridge WS server ← Lua connects here

# Default upstream URL — can be pinned via env to override MCM
_DEFAULT_SERVICE_URL = "wss://talker-live.duckdns.org/ws"
_PINNED_SERVICE_URL = os.environ.get("SERVICE_WS_URL", "").strip()  # if set, MCM cannot override
_service_url: str = _PINNED_SERVICE_URL or _DEFAULT_SERVICE_URL  # mutable if not pinned
_service_token: str = ""                  # auth token from MCM (ws_token)
_service_url_last_forwarded: str = ""     # Cache: track the last *forwarded* config to avoid re-closing
_service_token_last_forwarded: str = ""   # Cache for token

# Topics handled locally by the bridge (not proxied upstream)
LOCAL_TOPICS = {"mic.start", "mic.stop"}

# Topics proxied from talker_service downstream to Lua (transparent)
# (All service→bridge messages are forwarded to Lua by default)

# Audio streaming config
AUDIO_CHUNK_DURATION_MS = 200   # send a chunk every 200 ms
AUDIO_SAMPLE_RATE = 16000       # 16 kHz mono int16
VAD_SILENCE_THRESHOLD_S = 2.0  # seconds of silence before auto-stop
VAD_ENERGY_LEVEL = 1000        # energy threshold for silence detection


####################################################################################################
# WEBSOCKET STATE
####################################################################################################

_lua_ws       = None   # The single connected Lua game-client WebSocket
_service_ws   = None   # Upstream WebSocket to talker_service
_event_loop   = None   # asyncio loop reference (for thread→async sends)


def publish_to_lua(topic: str, payload: dict) -> None:
    """Send a JSON envelope {t, p, ts} to the connected Lua client via WebSocket."""
    if _lua_ws is None:
        logging.warning("No Lua client connected — dropping: %s", topic)
        return
    envelope = json.dumps({"t": topic, "p": payload, "ts": int(time.time() * 1000)})
    try:
        asyncio.run_coroutine_threadsafe(_lua_ws.send(envelope), _event_loop)
    except Exception:
        logging.warning("Failed to send WS message to Lua: %s", topic)


async def send_to_service(topic: str, payload: dict) -> None:
    """Send a JSON envelope to talker_service upstream."""
    if _service_ws is None:
        logging.warning("No service connection — dropping: %s", topic)
        return
    envelope = json.dumps({"t": topic, "p": payload, "ts": int(time.time() * 1000)})
    try:
        await _service_ws.send(envelope)
    except Exception:
        logging.warning("Failed to send WS message to service: %s", topic)


async def forward_raw_to_service(raw: str) -> None:
    """Forward a raw JSON string to talker_service."""
    if _service_ws is None:
        topic = "unknown"
        try:
            topic = json.loads(raw).get("t", "unknown")
        except Exception:
            pass
        logging.warning("No service connection — dropping proxied topic: %s", topic)
        return
    try:
        logging.debug("Forwarding to service: %s bytes", len(raw))
        await _service_ws.send(raw)
        logging.debug("Sent to service successfully")
    except websockets.ConnectionClosed:
        logging.debug("Service connection closed during forward (normal during reconnect)")
    except Exception as exc:
        logging.warning("Failed to forward message to service: %s", exc)


async def forward_raw_to_lua(raw: str) -> None:
    """Forward a raw JSON string from talker_service to Lua."""
    if _lua_ws is None:
        logging.debug("No Lua client — dropping service message")
        return
    try:
        await _lua_ws.send(raw)
    except Exception:
        logging.warning("Failed to forward message to Lua")


####################################################################################################
# SERVICE URL CONFIGURATION (MCM-driven)
####################################################################################################

def mask_token(url: str) -> str:
    """Mask the token query parameter in a URL for safe logging."""
    if "token=" not in url:
        return url
    return re.sub(r"token=[^&]*", "token=***", url)


def _build_service_url(base_url: str, token: str) -> str:
    """Build the full upstream URL, appending ?token=<token> if non-empty."""
    if not base_url:
        base_url = _DEFAULT_SERVICE_URL
    url = base_url.rstrip("/")
    if token and "token=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}token={token}"
    return url


def _apply_mcm_service_config(service_url: str | None, ws_token: str | None) -> None:
    """Update the upstream URL from MCM values and trigger reconnect if changed.
    
    If SERVICE_WS_URL is set in .env.local, it is pinned and MCM cannot override it
    (server-authority pattern, like talker_service pins).
    
    Uses caching to avoid redundant config processing when receiving duplicate
    config.sync messages in rapid succession.
    """
    global _service_url, _service_token, _service_ws
    global _service_url_last_forwarded, _service_token_last_forwarded

    # If SERVICE_WS_URL is pinned in env, ignore MCM service_url
    if _PINNED_SERVICE_URL:
        new_url = _PINNED_SERVICE_URL
    else:
        new_url = (service_url or "").strip() or _DEFAULT_SERVICE_URL
    
    new_token = (ws_token or "").strip()

    # **EARLY RETURN**: If this exact config was already forwarded, skip processing
    # This prevents redundant connection closes when rapid config.sync messagesarrive
    if new_url == _service_url_last_forwarded and new_token == _service_token_last_forwarded:
        logging.debug("Config identical to last forwarded—skipping redundant apply_mcm_service_config")
        return

    # Now compute the full URLs for comparison with current running config
    old_full = _build_service_url(_service_url, _service_token)
    new_full = _build_service_url(new_url, new_token)

    if old_full == new_full:
        logging.debug("No config change detected (old=%s, new=%s)", mask_token(old_full), mask_token(new_full))
        # Still update the cache so we don't reprocess this same config again
        _service_url_last_forwarded = new_url
        _service_token_last_forwarded = new_token
        return  # no change

    _service_url = new_url
    _service_token = new_token
    _service_url_last_forwarded = new_url
    _service_token_last_forwarded = new_token

    logging.info("Service URL updated → %s", mask_token(new_full))

    # Close current connection — service_reader() retry loop will reconnect
    ws = _service_ws
    if ws is not None:
        logging.debug("Closing service connection to trigger reconnect")
        try:
            asyncio.ensure_future(ws.close())
        except Exception as exc:
            logging.warning("Error scheduling service close: %s", exc)



####################################################################################################
# AUDIO CAPTURE & STREAMING (VAD-based)
####################################################################################################


class AudioStreamer:
    """Captures audio, runs local VAD (energy-based), and streams chunks upstream.

    The mic device is the only exclusive resource — one capture at a time.
    Transcription/LLM/TTS run concurrently in the background.

    - start()  — begin new capture (supersedes any active capture)
    - stop()   — graceful stop: end capture, trigger transcription
    - cancel() — hard cancel: discard captured audio
    """

    def __init__(self):
        self._recording = False
        self._seq = 0
        self._session_id = 0
        self._context_type = "dialogue"
        self._cancelled = False         # per-session cancel flag
        self._stopped = False           # per-session manual stop flag
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, context_type: str = "dialogue") -> None:
        """Begin audio capture in a background thread.

        If already recording, the old capture is superseded (no end signal).
        """
        with self._lock:
            if self._recording:
                # Supersede old capture — old thread will detect session mismatch
                self._recording = False
            self._session_id += 1
            self._recording = True
            self._cancelled = False
            self._stopped = False
            self._seq = 0
            self._context_type = context_type
            sid = self._session_id

        publish_to_lua("mic.status", {"status": "RECORDING", "session_id": sid})
        threading.Thread(target=self._capture_loop, args=(sid,), daemon=True).start()

    def stop(self) -> None:
        """Graceful stop — end capture, send mic.audio.end, trigger transcription."""
        with self._lock:
            if not self._recording:
                return
            self._stopped = True      # distinguish from VAD
            self._recording = False
            # Don't set _cancelled — thread will send mic.audio.end normally
        logging.info("Recording stopped (graceful)")

    def cancel(self) -> None:
        """Hard cancel — discard captured audio, suppress mic.audio.end."""
        with self._lock:
            if not self._recording:
                return
            self._cancelled = True
            self._recording = False
        logging.info("Recording cancelled")

    def _capture_loop(self, my_session_id: int) -> None:
        """Record audio, stream chunks, detect silence, send end signal.

        Exit reasons:
        - VAD silence detected → send mic.audio.end (trigger transcription)
        - stop() called        → send mic.audio.end (trigger transcription)
        - cancel() called      → suppress mic.audio.end (discard)
        - superseded by start() → suppress mic.audio.end (new session took over)
        """
        import numpy as np
        import sounddevice as sd

        chunk_samples = int(AUDIO_SAMPLE_RATE * AUDIO_CHUNK_DURATION_MS / 1000)
        silence_start = None
        grace_end = time.time() + 0.5  # 500ms grace period

        superseded = False
        cancelled = False
        stopped = False     # manual stop() — Lua already knows

        try:
            stream = sd.InputStream(samplerate=AUDIO_SAMPLE_RATE, channels=1,
                                    dtype="int16", blocksize=chunk_samples)
            stream.start()
            logging.info("Audio capture started (session=%d)", my_session_id)

            while True:
                with self._lock:
                    if self._session_id != my_session_id:
                        superseded = True
                        break
                    if not self._recording:
                        cancelled = self._cancelled
                        stopped = self._stopped
                        break

                data, overflowed = stream.read(chunk_samples)
                if overflowed:
                    logging.debug("Audio buffer overflowed")

                # Stream chunk to service (OGG/Vorbis compressed)
                self._seq += 1
                ogg_buf = io.BytesIO()
                sf.write(ogg_buf, data, AUDIO_SAMPLE_RATE,
                         format="OGG", subtype="VORBIS")
                audio_b64 = base64.b64encode(ogg_buf.getvalue()).decode("ascii")
                asyncio.run_coroutine_threadsafe(
                    send_to_service("mic.audio.chunk", {
                        "audio_b64": audio_b64,
                        "seq": self._seq,
                        "format": "ogg",
                        "session_id": my_session_id,
                    }),
                    _event_loop,
                )

                # Local VAD: energy-based silence detection
                energy = np.abs(data).mean()
                now = time.time()

                if now < grace_end:
                    silence_start = None
                elif energy < VAD_ENERGY_LEVEL:
                    if silence_start is None:
                        silence_start = now
                    elif (now - silence_start) >= VAD_SILENCE_THRESHOLD_S:
                        logging.info("VAD: silence detected (session=%d)", my_session_id)
                        break
                else:
                    silence_start = None

            stream.stop()
            stream.close()
        except Exception:
            logging.exception("Error during audio capture (session=%d)", my_session_id)
        finally:
            with self._lock:
                if self._session_id == my_session_id:
                    self._recording = False

        # Determine whether to send the end signal
        if superseded or cancelled:
            logging.info("Audio session %d ended without transcription (superseded=%s, cancelled=%s)",
                         my_session_id, superseded, cancelled)
            return

        # Notify Lua that the mic hardware stopped capturing.
        # For manual stop() Lua already set its state; only VAD needs this.
        if not stopped:
            publish_to_lua("mic.stopped", {"reason": "vad", "session_id": my_session_id})

        # Graceful end (VAD silence or stop()) → trigger transcription
        asyncio.run_coroutine_threadsafe(
            send_to_service("mic.audio.end", {
                "context": {"type": self._context_type},
                "session_id": my_session_id,
            }),
            _event_loop,
        )
        logging.info("Audio stream ended (session=%d, seq=%d, context=%s)",
                     my_session_id, self._seq, self._context_type)


####################################################################################################
# UPSTREAM SERVICE CONNECTION
####################################################################################################

async def service_reader():
    """Read messages from talker_service and forward them to Lua."""
    global _service_ws
    while True:
        url = _build_service_url(_service_url, _service_token)
        try:
            async with websockets.connect(url) as ws:
                _service_ws = ws
                logging.info("Connected to talker_service at %s", mask_token(url))
                async for raw in ws:
                    # Forward all service messages to Lua transparently
                    await forward_raw_to_lua(raw)
        except websockets.ConnectionClosed:
            logging.warning("Service connection closed — reconnecting in 3s")
        except (ConnectionRefusedError, OSError) as exc:
            logging.debug("Service not available (%s) — retrying in 3s", exc)
        except Exception:
            logging.exception("Service reader error — retrying in 3s")
        finally:
            _service_ws = None
        await asyncio.sleep(3)


####################################################################################################
# MAIN
####################################################################################################

def main() -> None:
    print("-" * 50)
    print_banner("TALKER")
    print("-" * 50)

    # ── Audio streamer ──────────────────────────────────────
    audio_streamer = AudioStreamer()

    # ── Local message handler (mic + TTS topics only) ───────
    async def handle_local_message(topic: str, payload: dict) -> None:
        """Handle topics that the bridge processes locally."""

        if topic == "mic.start":
            context_type = payload.get("context_type", "dialogue")
            audio_streamer.start(context_type)

        elif topic == "mic.stop":
            audio_streamer.stop()    # graceful: trigger transcription


    # ── Lua WebSocket handler (downstream) ──────────────────
    async def lua_ws_handler(websocket):
        global _lua_ws
        if _lua_ws is not None:
            await websocket.close(4000, "Only one connection allowed")
            logging.warning("Rejected second Lua connection")
            return

        _lua_ws = websocket
        logging.info("Lua game client connected")
        try:
            logging.debug("Entering message loop")
            message_count = 0
            async for raw in websocket:
                message_count += 1
                logging.debug("Received raw message #%d: %s bytes", message_count, len(raw))
                envelope = None
                topic = None
                try:
                    # Parse JSON envelope
                    try:
                        envelope = json.loads(raw)
                        topic = envelope.get("t")
                        if not topic:
                            logging.warning("WS frame missing 't' field")
                            continue
                    except (json.JSONDecodeError, TypeError) as exc:
                        logging.warning("Malformed WS frame from Lua: %s | %s", str(raw)[:80], exc)
                        continue  # Skip malformed, continue to next message
                    
                    # Extract payload safely
                    payload = envelope.get("p", {})
                    
                    # Route message based on topic
                    try:
                        if topic in LOCAL_TOPICS:
                            # Handle locally (mic control, TTS)
                            await handle_local_message(topic, payload)
                        elif topic == "config.sync":
                            # Peek at full config for service_url / ws_token, then proxy
                            logging.debug("Processing config.sync (#%d)", message_count)
                            try:
                                _apply_mcm_service_config(
                                    payload.get("service_url"),
                                    payload.get("ws_token"),
                                )
                                logging.debug("Config applied")
                            except Exception:
                                logging.exception("Error applying MCM config (continuing)")
                            # Always forward to service, even if config apply failed
                            await forward_raw_to_service(raw)
                            logging.debug("config.sync forwarded to service")
                        elif topic == "config.update":
                            # Peek at individual key change, then proxy
                            key = payload.get("key", "")
                            if key in ("service_url", "ws_token"):
                                # Fetch latest values — for a single key change we
                                # only update that one field, keeping the other as-is
                                val = payload.get("value", "")
                                try:
                                    if key == "service_url":
                                        _apply_mcm_service_config(val, _service_token)
                                    else:
                                        _apply_mcm_service_config(_service_url, val)
                                except Exception:
                                    logging.exception("Error applying MCM config update (continuing)")
                            await forward_raw_to_service(raw)
                        else:
                            # Proxy transparently to talker_service
                            if topic == "game.event":
                                logging.info("Proxying game.event to service")
                            await forward_raw_to_service(raw)
                        
                        logging.debug("Processed topic=%s (message #%d)", topic, message_count)
                    except Exception:
                        logging.exception("Error routing message (topic=%s)", topic)
                        # Don't re-raise — continue processing next message
                
                except Exception:
                    # Outer catch-all for ANY exception in message handling
                    logging.exception("FATAL: Uncaught exception in message processing (topic=%s)", topic)
                    # Don't re-raise — stay connected and process next message

            
            logging.debug("Message loop exited normally (websocket closed by client)")

        except websockets.ConnectionClosed:
            logging.info("Lua game client disconnected")
        except Exception:
            logging.exception("Fatal error in Lua WS handler")
        finally:
            logging.info("Lua handler exiting, cleaning up")
            _lua_ws = None

    # ── Launch ──────────────────────────────────────────────
    async def run():
        global _event_loop
        _event_loop = asyncio.get_running_loop()

        # Start upstream service reader (auto-reconnects)
        asyncio.create_task(service_reader())

        # Start downstream Lua-facing server
        async with websockets.serve(lua_ws_handler, "0.0.0.0", BRIDGE_WS_PORT):
            logging.info("Bridge WS server listening on ws://0.0.0.0:%d", BRIDGE_WS_PORT)
            startup_url = _build_service_url(_service_url, _service_token)
            logging.info("Proxying to talker_service at %s", mask_token(startup_url))
            print("TALKER Bridge ready. Waiting for game connection...")
            await asyncio.Future()  # run forever

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logging.info("User interrupt.")
    except Exception:
        logging.exception("Unhandled error.")
    finally:
        if audio_streamer.is_recording:
            audio_streamer.cancel()
        logging.info("Shutdown complete.")


if __name__ == "__main__":
    main()

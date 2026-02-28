import sys
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

from banner import print_banner

####################################################################################################
# CONFIG
####################################################################################################

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("talker.log", encoding="utf-8"),
    ],
)

BRIDGE_WS_PORT = 5558       # talker_bridge WS server ← Lua connects here
SERVICE_WS_URL = "ws://127.0.0.1:5557/ws"  # upstream talker_service

# Topics handled locally by the bridge (not proxied upstream)
LOCAL_TOPICS = {"mic.start", "mic.cancel", "mic.stop"}

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
        logging.debug("No service connection — queuing not implemented, dropping message")
        return
    try:
        await _service_ws.send(raw)
    except Exception:
        logging.warning("Failed to forward message to service")


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
# AUDIO CAPTURE & STREAMING (VAD-based)
####################################################################################################


class AudioStreamer:
    """Captures audio, runs local VAD (energy-based), and streams chunks upstream."""

    def __init__(self):
        self._recording = False
        self._seq = 0
        self._context_type = "dialogue"  # "dialogue" or "whisper"
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, context_type: str = "dialogue") -> None:
        """Begin audio capture + streaming in a background thread."""
        with self._lock:
            if self._recording:
                return
            self._recording = True
            self._seq = 0
            self._context_type = context_type

        publish_to_lua("mic.status", {"status": "LISTENING"})
        threading.Thread(target=self._capture_loop, daemon=True).start()

    def cancel(self) -> None:
        """Cancel the current recording session."""
        with self._lock:
            if not self._recording:
                return
            self._recording = False
        logging.info("Recording cancelled")

    def _capture_loop(self) -> None:
        """Record audio, stream chunks, detect silence, send end signal."""
        import numpy as np
        import sounddevice as sd

        chunk_samples = int(AUDIO_SAMPLE_RATE * AUDIO_CHUNK_DURATION_MS / 1000)
        silence_start = None
        grace_end = time.time() + 0.5  # 500ms grace period

        try:
            stream = sd.InputStream(samplerate=AUDIO_SAMPLE_RATE, channels=1,
                                    dtype="int16", blocksize=chunk_samples)
            stream.start()
            logging.info("Audio capture started")

            while True:
                with self._lock:
                    if not self._recording:
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
                    }),
                    _event_loop,
                )

                # Local VAD: energy-based silence detection
                energy = np.abs(data).mean()
                now = time.time()

                if now < grace_end:
                    # Grace period — ignore silence
                    silence_start = None
                elif energy < VAD_ENERGY_LEVEL:
                    if silence_start is None:
                        silence_start = now
                    elif (now - silence_start) >= VAD_SILENCE_THRESHOLD_S:
                        logging.info("VAD: silence detected, ending recording")
                        break
                else:
                    silence_start = None

            stream.stop()
            stream.close()
        except Exception:
            logging.exception("Error during audio capture")
        finally:
            with self._lock:
                self._recording = False

        # Send end-of-audio signal to service
        asyncio.run_coroutine_threadsafe(
            send_to_service("mic.audio.end", {
                "context": {"type": self._context_type},
            }),
            _event_loop,
        )
        logging.info("Audio stream ended (seq=%d, context=%s)", self._seq, self._context_type)


####################################################################################################
# UPSTREAM SERVICE CONNECTION
####################################################################################################

async def service_reader():
    """Read messages from talker_service and forward them to Lua."""
    global _service_ws
    while True:
        try:
            async with websockets.connect(SERVICE_WS_URL) as ws:
                _service_ws = ws
                logging.info("Connected to talker_service at %s", SERVICE_WS_URL)
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

        elif topic in ("mic.cancel", "mic.stop"):
            audio_streamer.cancel()

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
            async for raw in websocket:
                try:
                    envelope = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    logging.warning("Malformed WS frame from Lua: %s", str(raw)[:80])
                    continue

                topic = envelope.get("t")
                if not topic:
                    logging.warning("WS frame missing 't' field")
                    continue

                payload = envelope.get("p", {})

                if topic in LOCAL_TOPICS:
                    # Handle locally (mic control, TTS)
                    await handle_local_message(topic, payload)
                else:
                    # Proxy transparently to talker_service
                    await forward_raw_to_service(raw)

        except websockets.ConnectionClosed:
            logging.info("Lua game client disconnected")
        finally:
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
            logging.info("Proxying to talker_service at %s", SERVICE_WS_URL)
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

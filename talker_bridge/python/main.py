import sys
import time
import logging
import json
import base64
import threading
from collections import deque

import asyncio

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
LOCAL_TOPICS = {"mic.start", "mic.cancel", "mic.stop", "tts.speak"}

# Topics proxied from talker_service downstream to Lua (transparent)
# (All service→bridge messages are forwarded to Lua by default)

# Audio streaming config
AUDIO_CHUNK_DURATION_MS = 200   # send a chunk every 200 ms
AUDIO_SAMPLE_RATE = 16000       # 16 kHz mono int16
VAD_SILENCE_THRESHOLD_S = 2.0  # seconds of silence before auto-stop
VAD_ENERGY_LEVEL = 1000        # energy threshold for silence detection


####################################################################################################
# TTS QUEUE
####################################################################################################


class TTSQueue:
    """FIFO queue for TTS playback tasks.

    Only one TTS task plays at a time.  New tasks are queued and automatically
    started when the current one finishes.  STT is handled independently on its
    own thread so recording always works — even during TTS playback.
    """

    def __init__(self):
        self._queue: deque = deque()
        self._busy: bool = False
        self._lock = threading.Lock()

    @property
    def busy(self) -> bool:
        return self._busy

    def submit(self, task: dict) -> None:
        """Submit a TTS task.  Starts immediately when idle, queues otherwise."""
        with self._lock:
            if not self._busy:
                self._busy = True
                threading.Thread(target=self._execute, args=(task,), daemon=True).start()
            else:
                self._queue.append(task)
                logging.debug(
                    "TTS task queued — queue depth %d",
                    len(self._queue),
                )

    def _execute(self, task: dict) -> None:
        try:
            _run_tts_task(task)
        except Exception:
            logging.exception("Unhandled error executing TTS task")
        finally:
            with self._lock:
                if self._queue:
                    next_task = self._queue.popleft()
                    threading.Thread(target=self._execute, args=(next_task,), daemon=True).start()
                else:
                    self._busy = False


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

                # Stream chunk to service
                self._seq += 1
                audio_b64 = base64.b64encode(data.tobytes()).decode("ascii")
                asyncio.run_coroutine_threadsafe(
                    send_to_service("mic.audio.chunk", {
                        "audio_b64": audio_b64,
                        "seq": self._seq,
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
# TTS HELPERS
####################################################################################################

def load_voice_cache(voices_dir: str) -> "tuple[dict, object]":
    """Load all *.safetensors files in voices_dir into a dict keyed by voice_id (filename stem).

    Returns (cache, model). Both are empty/None if pocket-tts is unavailable or no files found.
    """
    import os
    import glob

    try:
        from pocket_tts import TTSModel
    except ImportError:
        logging.error(
            "pocket-tts is not installed — TTS disabled. "
            "Run export_voices.bat to install it."
        )
        return {}, None

    # Search both flat root (voices/bandit_1.safetensors) and subdirs
    # (voices/bandit_1/bandit_1.safetensors — Anomaly structure).
    files = sorted(
        glob.glob(os.path.join(voices_dir, "*.safetensors")) +
        glob.glob(os.path.join(voices_dir, "**", "*.safetensors"), recursive=True)
    )
    files = list(dict.fromkeys(files))  # deduplicate, preserve order
    if not files:
        logging.warning("No .safetensors voice files found in %s", voices_dir)
        return {}, None

    logging.info("Loading TTS model…")
    model = TTSModel.load_model()

    cache: dict = {}
    for path in files:
        voice_id = os.path.splitext(os.path.basename(path))[0]
        try:
            voice_state = model.get_state_for_audio_prompt(path)
            cache[voice_id] = voice_state
            logging.info("  Loaded voice: %s", voice_id)
        except Exception as exc:
            logging.error("  Failed to load voice %s: %s", voice_id, exc)

    logging.info("Voice cache ready: %d voice(s) loaded", len(cache))
    return cache, model


def play_tts(text: str, voice_state: object, model: object) -> None:
    """Stream TTS audio to the default audio output via sounddevice."""
    import sounddevice as sd

    with sd.OutputStream(samplerate=24000, channels=1, dtype="float32") as stream:
        for chunk in model.generate_audio_stream(voice_state, text):
            stream.write(chunk.numpy())


def _run_tts_task(task: dict) -> None:
    """Execute a TTS playback task."""
    voice_state = task["voice_state"]
    text: str   = task["text"]
    speaker_id: str = task.get("speaker_id", "")

    publish_to_lua("tts.started", {"speaker_id": speaker_id})
    try:
        play_tts(text, voice_state, task["model"])
    except Exception as exc:
        logging.error("TTS playback failed: %s", exc)
    finally:
        publish_to_lua("tts.done", {"speaker_id": speaker_id})


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

    # ── Argument parsing ────────────────────────────────────
    tts_enabled = "--tts" in sys.argv[1:]

    if tts_enabled:
        logging.info("TTS mode enabled (--tts)")

    # ── Audio streamer ──────────────────────────────────────
    audio_streamer = AudioStreamer()

    # ── TTS startup ─────────────────────────────────────────
    voice_cache: dict = {}
    tts_model = None
    if tts_enabled:
        import os

        voices_dir = os.path.join(os.path.dirname(__file__), "..", "voices")
        voice_cache, tts_model = load_voice_cache(voices_dir)
        if not voice_cache:
            logging.warning(
                "TTS enabled but no voices loaded. "
                "Add .wav files to talker_bridge/voices/ and run export_voices.bat."
            )

    tts_queue = TTSQueue()

    # ── Local message handler (mic + TTS topics only) ───────
    async def handle_local_message(topic: str, payload: dict) -> None:
        """Handle topics that the bridge processes locally."""

        if topic == "mic.start":
            context_type = payload.get("context_type", "dialogue")
            audio_streamer.start(context_type)

        elif topic in ("mic.cancel", "mic.stop"):
            audio_streamer.cancel()

        elif topic == "tts.speak" and tts_enabled:
            voice_id   = payload.get("voice_id", "")
            text       = payload.get("text", "")
            speaker_id = payload.get("speaker_id", "")
            logging.info("tts.speak  speaker=%s  voice=%s  text=%.60s",
                         speaker_id, voice_id or "(none)", text)

            if not text:
                logging.warning("tts.speak received with empty text — skipping")
                publish_to_lua("tts.done", {"speaker_id": speaker_id})
                return

            voice_state = voice_cache.get(voice_id)
            if voice_state is None:
                if voice_cache:
                    fallback_id = next(iter(voice_cache))
                    logging.warning(
                        "voice_id '%s' not in cache — falling back to '%s'",
                        voice_id,
                        fallback_id,
                    )
                    voice_state = voice_cache[fallback_id]
                else:
                    logging.error("tts.speak: voice cache empty, cannot play TTS")
                    publish_to_lua("tts.done", {"speaker_id": speaker_id})
                    return

            tts_queue.submit({
                "model":       tts_model,
                "voice_state": voice_state,
                "text":        text,
                "speaker_id":  speaker_id,
            })

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
            if tts_enabled:
                print("TTS enabled — NPCs will speak their dialogue aloud.")
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

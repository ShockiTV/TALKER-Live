import sys
import time
import logging
import json
import importlib
import threading
from collections import deque

import asyncio

import websockets

from recorder import Recorder
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

MIC_WS_PORT = 5558  # mic_python WS server ← Lua mic channel connects here
AUDIO_FILE = "talker_audio.ogg"

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
# STT HELPERS
####################################################################################################

# ── WebSocket connection state ──────────────────────────────────────────────────

_ws_connection = None   # The single connected game-client WebSocket
_event_loop    = None   # asyncio loop reference (for thread→async sends)


def publish(topic: str, payload: dict) -> None:
    """Send a JSON envelope {t, p, ts} to the connected game client via WebSocket."""
    if _ws_connection is None:
        logging.warning("No WS client connected — dropping: %s", topic)
        return
    envelope = json.dumps({"t": topic, "p": payload, "ts": int(time.time() * 1000)})
    try:
        asyncio.run_coroutine_threadsafe(_ws_connection.send(envelope), _event_loop)
    except Exception:
        logging.warning("Failed to send WS message: %s", topic)


def _run_stt_task(task: dict) -> None:
    """Execute a speech-to-text recording task."""
    recorder: Recorder   = task["recorder"]
    transcribe_func      = task["transcribe"]
    lang: "str | None"   = task.get("lang")
    prompt: str          = task.get("prompt", "")

    publish("mic.status", {"status": "LISTENING"})
    recorder.start_recording()
    while recorder.is_recording():
        time.sleep(0.1)

    publish("mic.status", {"status": "TRANSCRIBING"})
    try:
        text = transcribe_func(AUDIO_FILE, prompt=prompt, lang=lang)
    except Exception as exc:
        logging.error("Transcription failed: %s", exc)
        text = ""
    publish("mic.result", {"text": text})


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
    """Stream TTS audio to the default audio output via sounddevice.

    Opens an sd.OutputStream at 24 kHz mono float32 and writes chunks as
    they are generated by model.generate_audio_stream().
    """
    import sounddevice as sd

    with sd.OutputStream(samplerate=24000, channels=1, dtype="float32") as stream:
        for chunk in model.generate_audio_stream(voice_state, text):
            stream.write(chunk.numpy())


def _run_tts_task(task: dict) -> None:
    """Execute a TTS playback task."""
    voice_state = task["voice_state"]
    text: str   = task["text"]
    speaker_id: str = task.get("speaker_id", "")

    publish("tts.started", {"speaker_id": speaker_id})
    try:
        play_tts(text, voice_state, task["model"])
    except Exception as exc:
        logging.error("TTS playback failed: %s", exc)
    finally:
        publish("tts.done", {"speaker_id": speaker_id})


####################################################################################################
# MAIN
####################################################################################################

def main() -> None:
    print("-" * 50)
    print_banner("TALKER")
    print("-" * 50)

    # ── Argument parsing ────────────────────────────────────
    provider = "gemini_proxy"
    tts_enabled = False

    for arg in sys.argv[1:]:
        if arg == "--tts":
            tts_enabled = True
        elif arg in ("whisper_local", "whisper_api", "gemini_proxy"):
            provider = arg

    logging.info("Using transcription provider: %s", provider)
    if tts_enabled:
        logging.info("TTS mode enabled (--tts)")

    # ── Load transcription provider ─────────────────────────
    transcription_module = importlib.import_module(provider)
    load_api_key = getattr(transcription_module, "load_openai_api_key")
    transcribe_audio_file = getattr(transcription_module, "transcribe_audio_file")
    load_api_key()

    recorder = Recorder(AUDIO_FILE)

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
                "Add .wav files to mic_python/voices/ and run export_voices.bat."
            )

    # ── TTS queue + STT lock ────────────────────────────────
    tts_queue = TTSQueue()
    _stt_lock = threading.Lock()

    # ── Message handler ─────────────────────────────────────
    def handle_message(topic: str, payload: dict) -> None:
        """Route an incoming WS message by topic."""
        logging.info("Received topic=%s", topic)

        if topic == "mic.start":
            lang = payload.get("lang") or None
            prompt = payload.get("prompt") or ""

            def _stt_thread():
                with _stt_lock:
                    _run_stt_task({
                        "recorder":   recorder,
                        "transcribe": transcribe_audio_file,
                        "lang":       lang,
                        "prompt":     prompt,
                    })

            threading.Thread(target=_stt_thread, daemon=True).start()

        elif topic == "mic.stop":
            if recorder.is_recording():
                logging.info("Stopping recording on mic.stop command.")
                recorder.stop_recording()

        elif topic == "tts.speak" and tts_enabled:
            voice_id   = payload.get("voice_id", "")
            text       = payload.get("text", "")
            speaker_id = payload.get("speaker_id", "")
            logging.info("tts.speak  speaker=%s  voice=%s  text=%.60s",
                         speaker_id, voice_id or "(none)", text)

            if not text:
                logging.warning("tts.speak received with empty text — skipping")
                publish("tts.done", {"speaker_id": speaker_id})
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
                    publish("tts.done", {"speaker_id": speaker_id})
                    return

            tts_queue.submit({
                "model":       tts_model,
                "voice_state": voice_state,
                "text":        text,
                "speaker_id":  speaker_id,
            })

        else:
            logging.debug("Unhandled topic: %s", topic)

    # ── WebSocket handler ───────────────────────────────────
    async def ws_handler(websocket):
        global _ws_connection
        if _ws_connection is not None:
            await websocket.close(4000, "Only one connection allowed")
            logging.warning("Rejected second WS connection")
            return

        _ws_connection = websocket
        logging.info("Game client connected")
        try:
            async for raw in websocket:
                try:
                    envelope = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    logging.warning("Malformed WS frame: %s", str(raw)[:80])
                    continue

                topic = envelope.get("t")
                payload = envelope.get("p", {})
                if not topic:
                    logging.warning("WS frame missing 't' field")
                    continue

                handle_message(topic, payload)
        except websockets.ConnectionClosed:
            logging.info("Game client disconnected")
        finally:
            _ws_connection = None

    # ── Launch ──────────────────────────────────────────────
    async def run_server():
        global _event_loop
        _event_loop = asyncio.get_running_loop()

        async with websockets.serve(ws_handler, "0.0.0.0", MIC_WS_PORT):
            logging.info("WS server listening on ws://0.0.0.0:%d", MIC_WS_PORT)
            if tts_enabled:
                print("TTS enabled — NPCs will speak their dialogue aloud.")
            else:
                print("You can now use the in-game key to talk.")
            await asyncio.Future()  # run forever

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logging.info("User interrupt.")
    except Exception:
        logging.exception("Unhandled error.")
    finally:
        if recorder.is_recording():
            recorder.stop_recording()
        logging.info("Shutdown complete.")


if __name__ == "__main__":
    main()

import sys
import time
import logging
import json
import importlib
import threading
from collections import deque

import zmq

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

LUA_PUB_PORT  = 5555   # Lua PUB → mic_python SUB (subscribe to mic.* / tts.* topics)
MIC_PUB_PORT  = 5557   # mic_python PUB → Lua SUB (publish mic.status / mic.result / tts.*)
RECV_TIMEOUT_MS = 100
AUDIO_FILE = "talker_audio.ogg"

####################################################################################################
# STATE MACHINE + TASK QUEUE
####################################################################################################

# States
IDLE        = "IDLE"
STT_ACTIVE  = "STT_ACTIVE"
TTS_ACTIVE  = "TTS_ACTIVE"


class TaskQueue:
    """FIFO task queue with an IDLE / STT_ACTIVE / TTS_ACTIVE state machine.

    Only one audio task (STT or TTS) runs at a time.  New tasks are queued
    when busy and automatically started when the current task finishes.
    """

    def __init__(self):
        self._queue: deque = deque()
        self._state: str = IDLE
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        return self._state

    def submit(self, task: dict) -> None:
        """Submit a task.  Starts immediately when IDLE, queues otherwise."""
        with self._lock:
            if self._state == IDLE:
                new_state = STT_ACTIVE if task["type"] == "stt" else TTS_ACTIVE
                self._state = new_state
                threading.Thread(target=self._execute, args=(task,), daemon=True).start()
            else:
                self._queue.append(task)
                logging.debug(
                    "Task queued (%s) — currently %s, queue depth %d",
                    task["type"],
                    self._state,
                    len(self._queue),
                )

    def _execute(self, task: dict) -> None:
        try:
            if task["type"] == "stt":
                _run_stt_task(task)
            elif task["type"] == "tts":
                _run_tts_task(task)
            else:
                logging.warning("Unknown task type: %s", task.get("type"))
        except Exception:
            logging.exception("Unhandled error executing task: %s", task.get("type"))
        finally:
            with self._lock:
                if self._queue:
                    next_task = self._queue.popleft()
                    self._state = STT_ACTIVE if next_task["type"] == "stt" else TTS_ACTIVE
                    threading.Thread(target=self._execute, args=(next_task,), daemon=True).start()
                else:
                    self._state = IDLE


####################################################################################################
# STT HELPERS
####################################################################################################

def publish(pub_socket: zmq.Socket, topic: str, payload: dict) -> None:
    """Publish a message using the simple wire format: '<topic> <json-payload>'."""
    msg = topic + " " + json.dumps(payload)
    pub_socket.send_string(msg)
    logging.debug("Published: %s", msg[:120])


def _run_stt_task(task: dict) -> None:
    """Execute a speech-to-text recording task."""
    recorder: Recorder  = task["recorder"]
    pub_socket           = task["pub"]
    transcribe_func      = task["transcribe"]
    lang: "str | None"  = task.get("lang")
    prompt: str         = task.get("prompt", "")

    publish(pub_socket, "mic.status", {"status": "LISTENING"})
    recorder.start_recording()
    while recorder.is_recording():
        time.sleep(0.1)

    publish(pub_socket, "mic.status", {"status": "TRANSCRIBING"})
    try:
        text = transcribe_func(AUDIO_FILE, prompt=prompt, lang=lang)
    except Exception as exc:
        logging.error("Transcription failed: %s", exc)
        text = ""
    publish(pub_socket, "mic.result", {"text": text})


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
    pub_socket  = task["pub"]
    voice_state = task["voice_state"]
    text: str   = task["text"]
    speaker_id: str = task.get("speaker_id", "")

    publish(pub_socket, "tts.started", {"speaker_id": speaker_id})
    try:
        play_tts(text, voice_state, task["model"])
    except Exception as exc:
        logging.error("TTS playback failed: %s", exc)
    finally:
        publish(pub_socket, "tts.done", {"speaker_id": speaker_id})


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

    # ── ZMQ setup ───────────────────────────────────────────
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.connect(f"tcp://127.0.0.1:{LUA_PUB_PORT}")
    sub.setsockopt(zmq.SUBSCRIBE, b"mic.")
    if tts_enabled:
        sub.setsockopt(zmq.SUBSCRIBE, b"tts.")
    sub.setsockopt(zmq.RCVTIMEO, RECV_TIMEOUT_MS)
    pub = ctx.socket(zmq.PUB)
    pub.bind(f"tcp://*:{MIC_PUB_PORT}")

    logging.info(
        "ZMQ SUB connected to tcp://127.0.0.1:%d (filter: mic.%s)",
        LUA_PUB_PORT,
        ", tts." if tts_enabled else "",
    )
    logging.info("ZMQ PUB bound on tcp://*:%d", MIC_PUB_PORT)
    if tts_enabled:
        print("TTS enabled — NPCs will speak their dialogue aloud.")
    else:
        print("You can now use the in-game key to talk.")

    # ── Task queue / state machine ──────────────────────────
    task_queue = TaskQueue()

    try:
        while True:
            try:
                raw_bytes = sub.recv()
                try:
                    raw = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    raw = raw_bytes.decode("latin-1")
            except zmq.Again:
                # No message within timeout — keep polling
                continue

            # Parse wire format: "<topic> <json-payload>"
            space = raw.find(" ")
            if space < 0:
                logging.warning("Invalid message (no space separator): %s", raw[:80])
                continue

            topic = raw[:space]
            json_str = raw[space + 1:]
            try:
                payload = json.loads(json_str)
            except Exception:
                logging.warning("Failed to parse JSON payload: %s", json_str[:80])
                payload = {}

            # Lua's bridge.publish wraps the data in {"topic":..., "payload":{...}}
            # Unwrap if present (same pattern as talker_service router)
            payload = payload.get("payload", payload)

            logging.info("Received topic=%s", topic)

            # ── mic.start ───────────────────────────────────
            if topic == "mic.start":
                lang = payload.get("lang") or None
                prompt = payload.get("prompt") or ""
                task_queue.submit({
                    "type":       "stt",
                    "recorder":   recorder,
                    "pub":        pub,
                    "transcribe": transcribe_audio_file,
                    "lang":       lang,
                    "prompt":     prompt,
                })

            # ── mic.stop ────────────────────────────────────
            elif topic == "mic.stop":
                if recorder.is_recording():
                    logging.info("Stopping recording on mic.stop command.")
                    recorder.stop_recording()

            # ── tts.speak ───────────────────────────────────
            elif topic == "tts.speak" and tts_enabled:
                voice_id   = payload.get("voice_id", "")
                text       = payload.get("text", "")
                speaker_id = payload.get("speaker_id", "")
                logging.info("tts.speak  speaker=%s  voice=%s  text=%.60s",
                             speaker_id, voice_id or "(none)", text)

                if not text:
                    logging.warning("tts.speak received with empty text — skipping")
                    publish(pub, "tts.done", {"speaker_id": speaker_id})
                    continue

                # Look up voice in cache (fallback to first available)
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
                        publish(pub, "tts.done", {"speaker_id": speaker_id})
                        continue

                task_queue.submit({
                    "type":        "tts",
                    "pub":         pub,
                    "model":       tts_model,
                    "voice_state": voice_state,
                    "text":        text,
                    "speaker_id":  speaker_id,
                })

            else:
                logging.debug("Unhandled topic: %s", topic)

    except KeyboardInterrupt:
        logging.info("User interrupt.")
    except Exception:
        logging.exception("Unhandled error.")
    finally:
        if recorder.is_recording():
            recorder.stop_recording()
        sub.close()
        pub.close()
        ctx.term()
        logging.info("Shutdown complete.")


if __name__ == "__main__":
    main()

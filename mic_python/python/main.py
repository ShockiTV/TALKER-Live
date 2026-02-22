import sys
import time
import logging
import json
import importlib

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

LUA_PUB_PORT = 5555   # Lua PUB → mic_python SUB (subscribe to mic.* topics)
MIC_PUB_PORT = 5557   # mic_python PUB → Lua SUB (publish mic.status / mic.result)
RECV_TIMEOUT_MS = 100
AUDIO_FILE = "talker_audio.ogg"

####################################################################################################
# HELPERS
####################################################################################################

def publish(pub_socket: zmq.Socket, topic: str, payload: dict) -> None:
    """Publish a message using the simple wire format: '<topic> <json-payload>'."""
    msg = topic + " " + json.dumps(payload)
    pub_socket.send_string(msg)
    logging.debug("Published: %s", msg[:120])


def record_session(
    recorder: Recorder,
    pub_socket: zmq.Socket,
    transcribe_func,
    lang: "str | None",
    prompt: str,
) -> None:
    """Record audio, transcribe, then publish mic.status and mic.result."""
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
# MAIN
####################################################################################################

def main() -> None:
    print("-" * 50)
    print_banner("TALKER")
    print("-" * 50)

    # Determine transcription provider from command-line argument
    provider = "gemini_proxy"
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("whisper_local", "whisper_api", "gemini_proxy"):
            provider = arg
    logging.info("Using transcription provider: %s", provider)

    # Load provider module
    transcription_module = importlib.import_module(provider)
    load_api_key = getattr(transcription_module, "load_openai_api_key")
    transcribe_audio_file = getattr(transcription_module, "transcribe_audio_file")
    load_api_key()

    recorder = Recorder(AUDIO_FILE)

    # ZMQ setup
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.connect(f"tcp://127.0.0.1:{LUA_PUB_PORT}")
    sub.setsockopt(zmq.SUBSCRIBE, b"mic.")
    sub.setsockopt(zmq.RCVTIMEO, RECV_TIMEOUT_MS)
    pub = ctx.socket(zmq.PUB)
    pub.bind(f"tcp://*:{MIC_PUB_PORT}")

    logging.info("ZMQ SUB connected to tcp://127.0.0.1:%d (filter: mic.*)", LUA_PUB_PORT)
    logging.info("ZMQ PUB bound on tcp://*:%d", MIC_PUB_PORT)
    print("You can now use the in-game key to talk.")

    try:
        while True:
            try:
                raw = sub.recv_string()
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

            logging.info("Received topic=%s", topic)

            if topic == "mic.start":
                lang = payload.get("lang") or None
                prompt = payload.get("prompt") or ""
                record_session(recorder, pub, transcribe_audio_file, lang, prompt)
            elif topic == "mic.stop":
                if recorder.is_recording():
                    logging.info("Stopping recording on mic.stop command.")
                    recorder.stop_recording()
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

import os
from pathlib import Path
import sys
import time
import logging
import tempfile

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from files import read_file, write_to_file
from recorder import Recorder
from whisper_local import load_openai_api_key, transcribe_audio_file
from banner import print_banner

####################################################################################################
# CONFIG
####################################################################################################

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),              # console
        logging.FileHandler("talker.log", encoding="utf-8")  # persistent log
    ],
)

# Get the system's temporary directory
TEMP_DIR = tempfile.gettempdir()

# File paths in the temporary directory
COMMAND_FILE = os.path.join(TEMP_DIR, 'talker_mic_io_commands')
TRANSCRIPTION_FILE = os.path.join(TEMP_DIR, 'talker_mic_io_transcription')
AUDIO_FILE = os.path.join(TEMP_DIR, 'talker_audio.ogg')

# Commands
COMMANDS = {
    'LISTENING': 'LISTENING',
    'TRANSCRIBING': 'TRANSCRIBING',
    'START'       : 'START-',   # syntax: START-<lang>-<prompt>
    'STOP': 'STOP',
    'DONE': 'DONE'
}

####################################################################################################
# MAIN
####################################################################################################

def main():
    try:
        print("-"*50)
        print_banner("TALKER")
        print("-"*50)
        load_openai_api_key()
        recorder = Recorder(AUDIO_FILE)
        Path(COMMAND_FILE).touch()

        handler  = CommandHandler(recorder)
        observer = Observer()
        observer.schedule(handler, TEMP_DIR, recursive=False)
        observer.start()

        logging.info("Observer running, watching %s", COMMAND_FILE)
        print("You can now use the in-game key to talk.")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("User interrupt.")
    except Exception:
        logging.exception("Unhandled error.")
    finally:
        try:
            observer.stop(); observer.join()
        except NameError:
            pass
        logging.info("Shutdown complete.")


####################################################################################################
# START COMMAND
####################################################################################################

DEFAULT_LANG = None            # let Whisper auto-detect unless user supplies code

def parse_start_line(line: str):
    """Extract (lang, prompt) from 'START-...'."""
    payload = line[len(COMMANDS['START']):]          # after START-
    if len(payload) >= 3 and payload[2] == '-':
        lang = payload[:2]
        prompt = payload[3:]
    else:
        lang  = DEFAULT_LANG
        prompt= payload
    return lang, prompt



####################################################################################################
# COMMAND HANDLER
####################################################################################################
class CommandHandler(FileSystemEventHandler):
    def __init__(self, recorder: Recorder):
        self.recorder = recorder

    def on_modified(self, event):
        try:
            if os.path.abspath(event.src_path) == os.path.abspath(COMMAND_FILE):
                self._handle_command()
        except Exception as e:
            logging.warning("Error handling update: %s", e)

    # ─────────────── core ────────────────
    def _handle_command(self):
        raw = read_file(COMMAND_FILE)
        if raw.startswith(COMMANDS['START']):
            lang, prompt = parse_start_line(raw)
            self._record_session(prompt, lang)
        elif raw.strip() == COMMANDS['STOP']:
            self.recorder.stop_recording()

    def _record_session(self, prompt: str = '', language: str | None = DEFAULT_LANG):
        try:
            write_to_file(COMMAND_FILE, COMMANDS['LISTENING'])
            self.recorder.start_recording()
            while self.recorder.is_recording():
                time.sleep(0.1)

            write_to_file(COMMAND_FILE, COMMANDS['TRANSCRIBING'])
            text = transcribe_audio_file(AUDIO_FILE, prompt, language)
            write_to_file(TRANSCRIPTION_FILE, text)
            write_to_file(COMMAND_FILE, COMMANDS['DONE'])

        except Exception as e:
            logging.error("Recording session failed: %s", e)
            write_to_file(COMMAND_FILE, COMMANDS['ERROR'])







if __name__ == '__main__':
    main()

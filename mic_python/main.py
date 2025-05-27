import os
import sys
import time
import logging
import tempfile
import subprocess
import banner
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

print("="*50)
banner.print_banner("TALKER")
print("="*50)
def ask_and_install_requirements():
    answer = input("\nA required Python package is missing. Do you want to install all dependencies from requirements.txt now? [Y/n]: ").strip().lower()
    if answer in ('', 'y', 'yes'):
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
            print("\nDependencies installed. Please restart the script.")
        except subprocess.CalledProcessError as e:
            print(f"\nERROR: Failed to install requirements.\nDetails: {e}")
        input("Press Enter to exit...")
        sys.exit(1)
    else:
        print("Cannot continue without required packages.")
        input("Press Enter to exit...")
        sys.exit(1)

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    from recorder import Recorder
    from whisper_api import load_openai_api_key, transcribe_audio_file
except ModuleNotFoundError as e:
    print(f"\nERROR: {e}")
    ask_and_install_requirements()

# Configure logging
logging.basicConfig(level=logging.ERROR)

API_KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'openAi_API_KEY.key')
TEMP_DIR = tempfile.gettempdir()
COMMAND_FILE = os.path.join(TEMP_DIR, 'talker_mic_io_commands')
TRANSCRIPTION_FILE = os.path.join(TEMP_DIR, 'talker_mic_io_transcription')
AUDIO_FILE = os.path.join(TEMP_DIR, 'talker_audio.ogg')

COMMANDS = {
    'LISTENING': 'LISTENING',
    'TRANSCRIBING': 'TRANSCRIBING',
    'START': 'START-',
    'STOP': 'STOP',
    'DONE': 'DONE'
}

def exit_with_message(message):
    print(f"\nERROR: {message}")
    input("Press Enter to exit...")
    sys.exit(1)

def main():
    try:
        load_openai_api_key(API_KEY_PATH)
    except Exception as e:
        exit_with_message(f"Failed to load OpenAI API key. Make sure the file exists at {API_KEY_PATH} and contains a valid key.\nDetails: {e}")

    recorder = Recorder(AUDIO_FILE)

    try:
        if not os.path.exists(COMMAND_FILE):
            open(COMMAND_FILE, 'w').close()
    except Exception as e:
        exit_with_message(f"Cannot create or access the command file.\nDetails: {e}")

    event_handler = CommandHandler(recorder)
    observer = Observer()
    try:
        observer.schedule(event_handler, path=TEMP_DIR, recursive=False)
        observer.start()
    except Exception as e:
        exit_with_message(f"Could not start file watcher.\nDetails: {e}")



    print("TALKER speech to text started. You can now activate it via the game key.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    print("Exiting...")
    sys.exit(0)

class CommandHandler(FileSystemEventHandler):
    def __init__(self, recorder):
        self.recorder = recorder

    def on_modified(self, event):
        if os.path.abspath(event.src_path) == os.path.abspath(COMMAND_FILE):
            self.handle_command()

    def handle_command(self):
        content = read_file(COMMAND_FILE)
        if content.startswith(COMMANDS['START']):
            prompt = content[len(COMMANDS['START']):]
            self.start_recording_session(prompt)
        elif content.strip() == COMMANDS['STOP']:
            self.recorder.stop_recording()

    def start_recording_session(self, prompt=''):
        try:
            write_to_file(COMMAND_FILE, COMMANDS['LISTENING'])
            print("Recording started.")
            self.recorder.start_recording()

            while self.recorder.is_recording():
                time.sleep(0.1)
            print("Recording complete.")

            write_to_file(COMMAND_FILE, COMMANDS['TRANSCRIBING'])
            transcription = transcribe_audio_file(AUDIO_FILE, prompt)
            write_to_file(TRANSCRIPTION_FILE, transcription)
            write_to_file(COMMAND_FILE, COMMANDS['DONE'])

        except Exception as e:
            message = str(e)
            if "Error querying device -1" in message:
                error_msg = "No input microphone found. Please check your system's input device settings."
            else:
                error_msg = f"Something went wrong during recording or transcription.\nDetails: {message}"

            print(f"\nERROR: {error_msg}")
            write_to_file(COMMAND_FILE, 'ERROR')
            input("Press Enter to exit...")
            sys.exit(1)

def read_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except Exception as e:
        print(f"\nERROR: Failed to read from file {file_path}. Check if it exists and is accessible.\nDetails: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

def write_to_file(file_path, content):
    try:
        with open(file_path, 'w') as file:
            file.write(content)
    except Exception as e:
        print(f"\nERROR: Failed to write to file {file_path}. Check if the file is writable.\nDetails: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == '__main__':
    main()
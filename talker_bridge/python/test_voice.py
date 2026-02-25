import time
import os
import tempfile
from recorder import Recorder
from gemini_proxy import transcribe_audio_file

# --- Configuration ---
AUDIO_FILE = 'talker_test_audio.ogg' # Save in the same directory as the script
RECORD_SECONDS = 5

def main():
    """
    Records a short audio clip and sends it to the Gemini proxy for transcription.
    """
    print("--- Voice Transcription Test ---")
    
    # 1. Record audio
    recorder = Recorder(AUDIO_FILE)
    print(f"Recording with a {RECORD_SECONDS}-second silence grace period...")
    recorder.start_recording(silence_grace_period=RECORD_SECONDS)
    
    # In this test, we will manually stop the recording after the grace period
    # to ensure a predictable test duration.
    print(f"Waiting for {RECORD_SECONDS + 1} seconds before stopping...")
    time.sleep(RECORD_SECONDS + 1) # Record for grace period + 1 second
    if recorder.is_recording():
        recorder.stop_recording()

    print(f"Recording finished. Audio saved to: {os.path.abspath(AUDIO_FILE)}")

    # 2. Transcribe audio
    print("Transcribing audio with Gemini proxy...")
    transcription = transcribe_audio_file(AUDIO_FILE, prompt="", lang="en")

    # 3. Print result
    if transcription:
        print("\n--- Transcription Result ---")
        print(transcription)
    else:
        print("\n--- Transcription Failed ---")
        print("No transcription received. Check the logs for errors.")

if __name__ == '__main__':
    main()

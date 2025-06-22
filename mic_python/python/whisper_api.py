# whisper_api.py
# represents the transcription

import os
import sys
from pathlib import Path
import openai
import logging

logging.basicConfig(encoding="utf-8")

################################################################################################
# CONSTANTS
################################################################################################

ROOT_DIR = Path(getattr(sys, "frozen", False) and sys.executable or __file__).resolve().parent
API_KEY_FILE = ROOT_DIR / "openAi_API_KEY.key"

################################################################################################
# TRANSCRIPTION
################################################################################################

def transcribe_audio_file(audio_path: str,
                          prompt: str,
                          lang: str = "en",
                          out_path: str | None = None) -> str:
    """Call Whisper and (optionally) save the transcript."""
    transcript = openai.audio.transcriptions.create(
        model="whisper-1",
        file=open(audio_path, "rb"),
        prompt=prompt,
        language=lang,
    )
    text = transcript.text
    print(f"Transcription from {lang}: {text}")

    if out_path:
        Path(out_path).write_text(text, encoding="utf-8")

    return text

################################################################################################
# LOAD OR CREATE KEY
################################################################################################

API_KEY_FILE = Path(".") / "openai_api_key.txt"
TEMP_API_KEY_FILE = Path(os.getenv("TEMP")) / "openai_api_key.txt"

def load_openai_api_key():
    """Prompt for OpenAI API key if not found or invalid. Test before saving to config and temp."""
    while True:
        if API_KEY_FILE.exists():
            api_key = API_KEY_FILE.read_text(encoding="utf-8").strip()
        else:
            api_key = input("Enter your OpenAI API key: ").strip()

        if not api_key:
            print("[ERROR] No API key provided.")
            continue

        openai.api_key = api_key

        try:
            test_key()
            # Only save after successful test
            API_KEY_FILE.write_text(api_key, encoding="utf-8")
            TEMP_API_KEY_FILE.write_text(api_key, encoding="utf-8")
            print(f"API key saved to: {API_KEY_FILE}")
            print(f"API key also saved to: {TEMP_API_KEY_FILE}")
            break
        except openai.AuthenticationError:
            print("\n[ERROR] Invalid API key.")
            print("→ Visit https://platform.openai.com/account/api-keys to get a valid key.")
            print("→ Please enter a new key.\n")
            if API_KEY_FILE.exists():
                API_KEY_FILE.unlink(missing_ok=True)
            if TEMP_API_KEY_FILE.exists():
                TEMP_API_KEY_FILE.unlink(missing_ok=True)
        except openai.PermissionDeniedError:
            print("\n[ERROR] No funds on key or otherwise permission denied.")
            if API_KEY_FILE.exists():
                API_KEY_FILE.unlink(missing_ok=True)
            if TEMP_API_KEY_FILE.exists():
                TEMP_API_KEY_FILE.unlink(missing_ok=True)
        except Exception as e:
            print("\n[ERROR] Unexpected error while validating API key:", str(e))
            raise SystemExit(1)

################################################################################################
# TEST KEY
################################################################################################

def test_key():
    prompt = "Say 'Key successfully loaded!'"
    print(ask_gpt(prompt, "gpt-4o-mini"))

def ask_gpt(question: str, model: str) -> str:
    chat_completion = openai.chat.completions.create(
        messages=[{"role": "user", "content": question}],
        model=model,
    )
    return chat_completion.choices[0].message.content

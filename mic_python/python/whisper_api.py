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

def load_openai_api_key():
    """Load the OpenAI API key from a file, validate it, or prompt until it's valid."""
    while True:
        if not API_KEY_FILE.exists():
            api_key = input("Enter your OpenAI API key: ").strip()
            if not api_key:
                print("[ERROR] No API key provided.")
                continue
            API_KEY_FILE.write_text(api_key, encoding="utf-8")
            print(f"API key saved to: {API_KEY_FILE}")
        else:
            api_key = API_KEY_FILE.read_text(encoding="utf-8").strip()

        if not api_key:
            print("[ERROR] OpenAI API key file is empty.")
            API_KEY_FILE.unlink(missing_ok=True)
            continue

        openai.api_key = api_key

        try:
            test_key()
            break  # success
        except openai.AuthenticationError:
            print("\n[ERROR] Invalid API key.")
            print("→ Visit https://platform.openai.com/account/api-keys to get a valid key.")
            print("→ Please enter a new key.\n")
            API_KEY_FILE.unlink(missing_ok=True)
        except openai.PermissionDeniedError:
            print("\n[ERROR] No funds on key or otherwise permission denied.")
            API_KEY_FILE.unlink(missing_ok=True)
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

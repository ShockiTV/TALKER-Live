# whisper_api.py
# represents the transcription

from pathlib import Path
import openai

import logging
logging.basicConfig(encoding="utf-8")  

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
# LOAD KEY
################################################################################################

def load_openai_api_key(API_KEY_PATH):
    """Load the OpenAI API key from a file."""
    try:
        with open(API_KEY_PATH, "r") as file:
            api_key = file.read().strip()
        if not api_key:
            raise ValueError("OpenAI API key is empty. Please enter your API key in 'openAi_API_KEY.key'.")
        openai.api_key = api_key
        test_key()
    except FileNotFoundError:
        raise ValueError(f"OpenAI API key file '{API_KEY_PATH}' not found.")

################################################################################################
# TEST KEY
################################################################################################

def test_key():
    # says hello world to gpt4o mini
    prompt = "Say 'Key succesfully loaded!' "
    print(ask_gpt(prompt, "gpt-4o-mini"))


def ask_gpt(question: str, model: str) -> str:
    chat_completion = openai.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": question,
            }
        ],
        model=model,
    )
    return chat_completion.choices[0].message.content
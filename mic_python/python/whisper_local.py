# whisper_api.py
# local transcription using faster-whisper (Whisper Tiny)

import sys
import logging
from pathlib import Path

from faster_whisper import WhisperModel

logging.basicConfig(encoding="utf-8")

################################################################################################
# CONSTANTS
################################################################################################

ROOT_DIR = Path(getattr(sys, "frozen", False) and sys.executable or __file__).resolve().parent
WHISPER_MODEL = "tiny.en"  # faster-whisper model name

################################################################################################
# TRANSCRIPTION
################################################################################################

def transcribe_audio_file(audio_path: str,
                          prompt: str,
                          lang: str = "en",
                          out_path: str | None = None) -> str:
    """Transcribe audio using local faster-whisper model."""
    model = WhisperModel(WHISPER_MODEL, compute_type="int8", device="cpu")

    segments, _ = model.transcribe(audio_path, language=lang, initial_prompt=prompt)
    text = "".join(segment.text for segment in segments)

    print(f"Transcription from {lang}: {text}")

    if out_path:
        Path(out_path).write_text(text, encoding="utf-8")

    return text

################################################################################################
# API KEY HANDLING (noop)
################################################################################################

def load_openai_api_key():
    test_transcription_service()

################################################################################################
# CHECK SERVICE AVAILABILITY
################################################################################################

def test_transcription_service():
    try:
        model = WhisperModel(WHISPER_MODEL, compute_type="int8", device="cpu")
        print(f"✅ faster-whisper '{WHISPER_MODEL}' loaded successfully.")
    except Exception as e:
        print(f"❌ Failed to load model '{WHISPER_MODEL}': {e}")
        print("→ Try: pip install faster-whisper")

################################################################################################
# GPT STUB
################################################################################################

def ask_gpt(question: str, model: str) -> str:
    return "This function is not available in local-only mode."

"""Shared TTS HTTP microservice wrapping pocket_tts.

Loads the pocket_tts model and voice cache once at startup, then serves
``POST /generate`` requests returning OGG Vorbis audio bytes.

Designed to run inside a Docker container based on
``ghcr.io/kyutai-labs/pocket-tts:latest`` which provides all native
dependencies (Rust toolchain, FFI bindings, etc.).
"""

from __future__ import annotations

import asyncio
import os
import random
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

# ── pocket_tts ──────────────────────────────────────────────────────
from pocket_tts import TTSModel

# pocket_tts outputs 24 kHz; X-Ray engine requires 44100 Hz OGG files.
TTS_SAMPLE_RATE = 24000
ENGINE_SAMPLE_RATE = 44100

# Safety backstop: abort if chunk count exceeds this.
MAX_TTS_CHUNKS = 200

# Default volume boost (ffmpeg -af volume=N).
DEFAULT_VOLUME_BOOST = 8.0


# ── ffmpeg helper ───────────────────────────────────────────────────

def _get_ffmpeg_path() -> str:
    """Resolve ffmpeg executable path."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    return "ffmpeg"


# ── Global state ────────────────────────────────────────────────────

_model: Optional[TTSModel] = None
_voice_cache: Dict[str, Any] = {}


# ── Request / response models ──────────────────────────────────────

class GenerateRequest(BaseModel):
    text: str
    voice_id: str = ""
    volume_boost: float = DEFAULT_VOLUME_BOOST


# ── Lifespan ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model, _voice_cache

    logger.info("Loading pocket_tts model...")
    _model = TTSModel.load_model()
    logger.info("pocket_tts model loaded")

    voices_dir = Path(os.environ.get("VOICES_DIR", "./voices"))
    if voices_dir.exists():
        voice_files = sorted(voices_dir.glob("*.safetensors"))
        logger.info("Loading {} voice(s) from {}", len(voice_files), voices_dir)
        for vf in voice_files:
            try:
                _voice_cache[vf.stem] = _model.get_state_for_audio_prompt(str(vf))
                logger.info("  loaded voice: {}", vf.stem)
            except Exception as e:
                logger.error("  failed to load voice {}: {}", vf.stem, e)
        logger.info("Voice cache: {} voice(s)", len(_voice_cache))
    else:
        logger.warning("Voices directory not found: {}", voices_dir)

    yield

    logger.info("TTS service shutting down")


# ── App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="TALKER TTS Service",
    description="Shared pocket_tts microservice for OGG Vorbis audio generation",
    version="0.1.0",
    lifespan=lifespan,
)


def _resolve_voice(voice_id: str) -> tuple[str, Any, bool] | None:
    """Resolve voice_id → (resolved_id, voice_state, was_fallback).  Random fallback."""
    if not _voice_cache:
        return None
    if voice_id in _voice_cache:
        return voice_id, _voice_cache[voice_id], False
    # Random fallback
    fallback_id = random.choice(list(_voice_cache.keys()))
    logger.warning("Voice '{}' not found, falling back to '{}'", voice_id, fallback_id)
    return fallback_id, _voice_cache[fallback_id], True


def _generate_ogg(text: str, voice: Any, volume_boost: float) -> tuple[bytes, int]:
    """Synchronous TTS generation → OGG bytes + duration_ms."""
    chunks = []
    chunk_count = 0
    for chunk in _model.generate_audio_stream(voice, text):  # type: ignore[union-attr]
        chunk_count += 1
        if chunk_count > MAX_TTS_CHUNKS:
            logger.warning("Exceeded {} chunks, aborting", MAX_TTS_CHUNKS)
            break
        chunks.append(chunk.numpy())

    if not chunks:
        raise RuntimeError("pocket_tts produced no audio chunks")

    raw = np.concatenate(chunks).astype(np.float32)
    duration_ms = int(len(raw) / TTS_SAMPLE_RATE * 1000)

    # Peak-normalize to ±1.0
    peak = np.max(np.abs(raw))
    if peak > 1e-6:
        raw = raw / peak

    pcm_bytes = raw.tobytes()
    ffmpeg = _get_ffmpeg_path()

    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "f32le",
            "-ar", str(TTS_SAMPLE_RATE),
            "-ac", "1",
            "-i", "pipe:0",
            "-ar", str(ENGINE_SAMPLE_RATE),
            "-af", f"volume={volume_boost}",
            "-c:a", "libvorbis",
            "-q:a", "5",
            "-f", "ogg",
            "pipe:1",
        ],
        input=pcm_bytes,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode(errors='replace')[:500]}")

    return result.stdout, duration_ms


# ── Endpoints ───────────────────────────────────────────────────────

@app.post("/generate")
async def generate(req: GenerateRequest):
    """Generate OGG Vorbis audio from text.

    Returns raw OGG bytes with ``Content-Type: audio/ogg``.
    Duration (ms) is in the ``X-Audio-Duration-Ms`` response header.
    """
    if not req.text or not req.text.strip():
        return JSONResponse(status_code=400, content={"error": "text is required"})

    resolved = _resolve_voice(req.voice_id)
    if resolved is None:
        return JSONResponse(status_code=503, content={"error": "No voices loaded"})

    resolved_id, voice_state, was_fallback = resolved

    try:
        loop = asyncio.get_event_loop()
        ogg_bytes, duration_ms = await loop.run_in_executor(
            None, _generate_ogg, req.text, voice_state, req.volume_boost
        )
    except Exception as e:
        logger.opt(exception=True).error("TTS generation failed")
        return JSONResponse(status_code=500, content={"error": str(e)})

    headers = {
        "X-Audio-Duration-Ms": str(duration_ms),
        "X-Voice-Id": resolved_id,
    }
    if was_fallback:
        headers["X-Warning"] = f"voice_id '{req.voice_id}' not found, fell back to '{resolved_id}'"
    return Response(content=ogg_bytes, media_type="audio/ogg", headers=headers)


@app.get("/health")
async def health():
    """Health check — reports model and voice status."""
    return {
        "status": "ok",
        "model_loaded": _model is not None,
        "voices": len(_voice_cache),
    }

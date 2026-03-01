"""
TTS engine implementation using pocket_tts.

Loads pocket_tts model and voice cache, generates OGG Vorbis audio from text.

API reference (pocket_tts v1.1.1):
    model = TTSModel.load_model()
    voice_state = model.get_state_for_audio_prompt(safetensors_path)
    for chunk in model.generate_audio_stream(voice_state, text):
        audio = chunk.numpy()   # numpy float32 @ 24 kHz mono
"""

import asyncio
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from loguru import logger


def _log_memory():
    """Log current process memory usage (Windows only, best-effort)."""
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(pmc)
        handle = ctypes.windll.kernel32.GetCurrentProcess()  # type: ignore[attr-defined]
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):  # type: ignore[attr-defined]
            mb = pmc.WorkingSetSize / (1024 * 1024)
            peak_mb = pmc.PeakWorkingSetSize / (1024 * 1024)
            logger.info("Process memory: {:.0f} MB (peak {:.0f} MB)", mb, peak_mb)
    except Exception:
        pass  # non-critical diagnostic

# pocket_tts outputs 24 kHz; X-Ray engine requires 44100 Hz OGG files.
TTS_SAMPLE_RATE = 24000
ENGINE_SAMPLE_RATE = 44100

# Timeout for a single TTS generation call (seconds).
# If pocket_tts hangs (OOM, no EOS), this triggers fallback to text-only.
TTS_TIMEOUT_S = 30

# Safety backstop: abort if chunk count exceeds this.
# pocket_tts chunks are ~0.25s each at 24 kHz; 200 chunks ≈ 50 seconds.
# Normal dialogue lines produce 10-40 chunks. This only fires on true runaway.
MAX_TTS_CHUNKS = 200

# Default volume boost applied during OGG encoding (ffmpeg -af volume=N).
# Audio is peak-normalized to ±1.0 first; 8.0 ≈ +18 dB above full scale.
# Overridden at runtime by MCM setting tts_volume_boost.
DEFAULT_VOLUME_BOOST = 8.0

# pocket_tts import (will fail if not installed)
try:
    from pocket_tts import TTSModel
except ImportError as e:
    raise ImportError(f"pocket_tts not installed: {e}")


def _get_ffmpeg_path() -> str:
    """Resolve ffmpeg executable path.
    
    Tries imageio-ffmpeg bundled binary first, then system PATH.
    """
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    # Fallback to system PATH
    return "ffmpeg"


class TTSEngine:
    """TTS engine for generating OGG Vorbis audio from dialogue text."""

    def __init__(self):
        self.model: Optional[TTSModel] = None
        self.voice_cache: Dict[str, Any] = {}  # voice_id → voice_state object
        self.volume_boost: float = DEFAULT_VOLUME_BOOST
        self._loop = None
        self._executor_id = 0
        # Single-threaded executor: pocket_tts model is NOT thread-safe.
        # Concurrent calls corrupt internal state and cause infinite loops.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts")

    def _recycle_executor(self):
        """Abandon the current executor and create a fresh one.

        Called after a TTS timeout.  The stuck thread can't be killed (it's
        in native code), but creating a new executor lets subsequent calls
        proceed on a fresh thread instead of queueing behind the stuck one.
        """
        old = self._executor
        self._executor_id += 1
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"tts-{self._executor_id}")
        # Don't wait for the old executor — just let it leak the stuck thread.
        old.shutdown(wait=False, cancel_futures=True)
        logger.warning("Recycled TTS executor (#{}) after timeout", self._executor_id)

    def shutdown(self):
        """Shut down the TTS executor without waiting for stuck threads."""
        logger.info("Shutting down TTS executor (cancel_futures=True)...")
        self._executor.shutdown(wait=False, cancel_futures=True)

    async def load(self, voices_dir: Path):
        """Load pocket_tts model and voice cache from .safetensors files.
        
        Args:
            voices_dir: Directory containing .safetensors voice files
        """
        logger.info("Loading pocket_tts model...")
        self.model = TTSModel.load_model()
        logger.info("pocket_tts model loaded")

        # Load voices from .safetensors files
        voices_dir = Path(voices_dir)
        if not voices_dir.exists():
            logger.warning("Voices directory not found: {}", voices_dir)
            return

        voice_files = sorted(voices_dir.glob("*.safetensors"))
        if not voice_files:
            logger.warning("No .safetensors files found in {}", voices_dir)
            return

        logger.info("Loading {} voice(s) from {}...", len(voice_files), voices_dir)

        for voice_file in voice_files:
            voice_id = voice_file.stem  # e.g., "dolg_1" from "dolg_1.safetensors"
            try:
                voice_state = self.model.get_state_for_audio_prompt(str(voice_file))
                self.voice_cache[voice_id] = voice_state
                logger.info("Loaded voice: {}", voice_id)
            except Exception as e:
                logger.error("Failed to load voice {}: {}", voice_id, e)

        logger.info("Voice cache populated with {} voice(s)", len(self.voice_cache))

    def _generate_audio_sync(self, text: str, voice_id: str, cancel: threading.Event | None = None) -> Optional[bytes]:
        """Synchronous audio generation (runs in executor).
        
        Args:
            text: Dialogue text to synthesize
            voice_id: Voice ID to use (from cache)
            cancel: Optional cancellation event; checked between chunks
            
        Returns:
            OGG Vorbis bytes, or None on error or cancellation
        """
        if not text or text.strip() == "":
            logger.debug("Empty text, skipping TTS generation")
            return None

        if not self.model:
            logger.error("TTS model not loaded")
            return None

        # Resolve voice_id
        voice = self._resolve_voice(voice_id)
        if not voice:
            logger.warning("No voice available for TTS generation")
            return None

        try:
            # Concat-then-encode approach: collect all pocket_tts chunks,
            # concatenate, resample once, then pipe through subprocess.run().
            # This avoids the Popen stdin/stdout pipe deadlock that caused
            # every TTS call to hang with the streaming approach.
            _log_memory()
            logger.info("Generating TTS audio for text: '{}' (voice: {})", text[:50], voice_id)
            
            ffmpeg = _get_ffmpeg_path()

            # 1) Collect all chunks from pocket_tts
            chunks = []
            chunk_count = 0
            for chunk in self.model.generate_audio_stream(voice, text):
                # Check cancellation between chunks (set by async timeout)
                if cancel and cancel.is_set():
                    logger.warning("TTS generation cancelled by timeout after {} chunks", chunk_count)
                    return None
                chunk_count += 1
                if chunk_count > MAX_TTS_CHUNKS:
                    logger.warning(
                        "TTS exceeded {} chunks (runaway generation), aborting",
                        MAX_TTS_CHUNKS
                    )
                    break
                chunks.append(chunk.numpy())

            if not chunks:
                logger.warning("pocket_tts produced no chunks")
                return None

            logger.info("pocket_tts produced {} chunks, encoding...", chunk_count)

            # 2) Concatenate and peak-normalize to ±1.0
            raw_audio = np.concatenate(chunks).astype(np.float32)
            peak = np.max(np.abs(raw_audio))
            if peak > 1e-6:
                raw_audio = raw_audio / peak
                logger.info("Peak-normalized audio (peak was {:.6f})", peak)
            else:
                logger.warning("Audio near-silent (peak {:.6f}), skipping normalization", peak)
            pcm_bytes = raw_audio.tobytes()

            # ffmpeg handles 24kHz→44100Hz resampling, volume boost, and OGG encoding
            # in a single pass — no scipy dependency needed.
            result = subprocess.run(
                [
                    ffmpeg, '-y',
                    '-f', 'f32le',
                    '-ar', str(TTS_SAMPLE_RATE),
                    '-ac', '1',
                    '-i', 'pipe:0',
                    '-ar', str(ENGINE_SAMPLE_RATE),
                    '-af', f'volume={self.volume_boost}',
                    '-c:a', 'libvorbis',
                    '-q:a', '5',
                    '-f', 'ogg',
                    'pipe:1',
                ],
                input=pcm_bytes,
                capture_output=True,
            )

            if result.returncode != 0:
                logger.error("ffmpeg OGG encoding failed: {}", result.stderr.decode(errors='replace')[:500])
                return None

            ogg_bytes = result.stdout

            logger.info("Generated OGG audio: {} bytes ({} pages, {} chunks) for text: '{}'",
                        len(ogg_bytes), ogg_bytes.count(b'OggS'), chunk_count, text[:50])
            _log_memory()
            
            return ogg_bytes

        except Exception as e:
            logger.error("Failed to generate TTS audio: {}", e)
            return None

    async def generate_audio(self, text: str, voice_id: str) -> Optional[bytes]:
        """Generate OGG Vorbis audio from dialogue text (async).
        
        Runs the blocking TTS generation in a thread pool executor to avoid
        blocking the asyncio event loop.
        
        Args:
            text: Dialogue text to synthesize
            voice_id: Voice ID to use (from cache)
            
        Returns:
            OGG Vorbis bytes, or None on error or if text is empty
        """
        if not text or text.strip() == "":
            return None

        # Run synchronous generation in executor with timeout + cancellation.
        # On timeout, set cancel event so the thread stops at next chunk boundary.
        loop = asyncio.get_event_loop()
        cancel = threading.Event()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    self._executor,
                    self._generate_audio_sync, text, voice_id, cancel
                ),
                timeout=TTS_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            cancel.set()  # signal thread to stop at next chunk
            self._recycle_executor()  # abandon stuck thread, create fresh executor
            logger.error("TTS generation timed out after {}s for text: '{}'", TTS_TIMEOUT_S, text[:50])
            return None

    def _resolve_voice(self, voice_id: str) -> Optional[Any]:
        """Resolve voice_id to a voice state object.
        
        Falls back to first available voice if voice_id not found.
        Returns None if no voices are available.
        
        Args:
            voice_id: Requested voice ID
            
        Returns:
            Voice state object or None
        """
        if not self.voice_cache:
            logger.warning("Voice cache is empty, cannot resolve voice")
            return None

        # Try exact match
        if voice_id in self.voice_cache:
            return self.voice_cache[voice_id]

        # Fall back to first available voice
        fallback_voice_id = next(iter(self.voice_cache))
        logger.warning(
            "Voice '{}' not found, falling back to '{}'",
            voice_id,
            fallback_voice_id
        )
        return self.voice_cache[fallback_voice_id]

#!/usr/bin/env python3
"""
Generate 200 silent OGG Vorbis files for TTS slot pool.

Creates silent audio slots (44.1kHz mono, 0.1s duration) that are shipped
with the mod. These files enable runtime TTS audio playback without requiring
engine restart — the X-Ray engine indexes sound files at startup only.
"""

import os
import sys
import subprocess
import numpy as np

# Add talker_service/src to path for ogg_patcher
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'talker_service', 'src'))
from talker_service.tts.ogg_patcher import patch_ogg_xray


def _get_ffmpeg_path() -> str:
    """Resolve ffmpeg executable path."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"

# Configuration — files go under characters_voice so npc:add_sound() can find them
# when sound_prefix is set to "characters_voice\\"
OUTPUT_DIR = "gamedata/sounds/characters_voice/talker_tts"
NUM_SLOTS = 200
SAMPLE_RATE = 44100  # 44.1kHz — required by X-Ray engine
DURATION = 0.1  # 0.1 seconds (minimum to be accepted by X-Ray)
CHANNELS = 1  # Mono


def generate_silent_ogg(slot_num: int, output_dir: str) -> str:
    """Generate a single silent OGG Vorbis file.
    
    Args:
        slot_num: Slot number (1-100)
        output_dir: Directory to write the file to
        
    Returns:
        Path to the generated file
    """
    # Generate silent audio (zeros)
    num_samples = int(SAMPLE_RATE * DURATION)
    audio = np.zeros(num_samples, dtype=np.float32)
    
    # No leading zeros — X-Ray add_sound() scans slot_1.ogg, slot_2.ogg, etc.
    filename = f"slot_{slot_num}.ogg"
    filepath = os.path.join(output_dir, filename)
    
    # Write OGG Vorbis file via subprocess ffmpeg.
    # Subprocess ffmpeg produces proper OGG page boundaries that X-Ray
    # handles correctly (PyAV's in-process encoder truncates playback).
    raw_pcm = audio.tobytes()
    ffmpeg = _get_ffmpeg_path()
    proc = subprocess.run(
        [
            ffmpeg, '-y',
            '-f', 'f32le',
            '-ar', str(SAMPLE_RATE),
            '-ac', '1',
            '-i', 'pipe:0',
            '-c:a', 'libvorbis',
            '-q:a', '5',
            '-f', 'ogg',
            'pipe:1',
        ],
        input=raw_pcm,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for slot {slot_num}: {proc.stderr.decode(errors='replace')[:300]}")

    # Patch with X-Ray spatial audio metadata (version=3, min/max distance, etc.)
    ogg_bytes = proc.stdout
    patched = patch_ogg_xray(ogg_bytes)
    if patched:
        ogg_bytes = patched

    with open(filepath, 'wb') as f:
        f.write(ogg_bytes)
    
    return filepath


def main():
    """Generate all 200 silent slot files."""
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"Generating {NUM_SLOTS} silent OGG files...")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Format: {SAMPLE_RATE}Hz mono, {DURATION}s duration, OGG Vorbis")
    print()
    
    for slot_num in range(1, NUM_SLOTS + 1):
        filepath = generate_silent_ogg(slot_num, OUTPUT_DIR)
        
        # Print progress every 10 files
        if slot_num % 10 == 0:
            print(f"Generated {slot_num}/{NUM_SLOTS} files...")
    
    print()
    print(f"✓ Successfully generated {NUM_SLOTS} silent OGG files")
    print(f"  Total size: ~{NUM_SLOTS * 1}KB")
    print()
    print("You can now commit these files to the mod.")


if __name__ == "__main__":
    main()

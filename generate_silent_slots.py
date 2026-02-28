#!/usr/bin/env python3
"""
Generate 200 silent OGG Vorbis files for TTS slot pool.

Uses a single placeholder OGG (slot_placeholder.ogg) and copies it to
slot_1.ogg … slot_200.ogg.  Because every slot is a byte-for-byte copy
of the same source file, regenerating slots never produces git diffs.

The placeholder is a 44.1 kHz mono, 0.1 s silent OGG Vorbis file with
X-Ray spatial audio metadata patched in.  If slot_placeholder.ogg does
not exist yet it is created via ffmpeg + ogg_patcher.
"""

import os
import shutil
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
PLACEHOLDER = os.path.join(OUTPUT_DIR, "slot_placeholder.ogg")
NUM_SLOTS = 200
SAMPLE_RATE = 44100  # 44.1kHz — required by X-Ray engine
DURATION = 0.1  # 0.1 seconds (minimum to be accepted by X-Ray)
CHANNELS = 1  # Mono


def _ensure_placeholder() -> str:
    """Create slot_placeholder.ogg if it doesn't already exist.

    Returns:
        Absolute path to the placeholder file.
    """
    if os.path.isfile(PLACEHOLDER):
        return PLACEHOLDER

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Generate silent audio (zeros)
    num_samples = int(SAMPLE_RATE * DURATION)
    audio = np.zeros(num_samples, dtype=np.float32)
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
        raise RuntimeError(
            f"ffmpeg failed creating placeholder: "
            f"{proc.stderr.decode(errors='replace')[:300]}"
        )

    ogg_bytes = proc.stdout
    patched = patch_ogg_xray(ogg_bytes)
    if patched:
        ogg_bytes = patched

    with open(PLACEHOLDER, 'wb') as f:
        f.write(ogg_bytes)

    print(f"  Created placeholder: {PLACEHOLDER} ({len(ogg_bytes)} bytes)")
    return PLACEHOLDER


def main():
    """Copy slot_placeholder.ogg to slot_1..200."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Populating {NUM_SLOTS} TTS slot files from placeholder...")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    placeholder = _ensure_placeholder()

    for slot_num in range(1, NUM_SLOTS + 1):
        dest = os.path.join(OUTPUT_DIR, f"slot_{slot_num}.ogg")
        shutil.copy2(placeholder, dest)

        if slot_num % 50 == 0:
            print(f"  Copied {slot_num}/{NUM_SLOTS}...")

    size_kb = os.path.getsize(placeholder) * NUM_SLOTS // 1024
    print()
    print(f"✓ {NUM_SLOTS} slots populated ({size_kb} KB total)")


if __name__ == "__main__":
    main()

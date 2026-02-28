"""
phase2_enhance.py — Light cleanup and loudness normalization of triaged voice audio.

Reads .ogg files from voice_staging/raw/<theme>/ and writes cleaned .wav files
to voice_staging/clean/<theme>/.  Processing is intentionally minimal to preserve
voice characteristics:

  1. Stationary noise reduction (noisereduce) — removes background hiss/hum
  2. LUFS loudness normalization to -16 LUFS — ensures all voices sound equally
     loud (perceived loudness, not just peak), with a peak limiter at -1 dBFS

Usage:
    python phase2_enhance.py                   # process all themes
    python phase2_enhance.py --only dolg_1     # process one theme
"""

import argparse
from pathlib import Path

try:
    import numpy as np
    import soundfile as sf
    import noisereduce as nr
    import pyloudnorm as pyln
except ImportError:
    print("Please install requirements: pip install soundfile numpy noisereduce pyloudnorm")
    exit(1)

INPUT_DIR = Path(r"voice_staging\raw")
OUTPUT_DIR = Path(r"voice_staging\clean")

# Target loudness in LUFS (EBU R128 standard for speech is -16 to -23)
TARGET_LUFS = -16.0
# Peak limiter ceiling in dBFS (prevents clipping after loudness normalization)
PEAK_CEILING_DB = -1.0
PEAK_CEILING = 10 ** (PEAK_CEILING_DB / 20.0)  # ~0.891


def enhance_file(src: Path, dst: Path) -> None:
    """Apply light noise reduction and LUFS loudness normalization."""
    data, sr = sf.read(src, dtype="float32")

    # Mono mixdown if stereo
    if data.ndim > 1:
        data = data.mean(axis=1)

    # 1. Stationary noise reduction (gentle — prop_decrease=0.75 is lighter than default 1.0)
    data = nr.reduce_noise(y=data, sr=sr, stationary=True, prop_decrease=0.75)

    # 2. LUFS loudness normalization — makes all voices the same perceived volume
    meter = pyln.Meter(sr)
    current_lufs = meter.integrated_loudness(data)

    if not np.isinf(current_lufs):
        data = pyln.normalize.loudness(data, current_lufs, TARGET_LUFS)

        # Peak limiter — if normalization boosted a peak above ceiling, scale down
        peak = np.max(np.abs(data))
        if peak > PEAK_CEILING:
            data = data * (PEAK_CEILING / peak)
    else:
        # Fallback: file is near-silent, just peak-normalize
        peak = np.max(np.abs(data))
        if peak > 0:
            data = data * (PEAK_CEILING / peak)

    data = np.clip(data, -1.0, 1.0)
    sf.write(str(dst), data, sr)


def main():
    parser = argparse.ArgumentParser(
        description="Light cleanup and volume normalization of triaged voice audio"
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated list of theme names to process (skip all others)",
    )
    args = parser.parse_args()
    only_themes = set(args.only.split(",")) if args.only else None

    if not INPUT_DIR.exists():
        print(f"Input directory not found: {INPUT_DIR}")
        print("Please run phase1_triage.py first.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    profiles = sorted(p for p in INPUT_DIR.iterdir() if p.is_dir())
    if only_themes:
        profiles = [p for p in profiles if p.name in only_themes]

    total_cleaned = 0
    for profile in profiles:
        print(f"Enhancing {profile.name}...")
        profile_out_dir = OUTPUT_DIR / profile.name
        profile_out_dir.mkdir(exist_ok=True)

        for filepath in sorted(profile.glob("*.ogg")):
            out_filepath = profile_out_dir / (filepath.stem + ".wav")

            if out_filepath.exists():
                print(f"  Skipping {filepath.name} (already exists)")
                continue

            try:
                print(f"  Processing {filepath.name}...")
                enhance_file(filepath, out_filepath)
                total_cleaned += 1
            except Exception as e:
                print(f"  Failed to process {filepath.name}: {e}")

    print(f"\nDone! Cleaned {total_cleaned} files into {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

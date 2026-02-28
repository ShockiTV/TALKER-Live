"""
phase3_export.py — Bake triaged source audio into .safetensors voice caches.

Reads one audio file per theme from voice_staging/clean/<theme>/ (phase2 output)
with fallback to voice_staging/raw/<theme>/ if no clean version exists, and writes
a <theme>.safetensors to talker_service/voices/.

Usage:
    python phase3_export.py                    # bake all themes
    python phase3_export.py --only dolg_1      # bake one theme
    python phase3_export.py --only dolg_1,csky_2  # bake specific themes
    python phase3_export.py --raw-only         # skip clean/, use raw/ directly
"""

import argparse
from pathlib import Path

# Themes that should never be baked (no usable spoken audio)
EXCLUDE_THEMES = {"no_speach", "story"}

RAW_DIR = Path("voice_staging/raw")
CLEAN_DIR = Path("voice_staging/clean")
OUTPUT_DIR = Path("talker_service/voices")

AUDIO_EXTS = (".ogg", ".wav", ".mp3")


def find_source_audio(theme: str, raw_dir: Path, clean_dir: Path, raw_only: bool) -> Path | None:
    """Find the best source audio file for a theme.
    
    Prefers clean/ (phase2 output) over raw/, unless raw_only is set.
    Supports .wav, .ogg, .mp3 extensions.
    """
    search_dirs = [raw_dir / theme] if raw_only else [clean_dir / theme, raw_dir / theme]
    for d in search_dirs:
        if not d.exists():
            continue
        for ext in AUDIO_EXTS:
            files = sorted(d.glob(f"*{ext}"))
            if files:
                return files[0]
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Bake triaged source audio into .safetensors voice caches"
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated list of theme names to bake (skip all others)",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_DIR,
        help=f"Source directory with per-theme subdirs (default: {RAW_DIR})",
    )
    parser.add_argument(
        "--clean-dir",
        type=Path,
        default=CLEAN_DIR,
        help=f"Phase2 output directory (default: {CLEAN_DIR})",
    )
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="Skip clean/ directory, use raw/ directly",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory for .safetensors files (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    raw_dir: Path = args.raw_dir
    clean_dir: Path = args.clean_dir
    output_dir: Path = args.output_dir
    raw_only: bool = args.raw_only
    only_themes = set(args.only.split(",")) if args.only else None

    # Validate pocket_tts availability
    try:
        from pocket_tts import TTSModel, export_model_state
    except ImportError:
        print("ERROR: pocket_tts is required for voice export")
        print("Install with: pip install pocket-tts")
        raise SystemExit(1)

    if not raw_dir.exists():
        print(f"ERROR: Raw directory not found: {raw_dir}")
        raise SystemExit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Discover themes from raw/ (authoritative list of all triaged themes)
    themes = sorted(
        d.name for d in raw_dir.iterdir()
        if d.is_dir() and d.name not in EXCLUDE_THEMES
    )

    if only_themes:
        themes = [t for t in themes if t in only_themes]

    if not themes:
        print("No themes to process.")
        return

    # Load model once
    print("Loading pocket_tts model...")
    model = TTSModel.load_model()

    baked = 0
    skipped = 0

    for theme in themes:
        source = find_source_audio(theme, raw_dir, clean_dir, raw_only)

        if source is None:
            print(f"  WARNING: Skipping {theme}: no source audio found")
            skipped += 1
            continue

        out_path = output_dir / f"{theme}.safetensors"

        try:
            voice_state = model.get_state_for_audio_prompt(str(source))
            export_model_state(voice_state, str(out_path))
            print(f"  Baked {theme} <- {source}")
            baked += 1
        except Exception as exc:
            print(f"  ERROR: Failed to bake {theme}: {exc}")

    print(f"\nBaked {baked} voices to {output_dir}/")
    if skipped:
        print(f"Skipped {skipped} themes (no source audio)")


if __name__ == "__main__":
    main()

"""
export_voices.py - Bake voice reference audio into .safetensors kvcache files.

Usage: python export_voices.py [--top N] [--denoise] [--df-python PATH] [--force]

Supports two layouts under ../voices/:

  Flat files:
    voices/bandit_1.wav  ->  voices/bandit_1.safetensors

  Anomaly subfolder structure (copied from gamedata/sounds/characters_voice/human/):
    voices/stalker_1/talk/jokes/joke_5.ogg
      -> voices/stalker_1/stalker_1.ogg          (copy of selected source, ONLY if no root file exists)
      -> voices/stalker_1/stalker_1__clean.wav   (denoised, if --denoise)
      -> voices/stalker_1/stalker_1.safetensors  (voice kvcache)

  Manual override: place <stem>.<ext> directly in the theme folder root and the script
  will use it as-is without touching it. Only denoising and export are applied.
  Example: drop stalker_2.ogg into voices/stalker_2/ then run with --denoise --force.

Supported audio formats: .wav, .mp3, .ogg
--force: re-export .safetensors and re-denoise (never re-copies a manual source file)
--denoise: requires --df-python pointing to an env with deepfilternet+torch+torchaudio
"""

import os
import sys
import logging
import argparse
import shutil
import subprocess
import tempfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

AUDIO_EXTS = (".wav", ".mp3", ".ogg")

# Subfolders tried in order - first one that exists and has audio wins.
# talk/jokes: longest single-speaker conversational lines (~300 KB max) - best clone source.
# states/idle: fallback for themes without jokes (monolith_3, zombied_1, woman, etc.).
REFERENCE_SUBFOLDERS = [
    os.path.join("talk", "jokes"),
    os.path.join("states", "idle"),
]

# Number of files to pick. 1 = single longest file (no concatenation artefacts).
DEFAULT_TOP_N = 1

VOICES_DIR = os.path.join(os.path.dirname(__file__), "..", "voices")
WORKER = os.path.join(os.path.dirname(__file__), "denoise_worker.py")


def collect_audio(folder: str, top_n: int) -> list[str]:
    """Return up to top_n audio files from folder, sorted by size descending."""
    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(AUDIO_EXTS) and os.path.isfile(os.path.join(folder, f))
    ]
    files.sort(key=lambda p: os.path.getsize(p), reverse=True)
    return files[:top_n]


def concatenate_audio(paths: list[str], out_path: str) -> None:
    """Concatenate audio files into a single wav using soundfile + numpy."""
    import numpy as np
    import soundfile as sf

    chunks = []
    target_sr = None
    for p in paths:
        data, sr = sf.read(p, always_2d=False)
        if target_sr is None:
            target_sr = sr
        elif sr != target_sr:
            logging.warning("Sample rate mismatch in %s (%d vs %d) - skipping", p, sr, target_sr)
            continue
        if data.ndim > 1:
            data = data.mean(axis=1)
        chunks.append(data)
    sf.write(out_path, np.concatenate(chunks), target_sr)


def denoise_audio(src_path: str, out_path: str, df_python: str) -> None:
    """Apply DeepFilterNet speech enhancement via subprocess in the df venv."""
    result = subprocess.run(
        [df_python, WORKER, src_path, out_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"denoise_worker failed:\n{result.stderr.strip()}")


def export_voices(voices_dir: str, top_n: int = DEFAULT_TOP_N, force: bool = False,
                  denoise: bool = False, df_python: str = "") -> None:
    voices_dir = os.path.abspath(voices_dir)
    if not os.path.isdir(voices_dir):
        logging.error("voices/ directory not found: %s", voices_dir)
        sys.exit(1)

    tasks: list[tuple[str, str | list[str], str | None, str, str]] = []

    for entry in sorted(os.listdir(voices_dir)):
        full = os.path.join(voices_dir, entry)
        if os.path.isfile(full) and entry.lower().endswith(AUDIO_EXTS):
            base = os.path.splitext(entry)[0]
            out = os.path.join(voices_dir, base + ".safetensors")
            tasks.append((entry, full, None, base, out))
        elif os.path.isdir(full):
            out = os.path.join(full, entry + ".safetensors")
            manual = None
            for ext in AUDIO_EXTS:
                candidate = os.path.join(full, entry + ext)
                if os.path.isfile(candidate):
                    manual = candidate
                    break
            if manual:
                label = f"{entry}/  (manual: {os.path.basename(manual)})"
                tasks.append((label, manual, full, entry, out))
            else:
                found = False
                for subfolder in REFERENCE_SUBFOLDERS:
                    candidate_dir = os.path.join(full, subfolder)
                    if not os.path.isdir(candidate_dir):
                        continue
                    candidates = collect_audio(candidate_dir, top_n)
                    if not candidates:
                        continue
                    source = candidates[0] if len(candidates) == 1 else candidates
                    src_name = os.path.basename(candidates[0])
                    label = f"{entry}/  ({os.path.join(subfolder, src_name)})"
                    tasks.append((label, source, full, entry, out))
                    found = True
                    break
                if not found:
                    logging.warning("SKIP  %s/  (no usable audio in %s)", entry,
                                    " or ".join(REFERENCE_SUBFOLDERS))

    if not tasks:
        logging.warning("No audio files or voice subdirectories found in %s", voices_dir)
        return

    try:
        from moshi.models import loaders  # noqa
        from huggingface_hub import hf_hub_download  # noqa
    except ImportError:
        pass

    try:
        from pocket_tts import TTSModel, export_model_state
    except ImportError:
        logging.error("pocket-tts is not installed. Run: pip install pocket-tts")
        sys.exit(1)

    if denoise:
        if not df_python or not os.path.isfile(df_python):
            logging.error("--denoise requires --df-python pointing to a Python with deepfilternet installed")
            sys.exit(1)

    logging.info("Loading TTS model...")
    model = TTSModel.load_model()

    exported = 0
    skipped = 0

    for label, audio_source, theme_dir, stem, out_path in tasks:
        if not force and os.path.exists(out_path):
            logging.info("SKIP  %s  (already exported)", label)
            skipped += 1
            continue

        tmp_concat = None
        try:
            logging.info("Exporting %s", label)

            if isinstance(audio_source, list):
                tmp_concat = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_concat.close()
                concatenate_audio(audio_source, tmp_concat.name)
                raw_path = tmp_concat.name
            else:
                raw_path = audio_source

            if theme_dir is not None:
                src_ext = os.path.splitext(raw_path)[1].lower()
                raw_copy = os.path.join(theme_dir, stem + src_ext)
                is_already_root = os.path.normpath(raw_path) == os.path.normpath(raw_copy)
                if not is_already_root and not os.path.exists(raw_copy):
                    shutil.copy2(raw_path, raw_copy)
                    logging.info("  copied  -> %s", os.path.basename(raw_copy))
                source_for_denoise = raw_copy if os.path.exists(raw_copy) else raw_path

                if denoise:
                    clean_path = os.path.join(theme_dir, stem + "__clean.wav")
                    if force or not os.path.exists(clean_path):
                        logging.info("  denoising...")
                        denoise_audio(source_for_denoise, clean_path, df_python)
                        logging.info("  denoised -> %s", os.path.basename(clean_path))
                    effective_path = clean_path
                else:
                    effective_path = source_for_denoise
            else:
                effective_path = raw_path

            voice_state = model.get_state_for_audio_prompt(effective_path)
            export_model_state(voice_state, out_path)
            logging.info("  -> %s", os.path.basename(out_path))
            exported += 1

        except Exception as exc:
            logging.error("  Failed: %s", exc)
        finally:
            if tmp_concat and os.path.exists(tmp_concat.name):
                os.unlink(tmp_concat.name)

    logging.info("Done. Exported: %d  Skipped: %d  Total: %d", exported, skipped, len(tasks))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Anomaly voice themes to .safetensors")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N, metavar="N",
                        help=f"Number of longest files to use per theme (default: {DEFAULT_TOP_N})")
    parser.add_argument("--force", action="store_true",
                        help="Re-export and re-denoise (never overwrites manual source files)")
    parser.add_argument("--denoise", action="store_true",
                        help="Apply DeepFilterNet noise reduction before export")
    parser.add_argument("--df-python", default="", metavar="PATH",
                        help="Path to Python executable in the deepfilternet venv (required with --denoise)")
    args = parser.parse_args()
    export_voices(VOICES_DIR, top_n=args.top, force=args.force, denoise=args.denoise,
                  df_python=args.df_python)

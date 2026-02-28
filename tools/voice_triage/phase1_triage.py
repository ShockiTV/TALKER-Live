import os
import shutil
import argparse
from pathlib import Path
import warnings

try:
    import librosa
    import numpy as np
except ImportError:
    print("Please install requirements: pip install librosa numpy")
    exit(1)

# Suppress librosa warnings about PySoundFile
warnings.filterwarnings('ignore', category=UserWarning)

SOURCE_DIR = Path(r"F:\Anomaly\tools\_unpacked\sounds\characters_voice\human")
OUTPUT_DIR = Path(r"voice_staging\raw")
EXCLUDE_PROFILES = {"music", "no_speach", "story"}

def is_valid_path(filepath):
    parts = [p.lower() for p in filepath.parts]
    
    # Must be in states/idle or talk
    is_idle = "states" in parts and "idle" in parts
    is_talk = "talk" in parts
    if not (is_idle or is_talk):
        return False
        
    # Must not contain action/combat/drunk words
    bad_words = {"fight", "attack", "death", "hit", "anomaly", "sleep", "drunk", "help", "enemy"}
    
    # Only check the parts after 'human' to avoid false positives from the root path
    try:
        human_idx = parts.index("human")
        relevant_parts = parts[human_idx+1:]
    except ValueError:
        relevant_parts = parts
        
    for part in relevant_parts:
        if any(bad in part for bad in bad_words):
            return False
            
    return True

def analyze_audio(filepath):
    """
    Analyzes an audio file and returns a score. Lower is better (closer to ideal).
    Returns None if the file is outside acceptable parameters.
    """
    try:
        # Load audio (librosa handles ogg natively)
        y, sr = librosa.load(filepath, sr=None, mono=True)
        
        duration = librosa.get_duration(y=y, sr=sr)
        
        # Hard limits - increased to allow longer jokes/stories
        if duration < 4.0 or duration > 15.0:
            return None
            
        # 1. RMS Energy (Loudness)
        # We want a normal conversational volume, not too quiet, not clipping
        rms = librosa.feature.rms(y=y)[0]
        mean_rms = np.mean(rms)
        
        # If it's too quiet or too loud, penalize heavily
        if mean_rms < 0.01 or mean_rms > 0.3:
            return None
            
        # 2. Silence Ratio
        # We want continuous speech, not long pauses
        non_mute_intervals = librosa.effects.split(y, top_db=30)
        active_duration = sum([(end - start) / sr for start, end in non_mute_intervals])
        speech_ratio = active_duration / duration
        
        # If less than 60% of the file is actual speech, reject it (relaxed slightly for longer files)
        if speech_ratio < 0.60:
            return None
            
        # 3. Spectral Flatness (Tonal vs Noise)
        # High flatness = noise/static/breathing. Low flatness = clear tones (speech)
        flatness = librosa.feature.spectral_flatness(y=y)[0]
        mean_flatness = np.mean(flatness)
        
        # Calculate a score (Lower is better)
        # - We want duration close to 8-10 seconds (ideal for TTS)
        # - We want high speech ratio (close to 1.0)
        # - We want low spectral flatness (less noise)
        
        # Reward longer files up to 10 seconds, penalize slightly if too long
        if duration <= 10.0:
            duration_penalty = (10.0 - duration) * 0.5
        else:
            duration_penalty = (duration - 10.0) * 0.2
            
        speech_penalty = (1.0 - speech_ratio) * 5.0
        noise_penalty = mean_flatness * 10.0
        
        total_score = duration_penalty + speech_penalty + noise_penalty
        
        return {
            'filepath': filepath,
            'score': total_score,
            'duration': duration,
            'speech_ratio': speech_ratio,
            'flatness': mean_flatness
        }
        
    except Exception as e:
        # print(f"Error analyzing {filepath}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Triage voice candidates from game audio")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=SOURCE_DIR,
        help=f"Override source directory (default: {SOURCE_DIR})",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated list of theme names to triage (skip all others)",
    )
    args = parser.parse_args()

    source_dir = args.source_dir
    only_themes = set(args.only.split(",")) if args.only else None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}")
        return

    profiles = [p for p in source_dir.iterdir() if p.is_dir() and p.name not in EXCLUDE_PROFILES]

    if only_themes:
        available = {p.name for p in profiles}
        missing = only_themes - available
        for m in sorted(missing):
            print(f"WARNING: Theme '{m}' not found in source directory")
        profiles = [p for p in profiles if p.name in only_themes]
    
    total_candidates = 0
    for profile in profiles:
        print(f"Processing {profile.name}...")
        analyzed_files = []
        
        for root, _, files in os.walk(profile):
            for file in files:
                if not file.endswith(".ogg"):
                    continue
                    
                filepath = Path(root) / file
                if not is_valid_path(filepath):
                    continue
                    
                result = analyze_audio(filepath)
                if result:
                    analyzed_files.append(result)
        
        if not analyzed_files:
            print(f"  No valid files found for {profile.name}")
            continue
            
        # Sort by score (lowest is best)
        analyzed_files.sort(key=lambda x: x['score'])
        
        # Pick the top 5 best scoring files
        selected = analyzed_files[:5]
        
        profile_out_dir = OUTPUT_DIR / profile.name
        profile_out_dir.mkdir(exist_ok=True)
        
        for i, data in enumerate(selected):
            filepath = data['filepath']
            # Include score in filename for reference
            score_str = f"{data['score']:.2f}"
            dest = profile_out_dir / f"rank{i+1}_score{score_str}_{filepath.name}"
            shutil.copy2(filepath, dest)
            total_candidates += 1
        
        print(f"  Saved top {len(selected)} candidates (Best score: {selected[0]['score']:.2f}).")
        
    print(f"\nDone! Staged {total_candidates} files in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()

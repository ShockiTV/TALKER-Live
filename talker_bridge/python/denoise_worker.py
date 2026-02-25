"""
denoise_worker.py - Standalone DeepFilterNet denoising subprocess.
Called by export_voices.py via the .venv_df venv which has deepfilternet installed.

Usage: python denoise_worker.py <src_path> <out_path>
"""
import sys


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: denoise_worker.py <src> <out>", file=sys.stderr)
        sys.exit(1)
    src, out = sys.argv[1], sys.argv[2]
    from df.enhance import enhance, init_df, load_audio, save_audio  # noqa
    model, df_state, _ = init_df()
    audio, _ = load_audio(src, sr=df_state.sr())
    enhanced = enhance(model, df_state, audio)
    save_audio(out, enhanced, df_state.sr())


if __name__ == "__main__":
    main()

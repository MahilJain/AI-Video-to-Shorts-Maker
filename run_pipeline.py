import argparse
import json
import os
import shutil
import subprocess
import sys


SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
LEGACY_DIR = os.path.join(SRC_DIR, "legacy_or_optional")


def run_step(description: str, cmd: list) -> None:
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"\nFAILED at step: {description}")
        sys.exit(1)


def clean_previous_run(video_name: str, audio_name: str) -> None:
    """Remove artifacts from any previous run so a new URL always
    produces fresh output instead of silently reusing stale files."""
    files_to_remove = [
        video_name,
        audio_name,
        "transcript.json",
        "clip_candidates.json",
        "clip_candidates_llm.json",
    ]
    for f in files_to_remove:
        if os.path.exists(f):
            os.remove(f)

    if os.path.exists("clips_output"):
        shutil.rmtree("clips_output")

    print("Cleared previous run's files (video, audio, transcript, clips).")


def main():
    parser = argparse.ArgumentParser(description="Full YouTube-to-Shorts pipeline")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--video-name", default="input_video.mp4", help="Filename to save the downloaded video as")
    parser.add_argument("--audio-name", default="input_audio.mp3", help="Filename for the extracted audio")
    parser.add_argument("--rule-based", action="store_true", help="Use rule-based selection instead of LLM")
    args = parser.parse_args()

    video_name = args.video_name
    audio_name = args.audio_name
    transcript_json = "transcript.json"
    clips_json = "clip_candidates_llm.json" if not args.rule_based else "clip_candidates.json"

    clean_previous_run(video_name, audio_name)

    run_step(
        "Downloading video",
        [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestvideo[height<=720]+bestaudio",
            "--merge-output-format", "mp4",
            "-o", video_name,
            args.url,
        ],
    )

    run_step(
        "Extracting audio",
        [
            "ffmpeg", "-y", "-i", video_name,
            "-vn", "-acodec", "libmp3lame", "-q:a", "4",
            audio_name,
        ],
    )

    run_step(
        "Transcribing audio (Groq whisper-large-v3-turbo)",
        [sys.executable, "-u", os.path.join(SRC_DIR, "transcribe_groq.py"), audio_name],
    )

    if args.rule_based:
        run_step(
            "Selecting segments (rule-based)",
            [sys.executable, "-u", os.path.join(LEGACY_DIR, "select_segments.py"), transcript_json],
        )
    else:
        run_step(
            "Selecting segments (Groq LLM)",
            [sys.executable, "-u", os.path.join(SRC_DIR, "select_segments_groq.py"), transcript_json],
        )

    run_step(
        "Cutting clips",
        [sys.executable, "-u", os.path.join(SRC_DIR, "cut_clips.py"), video_name, clips_json],
    )

    run_step(
        "Reframing to vertical (face-tracked)",
        [sys.executable, "-u", os.path.join(SRC_DIR, "reframe_vertical_tracked.py"), "clips_output"],
    )

    final_dir = os.path.abspath("clips_output/vertical_tracked")
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"Final clips are in: {final_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

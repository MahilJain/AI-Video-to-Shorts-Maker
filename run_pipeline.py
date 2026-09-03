import argparse
import json
import os
import subprocess
import sys


def run_step(description: str, cmd: list) -> None:
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"\nFAILED at step: {description}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Full YouTube-to-Shorts pipeline")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--video-name", default="input_video.mp4", help="Filename to save the downloaded video as")
    parser.add_argument("--use-llm", action="store_true", default=True, help="Use Groq LLM for segment selection (default: True)")
    parser.add_argument("--rule-based", action="store_true", help="Use rule-based selection instead of LLM")
    args = parser.parse_args()

    video_name = args.video_name
    transcript_json = "transcript.json"
    clips_json = "clip_candidates_llm.json" if not args.rule_based else "clip_candidates.json"

    # Step 1: Download
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

    # Step 2: Transcribe
    run_step(
        "Transcribing video",
        [sys.executable, "-u", "transcribe.py", video_name],
    )

    # Step 3: Select segments
    if args.rule_based:
        run_step(
            "Selecting segments (rule-based)",
            [sys.executable, "-u", "select_segments.py", transcript_json],
        )
    else:
        run_step(
            "Selecting segments (Groq LLM)",
            [sys.executable, "-u", "select_segments_groq.py", transcript_json],
        )

    # Step 4: Cut clips
    run_step(
        "Cutting clips",
        [sys.executable, "-u", "cut_clips.py", video_name, clips_json],
    )

    # Step 5: Reframe to vertical (face-tracked)
    run_step(
        "Reframing to vertical (face-tracked)",
        [sys.executable, "-u", "reframe_vertical_tracked.py", "clips_output"],
    )

    # Step 6: Burn captions
    run_step(
        "Generating and burning captions",
        [
            sys.executable, "-u", "generate_captions.py",
            transcript_json, clips_json, "clips_output/vertical_tracked",
        ],
    )

    final_dir = os.path.abspath("clips_output/vertical_tracked/captioned")
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"Final clips are in: {final_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

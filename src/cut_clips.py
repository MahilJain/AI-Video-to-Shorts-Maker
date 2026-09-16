"""Cut selected timestamp ranges from the source video with ffmpeg."""

import os
import sys
from utils import load_json, resolve_project_path, run_ffmpeg


def cut_clip(source_video: str, start: float, end: float, output_path: str) -> None:
    duration = end - start
    cmd = [
        "ffmpeg",
        "-y",  # overwrite existing files without asking
        "-ss", str(start),
        "-i", source_video,
        "-t", str(duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        output_path,
    ]
    run_ffmpeg(cmd, output_path)


def main():
    if len(sys.argv) < 3:
        print("Usage: python cut_clips.py <source_video> <clips_json>")
        print("Example: python cut_clips.py test_video2.mp4 clip_candidates_llm.json")
        return

    source_video = resolve_project_path(sys.argv[1])
    clips_json = resolve_project_path(sys.argv[2])

    if not os.path.exists(source_video):
        print(f"Error: source video '{source_video}' not found.")
        return

    clips = load_json(clips_json)
    output_dir = resolve_project_path("clips_output")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Cutting {len(clips)} clips from {source_video}...\n")

    for i, clip in enumerate(clips, 1):
        start = clip["start"]
        end = clip["end"]
        output_path = os.path.join(output_dir, f"clip_{i}.mp4")
        cut_clip(source_video, start, end, output_path)

    print(f"\nDone. Clips saved in '{os.path.abspath(output_dir)}'")


if __name__ == "__main__":
    main()

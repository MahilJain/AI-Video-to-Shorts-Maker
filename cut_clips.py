import json
import os
import subprocess
import sys


def load_clips(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg failed for {output_path}:")
        print(result.stderr[-500:])  # last 500 chars of error, usually the useful part
    else:
        print(f"Saved: {output_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python cut_clips.py <source_video> <clips_json>")
        print("Example: python cut_clips.py test_video2.mp4 clip_candidates_llm.json")
        return

    source_video = sys.argv[1]
    clips_json = sys.argv[2]

    if not os.path.exists(source_video):
        print(f"Error: source video '{source_video}' not found.")
        return

    clips = load_clips(clips_json)
    output_dir = "clips_output"
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

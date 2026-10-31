"""Optional center-crop vertical reframing fallback without face tracking."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import resolve_project_path, run_ffmpeg


def reframe_to_vertical(input_path: str, output_path: str) -> None:
    # Crop to 9:16 centered, then scale to 1080x1920
    vf = (
        "crop=ih*9/16:ih,"
        "scale=1080:1920"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-c:a", "aac",
        output_path,
    ]
    run_ffmpeg(cmd, output_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python reframe_vertical.py <clips_folder>")
        print("Example: python reframe_vertical.py clips_output")
        return

    clips_folder = resolve_project_path(sys.argv[1])
    output_dir = os.path.join(clips_folder, "vertical")
    os.makedirs(output_dir, exist_ok=True)

    clip_files = [f for f in os.listdir(clips_folder) if f.endswith(".mp4")]

    print(f"Reframing {len(clip_files)} clips to vertical 9:16...\n")

    for filename in clip_files:
        input_path = os.path.join(clips_folder, filename)
        output_path = os.path.join(output_dir, filename)
        reframe_to_vertical(input_path, output_path)

    print(f"\nDone. Vertical clips saved in '{os.path.abspath(output_dir)}'")


if __name__ == "__main__":
    main()

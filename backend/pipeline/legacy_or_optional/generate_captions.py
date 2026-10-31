"""Optional caption generator that burns grouped word timestamps into vertical clips."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_json, resolve_project_path, run_ffmpeg


def get_words_in_range(transcript: list, clip_start: float, clip_end: float) -> list:
    """Extract all words falling within [clip_start, clip_end], with timestamps
    re-based to be relative to the clip's own start (0.0 = clip start)."""
    words = []
    for segment in transcript:
        for w in segment.get("words", []):
            if w["start"] >= clip_start and w["end"] <= clip_end:
                words.append({
                    "word": w["word"].strip(),
                    "start": round(w["start"] - clip_start, 2),
                    "end": round(w["end"] - clip_start, 2),
                })
    return words


def seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format: H:MM:SS.CS"""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass_file(words: list, output_path: str, words_per_group: int = 4) -> None:
    """Builds an .ass subtitle file showing a few words at a time,
    styled bold with a highlight color, centered near the bottom-middle of a vertical frame."""

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]

    # Group words into small chunks for on-screen readability
    for i in range(0, len(words), words_per_group):
        group = words[i:i + words_per_group]
        if not group:
            continue
        start_time = seconds_to_ass_time(group[0]["start"])
        end_time = seconds_to_ass_time(group[-1]["end"])
        text = " ".join(w["word"] for w in group).upper()
        lines.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def burn_captions(video_path: str, ass_path: str, output_path: str) -> None:
    # ffmpeg needs escaped colons/backslashes in filter paths on Windows
    escaped_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
    vf = f"ass={escaped_ass_path}"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-c:a", "copy",
        output_path,
    ]
    run_ffmpeg(cmd, output_path, error_tail=800)


def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_captions.py <transcript_json> <clips_json> [vertical_clips_folder]")
        print("Example: python generate_captions.py transcript.json clip_candidates_llm.json clips_output/vertical_tracked")
        return

    transcript_path = sys.argv[1]
    clips_json_path = sys.argv[2]
    vertical_folder = resolve_project_path(sys.argv[3]) if len(sys.argv) > 3 else resolve_project_path("clips_output/vertical_tracked")

    transcript = load_json(transcript_path)
    clips = load_json(clips_json_path)

    output_dir = os.path.join(vertical_folder, "captioned")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Generating captions for {len(clips)} clips...\n")

    for i, clip in enumerate(clips, 1):
        clip_video = os.path.join(vertical_folder, f"clip_{i}.mp4")
        if not os.path.exists(clip_video):
            print(f"Skipping clip_{i}: video not found at {clip_video}")
            continue

        print(f"Processing clip_{i}...")
        words = get_words_in_range(transcript, clip["start"], clip["end"])

        if not words:
            print(f"  No words found in range for clip_{i}, skipping captions.")
            continue

        ass_path = os.path.join(output_dir, f"clip_{i}.ass")
        build_ass_file(words, ass_path)

        output_video = os.path.join(output_dir, f"clip_{i}.mp4")
        burn_captions(clip_video, ass_path, output_video)

    print(f"\nDone. Captioned clips saved in '{os.path.abspath(output_dir)}'")


if __name__ == "__main__":
    main()

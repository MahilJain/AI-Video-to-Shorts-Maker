import argparse
import json
import os
import sys
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

MODEL = "whisper-large-v3-turbo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe a video with Groq's hosted Whisper API.")
    parser.add_argument(
        "video_filename",
        nargs="?",
        default="test_video.mp4",
        help="Video filename or path (default: test_video.mp4)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    video_path = os.path.abspath(args.video_filename)

    if not os.path.isfile(video_path):
        raise FileNotFoundError(video_path)

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set (check your .env file).")

    client = Groq(api_key=api_key)

    print(f"Sending {os.path.basename(video_path)} to Groq ({MODEL}) for transcription...")
    print("(Groq accepts audio/video files directly — no separate audio extraction needed)")

    with open(video_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(video_path), f.read()),
            model=MODEL,
            language="hi",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )

    print(f"Detected language: {transcription.language}")
    print(f"Duration: {transcription.duration:.2f} seconds\n")

    transcript_data = []
    words_all = transcription.words if hasattr(transcription, "words") else []

    for segment in transcription.segments:
        seg_start = segment["start"] if isinstance(segment, dict) else segment.start
        seg_end = segment["end"] if isinstance(segment, dict) else segment.end
        seg_text = segment["text"] if isinstance(segment, dict) else segment.text

        words_data = []
        for w in words_all:
            w_start = w["start"] if isinstance(w, dict) else w.start
            w_end = w["end"] if isinstance(w, dict) else w.end
            w_word = w["word"] if isinstance(w, dict) else w.word
            if w_start >= seg_start and w_end <= seg_end:
                words_data.append({
                    "word": w_word,
                    "start": round(w_start, 2),
                    "end": round(w_end, 2),
                })

        segment_data = {
            "start": round(seg_start, 2),
            "end": round(seg_end, 2),
            "text": seg_text.strip(),
            "words": words_data,
        }
        transcript_data.append(segment_data)
        print(f"[{segment_data['start']}s -> {segment_data['end']}s] {segment_data['text']}")

    output_path = os.path.join(os.path.dirname(video_path), "transcript.json")
    print(f"\nWriting transcript to: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, indent=2, ensure_ascii=False)

    print(f"Saved transcript to {output_path}")


if __name__ == "__main__":
    main()

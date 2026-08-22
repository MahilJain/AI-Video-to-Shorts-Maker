import argparse
import json
import os


def parse_args() -> argparse.Namespace:
    """Parse the video filename supplied on the command line."""
    parser = argparse.ArgumentParser(description="Transcribe a video with faster-whisper.")
    parser.add_argument(
        "video_filename",
        nargs="?",
        default="test_video.mp4",
        help="Video filename or path (default: test_video.mp4)",
    )
    return parser.parse_args()


def main() -> None:
    """Transcribe a video and save its timestamped transcript as JSON."""
    args = parse_args()
    video_path = os.path.abspath(args.video_filename)

    try:
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)

        from faster_whisper import WhisperModel

        # Use the local CPU-friendly model so transcription does not require a GPU.
        model = WhisperModel("base", device="cpu", compute_type="int8")
        # Request word timestamps because later stages use precise clip and caption timing.
        segments, info = model.transcribe(video_path, word_timestamps=True)

        print(f"Detected language: {info.language}")
        print(f"Duration: {info.duration:.2f} seconds\n")

        transcript_data = []

        for segment in segments:
            words_data = []
            if segment.words:
                # Preserve each word's timing for future word-level captions.
                for word in segment.words:
                    words_data.append({
                        "word": word.word,
                        "start": round(word.start, 2),
                        "end": round(word.end, 2)
                    })

            # Store sentence-level timing together with its optional word-level details.
            segment_data = {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
                "words": words_data
            }
            transcript_data.append(segment_data)
            print(f"[{segment_data['start']}s -> {segment_data['end']}s] {segment_data['text']}")

    except FileNotFoundError:
        raise SystemExit(f"Error: video file does not exist: {video_path}")
    except OSError as error:
        raise SystemExit(f"Error loading or transcribing video '{video_path}': {error}")

    output_path = os.path.abspath("transcript.json")
    print(f"Writing transcript to: {output_path}")
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(transcript_data, file, indent=2, ensure_ascii=False)

    print(f"Saved transcript to {output_path}")


if __name__ == "__main__":
    main()

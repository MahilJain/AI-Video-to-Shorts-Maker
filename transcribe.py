import json
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")

video_path = "test_video.mp4"

segments, info = model.transcribe(video_path, word_timestamps=True)

print(f"Detected language: {info.language}")
print(f"Duration: {info.duration:.2f} seconds\n")

transcript_data = []

for segment in segments:
    words_data = []
    if segment.words:
        for word in segment.words:
            words_data.append({
                "word": word.word,
                "start": round(word.start, 2),
                "end": round(word.end, 2)
            })

    segment_data = {
        "start": round(segment.start, 2),
        "end": round(segment.end, 2),
        "text": segment.text.strip(),
        "words": words_data
    }
    transcript_data.append(segment_data)
    print(f"[{segment_data['start']}s -> {segment_data['end']}s] {segment_data['text']}")

with open("transcript.json", "w", encoding="utf-8") as f:
    json.dump(transcript_data, f, indent=2, ensure_ascii=False)

print("\nSaved transcript to transcript.json")

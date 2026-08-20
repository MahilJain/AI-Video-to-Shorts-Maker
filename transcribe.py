from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")

video_path = "test_video.mp4"

segments, info = model.transcribe(video_path, word_timestamps=True)

print(f"Detected language: {info.language}")
print(f"Duration: {info.duration:.2f} seconds\n")

for segment in segments:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")

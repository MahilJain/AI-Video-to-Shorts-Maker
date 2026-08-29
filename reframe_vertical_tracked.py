import os
import subprocess
import sys
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision


MODEL_PATH = "blaze_face_short_range.tflite"


def detect_face_centers(video_path: str, sample_every_n_frames: int = 5) -> list:
    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.5)
    detector = vision.FaceDetector.create_from_options(options)

    cap = cv2.VideoCapture(video_path)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    centers = []
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_every_n_frames == 0:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = detector.detect(mp_image)

            if result.detections:
                box = result.detections[0].bounding_box
                face_center_x = (box.origin_x + box.width / 2) / frame_width
                centers.append(face_center_x)
            else:
                centers.append(None)

        frame_idx += 1

    cap.release()
    detector.close()
    return centers, frame_width


def smooth_centers(centers: list, window: int = 5) -> list:
    filled = []
    last_valid = 0.5
    for c in centers:
        if c is not None:
            last_valid = c
        filled.append(last_valid)

    smoothed = []
    for i in range(len(filled)):
        start = max(0, i - window // 2)
        end = min(len(filled), i + window // 2 + 1)
        smoothed.append(sum(filled[start:end]) / (end - start))

    return smoothed


def reframe_to_vertical_tracked(input_path: str, output_path: str) -> None:
    cap = cv2.VideoCapture(input_path)
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_width_check = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()

    crop_width = int(frame_height * 9 / 16)

    print(f"  Detecting face position...")
    centers, frame_width = detect_face_centers(input_path)
    smoothed = smooth_centers(centers)

    avg_center = sum(smoothed) / len(smoothed) if smoothed else 0.5
    center_px = avg_center * frame_width
    x_offset = int(center_px - crop_width / 2)
    x_offset = max(0, min(x_offset, frame_width - crop_width))

    print(f"  Face-centered crop x-offset: {x_offset}px (frame width: {frame_width}px)")

    vf = f"crop={crop_width}:{frame_height}:{x_offset}:0,scale=1080:1920"
    cmd = [
        "ffmpeg", "-y", "-i", input_path, "-vf", vf,
        "-c:v", "libx264", "-c:a", "aac", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ffmpeg failed for {output_path}:")
        print(result.stderr[-500:])
    else:
        print(f"  Saved: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python reframe_vertical_tracked.py <clips_folder>")
        return

    clips_folder = sys.argv[1]
    output_dir = os.path.join(clips_folder, "vertical_tracked")
    os.makedirs(output_dir, exist_ok=True)

    clip_files = [f for f in os.listdir(clips_folder) if f.endswith(".mp4")]
    print(f"Reframing {len(clip_files)} clips with face tracking...\n")

    for filename in clip_files:
        print(f"Processing {filename}...")
        input_path = os.path.join(clips_folder, filename)
        output_path = os.path.join(output_dir, filename)
        reframe_to_vertical_tracked(input_path, output_path)

    print(f"\nDone. Vertical clips saved in '{os.path.abspath(output_dir)}'")


if __name__ == "__main__":
    main()

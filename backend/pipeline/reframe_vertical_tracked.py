"""Track visible faces and reframe each selected clip to 9:16."""

import json
import os
import sys
import tempfile
from bisect import bisect_right

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .utils import resolve_project_path, run_ffmpeg


MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "blaze_face_short_range.tflite",
)
SAMPLE_EVERY_N_FRAMES = 5
MOUTH_MOTION_THRESHOLD = 0.018


def speech_intervals(
    transcript: list[dict], clip_start: float, clip_end: float
) -> list[tuple[float, float]]:
    """Return clip-relative speech intervals using word timing where available."""
    intervals = []
    for segment in transcript:
        words = segment.get("words")
        timed_words = words if isinstance(words, list) and words else [segment]
        for word in timed_words:
            start = word.get("start")
            end = word.get("end")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                continue
            start = max(float(start), clip_start)
            end = min(float(end), clip_end)
            if start < end:
                intervals.append((start - clip_start, end - clip_start))
    return intervals


def is_speech_time(timestamp: float, intervals: list[tuple[float, float]]) -> bool:
    return any(start <= timestamp <= end for start, end in intervals)


def choose_active_face(
    faces: list[dict], speech_active: bool, previous_face_id: int | None
) -> dict | None:
    """Prefer a visibly moving mouth during speech; otherwise retain the speaker."""
    if not faces:
        return None

    faces_by_id = {face["id"]: face for face in faces}
    previous_face = faces_by_id.get(previous_face_id)
    if speech_active:
        ranked_faces = sorted(
            faces, key=lambda face: (face["mouth_motion"], face["area"]), reverse=True
        )
        strongest = ranked_faces[0]
        second_motion = ranked_faces[1]["mouth_motion"] if len(ranked_faces) > 1 else 0
        has_clear_speech_motion = (
            strongest["mouth_motion"] >= MOUTH_MOTION_THRESHOLD
            and strongest["mouth_motion"] >= second_motion * 1.2
        )
        if has_clear_speech_motion:
            return strongest
        if previous_face is not None:
            return previous_face

    if previous_face is not None:
        return previous_face
    return max(faces, key=lambda face: face["area"])


def _mouth_patch(gray_frame, box):
    x, y, width, height = box
    left = max(0, x + int(width * 0.2))
    right = min(gray_frame.shape[1], x + int(width * 0.8))
    top = max(0, y + int(height * 0.55))
    bottom = min(gray_frame.shape[0], y + int(height * 0.92))
    if right <= left or bottom <= top:
        return None
    return cv2.resize(gray_frame[top:bottom, left:right], (32, 16))


def _match_faces(detections: list[dict], tracks: dict[int, dict], sample_index: int) -> None:
    available_track_ids = {
        track_id
        for track_id, track in tracks.items()
        if sample_index - track["last_sample"] <= 2
    }
    matches = []
    for detection_index, detection in enumerate(detections):
        cx, cy = detection["center"]
        for track_id in available_track_ids:
            track = tracks[track_id]
            old_x, old_y = track["center"]
            distance = ((cx - old_x) ** 2 + (cy - old_y) ** 2) ** 0.5
            if distance <= 0.2:
                matches.append((distance, detection_index, track_id))

    assigned_detections = set()
    assigned_tracks = set()
    for _, detection_index, track_id in sorted(matches):
        if detection_index in assigned_detections or track_id in assigned_tracks:
            continue
        detection = detections[detection_index]
        track = tracks[track_id]
        previous_patch = track["mouth_patch"]
        current_patch = detection["mouth_patch"]
        detection["mouth_motion"] = (
            float(cv2.absdiff(previous_patch, current_patch).mean()) / 255
            if previous_patch is not None and current_patch is not None
            else 0.0
        )
        detection["id"] = track_id
        track.update(
            center=detection["center"],
            mouth_patch=current_patch,
            last_sample=sample_index,
        )
        assigned_detections.add(detection_index)
        assigned_tracks.add(track_id)

    for detection_index, detection in enumerate(detections):
        if detection_index in assigned_detections:
            continue
        track_id = max(tracks, default=-1) + 1
        detection["id"] = track_id
        detection["mouth_motion"] = 0.0
        tracks[track_id] = {
            "center": detection["center"],
            "mouth_patch": detection["mouth_patch"],
            "last_sample": sample_index,
        }


def detect_face_centers(
    video_path: str, speech: list[tuple[float, float]]
) -> tuple[list[tuple[int, float]], int, int, float, int]:
    """Sample faces and choose the visible, mouth-moving speaker at speech times."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video for face tracking: {video_path}")

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps > 0 else 25.0
    if frame_width <= 0 or frame_height <= 0:
        cap.release()
        raise RuntimeError(f"Video has invalid dimensions: {video_path}")

    options = vision.FaceDetectorOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        min_detection_confidence=0.5,
    )
    detector = vision.FaceDetector.create_from_options(options)
    tracks = {}
    anchors = []
    previous_face_id = None
    frame_index = 0
    sample_index = 0
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_index % SAMPLE_EVERY_N_FRAMES == 0:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = detector.detect(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                )
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                detections = []
                for item in result.detections or []:
                    box = item.bounding_box
                    x = max(0, box.origin_x)
                    y = max(0, box.origin_y)
                    width = min(box.width, frame_width - x)
                    height = min(box.height, frame_height - y)
                    if width <= 0 or height <= 0:
                        continue
                    detections.append(
                        {
                            "center": ((x + width / 2) / frame_width, (y + height / 2) / frame_height),
                            "area": width * height,
                            "mouth_patch": _mouth_patch(gray_frame, (x, y, width, height)),
                        }
                    )

                _match_faces(detections, tracks, sample_index)
                timestamp = frame_index / fps
                face = choose_active_face(
                    detections,
                    is_speech_time(timestamp, speech),
                    previous_face_id,
                )
                if face is not None:
                    previous_face_id = face["id"]
                    center_x = face["center"][0]
                else:
                    center_x = anchors[-1][1] if anchors else 0.5
                anchors.append((frame_index, center_x))
                sample_index += 1
            frame_index += 1
    finally:
        cap.release()
        detector.close()

    return anchors, frame_width, frame_height, fps, frame_index


def smooth_centers(anchors: list[tuple[int, float]], alpha: float = 0.25) -> list[tuple[int, float]]:
    if not anchors:
        return []
    smoothed = [anchors[0]]
    previous_center = anchors[0][1]
    for frame_index, center in anchors[1:]:
        previous_center += alpha * (center - previous_center)
        smoothed.append((frame_index, previous_center))
    return smoothed


def center_at_frame(anchors: list[tuple[int, float]], frame_index: int) -> float:
    if not anchors or frame_index <= anchors[0][0]:
        return anchors[0][1] if anchors else 0.5
    next_index = bisect_right(anchors, (frame_index, float("inf")))
    if next_index == len(anchors):
        return anchors[-1][1]
    previous_frame, previous_center = anchors[next_index - 1]
    next_frame, next_center = anchors[next_index]
    fraction = (frame_index - previous_frame) / (next_frame - previous_frame)
    return previous_center + fraction * (next_center - previous_center)


def reframe_to_vertical_tracked(
    input_path: str,
    output_path: str,
    speech: list[tuple[float, float]] | None = None,
) -> None:
    print("  Detecting faces and identifying the visible speaker...")
    anchors, frame_width, frame_height, fps, _ = detect_face_centers(
        input_path, speech or []
    )
    anchors = smooth_centers(anchors)

    if frame_width / frame_height > 9 / 16:
        crop_width = int(frame_height * 9 / 16)
        crop_height = frame_height
    else:
        crop_width = frame_width
        crop_height = int(frame_width * 16 / 9)

    output_dir = os.path.dirname(os.path.abspath(output_path))
    temp_file = tempfile.NamedTemporaryFile(
        prefix="reframe_", suffix=".mp4", dir=output_dir, delete=False
    )
    temp_path = temp_file.name
    temp_file.close()

    cap = cv2.VideoCapture(input_path)
    writer = cv2.VideoWriter(
        temp_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (1080, 1920),
    )
    if not cap.isOpened() or not writer.isOpened():
        cap.release()
        writer.release()
        os.remove(temp_path)
        raise RuntimeError("Could not open video reader or vertical video writer.")

    frame_index = 0
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            center_x = center_at_frame(anchors, frame_index) * frame_width
            x_offset = int(center_x - crop_width / 2)
            x_offset = max(0, min(x_offset, frame_width - crop_width))
            y_offset = max(0, (frame_height - crop_height) // 2)
            crop = frame[
                y_offset : y_offset + crop_height,
                x_offset : x_offset + crop_width,
            ]
            writer.write(cv2.resize(crop, (1080, 1920), interpolation=cv2.INTER_AREA))
            frame_index += 1
    finally:
        cap.release()
        writer.release()

    try:
        if not run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                temp_path,
                "-i",
                input_path,
                "-map",
                "0:v:0",
                "-map",
                "1:a?",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-shortest",
                output_path,
            ],
            output_path,
        ):
            raise RuntimeError(f"Could not encode reframed clip: {output_path}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _load_json(path: str) -> list[dict]:
    with open(resolve_project_path(path), encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return value


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m backend.pipeline.reframe_vertical_tracked "
            "<clips_folder> [transcript.json] [clip_candidates.json]"
        )
        return

    clips_folder = resolve_project_path(sys.argv[1])
    transcript = _load_json(sys.argv[2]) if len(sys.argv) > 2 else []
    candidates = _load_json(sys.argv[3]) if len(sys.argv) > 3 else []
    output_dir = os.path.join(clips_folder, "vertical_tracked")
    os.makedirs(output_dir, exist_ok=True)

    clip_files = sorted(
        (filename for filename in os.listdir(clips_folder) if filename.endswith(".mp4")),
        key=lambda filename: (
            0,
            int(filename.removeprefix("clip_").removesuffix(".mp4")),
        )
        if filename.removeprefix("clip_").removesuffix(".mp4").isdigit()
        else (1, filename),
    )
    print(f"Reframing {len(clip_files)} clips with active-speaker tracking...\n")

    for filename in clip_files:
        print(f"Processing {filename}...")
        number = filename.removeprefix("clip_").removesuffix(".mp4")
        candidate = (
            candidates[int(number) - 1]
            if number.isdigit() and int(number) <= len(candidates)
            else {}
        )
        start = candidate.get("start", 0)
        end = candidate.get("end", start)
        speech = speech_intervals(transcript, float(start), float(end))
        input_path = os.path.join(clips_folder, filename)
        output_path = os.path.join(output_dir, filename)
        reframe_to_vertical_tracked(input_path, output_path, speech)

    print(f"\nDone. Vertical clips saved in '{os.path.abspath(output_dir)}'")


if __name__ == "__main__":
    main()

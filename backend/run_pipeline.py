"""Orchestrate the download, transcription, selection, cutting, and reframing stages."""

import argparse
import os
import shutil
import subprocess
import sys

from .pipeline.utils import (
    GROQ_API_KEY,
    PROJECT_ROOT,
    load_project_env,
    resolve_project_path,
)


PIPELINE_PACKAGE = "backend.pipeline"


def build_download_command(video_name: str, url: str) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "-f",
        "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "--merge-output-format",
        "mp4",
        "--remux-video",
        "mp4",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--extractor-retries",
        "3",
        "--file-access-retries",
        "3",
        "--socket-timeout",
        "30",
        "-o",
        video_name,
    ]
    cookies_file = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    cookies_browser = os.environ.get("YTDLP_COOKIES_FROM_BROWSER", "").strip()
    if cookies_file:
        cookies_path = resolve_project_path(os.path.expandvars(cookies_file))
        if not os.path.isfile(cookies_path):
            raise FileNotFoundError(
                "YTDLP_COOKIES_FILE does not exist: "
                f"{cookies_path}. Configure a Netscape-format cookies file."
            )
        command.extend(["--cookies", cookies_path])
    elif cookies_browser:
        command.extend(["--cookies-from-browser", cookies_browser])
    command.append(url)
    return command


def run_download_attempt(command: list[str]) -> tuple[int, bool]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        cwd=PROJECT_ROOT,
    )
    assert process.stdout is not None
    cookie_database_error = False
    with process.stdout:
        for line in process.stdout:
            print(line, end="", flush=True)
            lowered_line = line.lower()
            if "could not copy" in lowered_line and "cookie database" in lowered_line:
                cookie_database_error = True
    return process.wait(), cookie_database_error


def run_download_step(command: list[str]) -> None:
    print(f"\n{'='*60}")
    print("STEP: Downloading video")
    print(f"{'='*60}")
    return_code, cookie_database_error = run_download_attempt(command)

    if (
        return_code != 0
        and cookie_database_error
        and "--cookies-from-browser" in command
    ):
        print(
            "\nCould not read the browser cookie database. Retrying without browser "
            "cookies; if this video requires sign-in, close the browser or configure "
            "YTDLP_COOKIES_FILE."
        )
        retry_command = command.copy()
        cookie_option_index = retry_command.index("--cookies-from-browser")
        del retry_command[cookie_option_index : cookie_option_index + 2]
        return_code, _ = run_download_attempt(retry_command)

    if return_code != 0:
        print("\nFAILED at step: Downloading video")
        sys.exit(1)


def run_step(description: str, cmd: list) -> None:
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, capture_output=False, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"\nFAILED at step: {description}")
        sys.exit(1)


def clean_previous_run(video_name: str, audio_name: str) -> None:
    """Remove artifacts from any previous run so a new URL always
    produces fresh output instead of silently reusing stale files."""
    files_to_remove = [video_name, audio_name, "transcript.json", "clip_candidates.json", "clip_candidates_llm.json"]
    for f in files_to_remove:
        path = resolve_project_path(f)
        if os.path.exists(path):
            os.remove(path)

    clips_dir = resolve_project_path("clips_output")
    if os.path.exists(clips_dir):
        # Clear outputs so a new URL cannot silently retain clips from a prior run.
        shutil.rmtree(clips_dir)

    print("Cleared previous run's files (video, audio, transcript, clips).")


def main():
    load_project_env()
    parser = argparse.ArgumentParser(description="Full YouTube-to-Shorts pipeline")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--video-name", default="input_video.mp4", help="Filename to save the downloaded video as")
    parser.add_argument(
        "--audio-name",
        default="input_audio.mp3",
        help="Legacy cleanup filename; audio extraction is no longer needed",
    )
    parser.add_argument("--rule-based", action="store_true", help="Use rule-based selection instead of LLM")
    args = parser.parse_args()

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the project root .env file "
            "before running the pipeline."
        )

    video_name = resolve_project_path(args.video_name)
    audio_name = resolve_project_path(args.audio_name)
    transcript_json = "transcript.json"
    clips_json = "clip_candidates_llm.json" if not args.rule_based else "clip_candidates.json"

    clean_previous_run(video_name, audio_name)

    run_download_step(build_download_command(video_name, args.url))

    run_step(
        "Transcribing video (Groq whisper-large-v3-turbo)",
        [sys.executable, "-u", "-m", f"{PIPELINE_PACKAGE}.transcribe_groq", video_name],
    )

    if args.rule_based:
        run_step(
            "Selecting segments (rule-based)",
            [
                sys.executable,
                "-u",
                "-m",
                f"{PIPELINE_PACKAGE}.select_segments",
                resolve_project_path(transcript_json),
            ],
        )
    else:
        run_step(
            "Selecting segments (Groq LLM)",
            [
                sys.executable,
                "-u",
                "-m",
                f"{PIPELINE_PACKAGE}.select_segments_groq",
                resolve_project_path(transcript_json),
            ],
        )

    run_step(
        "Cutting clips",
        [
            sys.executable,
            "-u",
            "-m",
            f"{PIPELINE_PACKAGE}.cut_clips",
            video_name,
            resolve_project_path(clips_json),
        ],
    )

    run_step(
        "Reframing to vertical (face-tracked)",
        [
            sys.executable,
            "-u",
            "-m",
            f"{PIPELINE_PACKAGE}.reframe_vertical_tracked",
            resolve_project_path("clips_output"),
            resolve_project_path(transcript_json),
            resolve_project_path(clips_json),
        ],
    )

    final_dir = resolve_project_path("clips_output/vertical_tracked")
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"Final clips are in: {final_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

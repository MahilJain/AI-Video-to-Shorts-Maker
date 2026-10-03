"""FastAPI wrapper for the YouTube-to-shorts pipeline."""

import json
import logging
import re
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parent
CLIPS_DIR = PROJECT_ROOT / "clips_output" / "vertical_tracked"
JOB_RESULTS_DIR = PROJECT_ROOT / "clips_output_jobs"
CANDIDATES_PATH = PROJECT_ROOT / "clip_candidates_llm.json"
STEP_NAMES = {
    "Downloading video": "downloading",
    "Transcribing video": "transcribing",
    "Selecting segments": "selecting_segments",
    "Cutting clips": "cutting",
    "Reframing to vertical": "reframing",
}
MAX_ERROR_LENGTH = 4000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Shorts Clipper API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(
    _request: Request, _error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid request. Provide a YouTube URL as a string."},
    )


jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()
pipeline_state = {"active_job_id": None}


class PipelineRequest(BaseModel):
    url: str = Field(max_length=2048)

    class Config:
        extra = "forbid"


def is_youtube_url(value: str) -> bool:
    try:
        parsed = urlsplit(value.strip())
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    if host not in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
    }:
        return False

    path_parts = [part for part in parsed.path.split("/") if part]
    if host == "youtu.be":
        return bool(path_parts and re.fullmatch(r"[\w-]+", path_parts[0]))

    if parsed.path.rstrip("/") == "/watch":
        return bool(parse_qs(parsed.query).get("v", [""])[0])
    return bool(
        len(path_parts) >= 2
        and path_parts[0] in {"shorts", "embed", "live", "v"}
        and re.fullmatch(r"[\w-]+", path_parts[1])
    )


def update_job(job_id: str, **updates: Any) -> None:
    with jobs_lock:
        jobs[job_id].update(updates)


def read_candidates() -> tuple[list[dict[str, Any]], str | None]:
    try:
        with CANDIDATES_PATH.open(encoding="utf-8") as candidates_file:
            candidates = json.load(candidates_file)
    except FileNotFoundError:
        return [], "Clip candidate metadata was not produced."
    except (OSError, json.JSONDecodeError) as error:
        logger.warning("Could not read clip candidate metadata: %s", error)
        return [], "Clip candidate metadata could not be read."

    if not isinstance(candidates, list):
        return [], "Clip candidate metadata has an unexpected format."
    return [item for item in candidates if isinstance(item, dict)], None


def collect_clips() -> tuple[list[dict[str, Any]], str | None]:
    if not CLIPS_DIR.is_dir():
        return [], "The pipeline did not create the vertical clips directory."

    candidate_list, warning = read_candidates()
    candidates_by_number = {
        index: candidate for index, candidate in enumerate(candidate_list, start=1)
    }
    clip_paths = sorted(
        CLIPS_DIR.glob("*.mp4"),
        key=lambda path: (
            0,
            int(path.stem.removeprefix("clip_")),
        )
        if path.stem.removeprefix("clip_").isdigit()
        else (1, path.name),
    )
    clips = []
    for path in clip_paths:
        number_text = path.stem.removeprefix("clip_")
        candidate = candidates_by_number.get(int(number_text)) if number_text.isdigit() else None
        start = candidate.get("start") if candidate else None
        end = candidate.get("end") if candidate else None
        duration = None
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            duration = max(0.0, float(end) - float(start))

        clips.append(
            {
                "filename": path.name,
                "duration": duration,
                "reason": candidate.get("reason") if candidate else None,
                "url": f"/api/jobs/{{job_id}}/clips/{path.name}",
            }
        )
    return clips, warning


def run_pipeline_job(job_id: str, url: str) -> None:
    output_lines: list[str] = []
    try:
        update_job(job_id, status="running", progress="downloading")
        process = subprocess.Popen(
            [sys.executable, "-u", "run_pipeline.py", url],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            output_lines.append(line.rstrip())
            output_lines = output_lines[-100:]
            if line.startswith("STEP: "):
                description = line[len("STEP: ") :].strip()
                for prefix, progress in STEP_NAMES.items():
                    if description.startswith(prefix):
                        update_job(job_id, progress=progress)
                        break

        return_code = process.wait()
        output = "\n".join(output_lines)
        if return_code != 0:
            failed_step = None
            for line in output_lines:
                match = re.search(r"FAILED at step:\s*(.+)", line)
                if match:
                    description = match.group(1)
                    failed_step = next(
                        (
                            progress
                            for prefix, progress in STEP_NAMES.items()
                            if description.startswith(prefix)
                        ),
                        description,
                    )
                    break
            update_job(
                job_id,
                status="failed",
                failed_step=failed_step or jobs[job_id]["progress"],
                error=(output or f"Pipeline exited with status code {return_code}")[
                    -MAX_ERROR_LENGTH:
                ],
            )
            return

        clips, warning = collect_clips()
        if not clips:
            update_job(
                job_id,
                status="failed",
                progress="reframing",
                failed_step="reframing",
                error="The pipeline completed but did not produce any vertical MP4 clips.",
            )
            return

        job_clip_dir = JOB_RESULTS_DIR / job_id
        job_clip_dir.mkdir(parents=True, exist_ok=False)
        for clip in clips:
            shutil.copy2(CLIPS_DIR / clip["filename"], job_clip_dir / clip["filename"])
            clip["url"] = clip["url"].format(job_id=job_id)
        update_job(
            job_id,
            status="done",
            progress="done",
            clips=clips,
            warning=warning,
        )
    except Exception as error:
        logger.exception("Pipeline job %s failed unexpectedly", job_id)
        update_job(
            job_id,
            status="failed",
            failed_step=jobs[job_id].get("progress"),
            error=str(error) or error.__class__.__name__,
        )
    finally:
        with jobs_lock:
            if pipeline_state["active_job_id"] == job_id:
                pipeline_state["active_job_id"] = None


@app.post("/api/process", status_code=202)
def process_video(request: PipelineRequest) -> dict[str, str]:
    if not is_youtube_url(request.url):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid YouTube video URL (youtube.com or youtu.be).",
        )

    job_id = str(uuid.uuid4())
    with jobs_lock:
        if pipeline_state["active_job_id"] is not None:
            raise HTTPException(
                status_code=409,
                detail="A pipeline job is already running. Try again when it finishes.",
            )
        pipeline_state["active_job_id"] = job_id
        jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": "queued",
            "failed_step": None,
            "error": None,
            "warning": None,
        }

    thread = threading.Thread(
        target=run_pipeline_job,
        args=(job_id, request.url.strip()),
        name=f"pipeline-{job_id}",
        daemon=True,
    )
    try:
        thread.start()
    except RuntimeError as error:
        with jobs_lock:
            pipeline_state["active_job_id"] = None
            jobs[job_id].update(
                status="failed",
                error=f"Could not start the pipeline job: {error}",
            )
        raise HTTPException(
            status_code=500, detail="Could not start the pipeline job."
        ) from error
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def get_status(job_id: str) -> Any:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        response = {
            key: value for key, value in job.items() if key not in {"clips", "clip_dir"}
        }
    if response["status"] == "failed":
        return JSONResponse(status_code=500, content=response)
    return response


@app.get("/api/jobs/{job_id}/clips")
def list_job_clips(job_id: str) -> list[dict[str, Any]]:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        if job["status"] != "done":
            raise HTTPException(
                status_code=409, detail="Clips are available after the job completes."
            )
        return job["clips"]


@app.get("/api/jobs/{job_id}/clips/{filename}")
def get_clip(job_id: str, filename: str, download: bool = False) -> FileResponse:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        if job["status"] != "done":
            raise HTTPException(
                status_code=409, detail="Clips are available after the job completes."
            )
        allowed_names = {clip["filename"] for clip in job["clips"]}

    if filename not in allowed_names or Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="Clip not found.")

    path = JOB_RESULTS_DIR / job_id / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Clip file not found.")

    headers = {"Accept-Ranges": "bytes"}
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=filename if download else None,
        headers=headers,
    )

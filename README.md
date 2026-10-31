# Shorts Clipper

Shorts Clipper turns a public YouTube video into short, face-tracked vertical
clips. It consists of a FastAPI backend, a Python video-processing pipeline,
and a React/Vite web application.

## Features

- Download public YouTube videos with `yt-dlp`.
- Transcribe speech with Groq Whisper and select clip-worthy moments with a
  Groq language model (or use the optional rule-based selector).
- Cut selected segments and reframe them to 9:16 using MediaPipe face tracking.
- Submit and monitor processing jobs through the web app or REST API.
- Preview and download completed clips.

## Requirements

- Python 3.10 or later
- Node.js 20 or later and npm
- FFmpeg available on `PATH`
- A Groq API key
- Deno, if required by your `yt-dlp` YouTube configuration

## Configuration

Create a `.env` file in the project root and set your Groq API key:

```text
GROQ_API_KEY=your_groq_api_key
```

Do not commit `.env` or real API keys. The backend loads this file from the
project root. For a frontend hosted separately from the API, set
`VITE_API_BASE_URL` in the frontend environment to the backend's base URL; the
default local setup uses the Vite `/api` proxy.

## Install

Run commands from the `shorts-clipper` project root. On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

## Run locally

Start the backend from the project root:

```powershell
python -m uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, start the frontend:

```powershell
Set-Location frontend
npm run dev
```

Open the URL printed by Vite, normally <http://localhost:5173>. Vite proxies
`/api` requests to <http://localhost:8000>. Interactive API documentation is
available at <http://localhost:8000/docs>.

Processing can take several minutes. Only one job runs at a time because jobs
share intermediate pipeline files. Job state is held in memory and is lost
when the backend restarts.

For deployment, build the frontend with `npm run build` and serve `frontend/dist`
from a static web server. Route `/api` to the backend or configure
`VITE_API_BASE_URL`. The current backend is intended for a single process and
worker: job state is in memory and pipeline files are shared, so multiple
workers or replicas are not supported.

## Run the pipeline from the command line

```powershell
python -m backend.run_pipeline "https://www.youtube.com/watch?v=VIDEO_ID"
```

Pass `--rule-based` to select segments without the Groq language model:

```powershell
python -m backend.run_pipeline "https://www.youtube.com/watch?v=VIDEO_ID" --rule-based
```

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/process` | Submit `{"url": "https://..."}` and receive a `job_id`. |
| `GET` | `/api/status/{job_id}` | Get the job state and current pipeline step. |
| `GET` | `/api/jobs/{job_id}/clips` | List completed clips, durations, and selection reasons. |
| `GET` | `/api/jobs/{job_id}/clips/{filename}` | Stream a clip; add `?download=true` to download it. |

Completed clips are copied into `clips_output_jobs/` so results remain
available independently of the pipeline's temporary output.

## Project layout

```text
shorts-clipper/
├── backend/
│   ├── api.py                 # FastAPI endpoints and background job handling
│   ├── run_pipeline.py        # Pipeline orchestration and CLI
│   ├── requirements.txt       # Python dependencies
│   ├── models/                # MediaPipe face detection model
│   └── pipeline/              # Transcription, selection, cutting, reframing
│       └── legacy_or_optional/ # Standalone alternatives not used by the API
├── frontend/
│   ├── src/
│   │   ├── api/               # Frontend API client
│   │   ├── components/        # Form, progress, and results UI
│   │   ├── hooks/             # Job submission and progress polling
│   │   └── App.jsx            # Main page composition
│   ├── package.json
│   └── vite.config.js
├── api.py                     # Root-level compatibility import for the API
├── .env                       # Local secrets; do not commit
└── README.md
```

Generated media, job snapshots, Python environments, and frontend build and
dependency directories are runtime artifacts and should not be committed.

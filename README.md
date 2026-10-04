# Shorts Clipper

Turn a public YouTube video into short, face-tracked vertical clips. The
project includes a Python video-processing pipeline, a FastAPI job API, and a
React web interface.

## Features

- Download videos with `yt-dlp`.
- Transcribe speech and select clip-worthy moments with Groq.
- Cut candidate segments and reframe them vertically with MediaPipe face
  tracking.
- Submit a video from the web app and follow its pipeline progress.
- Preview and download clips, with the candidate's reason shown when available.

## Requirements

- Python 3.10 or later
- Node.js 20 or later and npm
- FFmpeg available on your `PATH`
- A Groq API key
- Deno, if required by your `yt-dlp` YouTube setup

## Setup

Run these commands from the project root (`shorts-clipper`):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Add your Groq API key to `.env` in the project root:

```text
GROQ_API_KEY=your_groq_api_key
```

Install the frontend dependencies:

```powershell
Set-Location frontend
npm install
Set-Location ..
```

## Run the application

Start the API from the project root in the first terminal:

```powershell
.\venv\Scripts\python.exe -m uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

Start Vite in a second terminal:

```powershell
Set-Location frontend
npm run dev
```

Open the URL printed by Vite, normally <http://localhost:5173>. The frontend's
development server proxies API requests to <http://localhost:8000>. Interactive
API documentation is available at <http://localhost:8000/docs>.

Paste a public YouTube video URL into the app and select **Generate clips**.
Processing can take a few minutes. The app displays the active pipeline step
and, when processing finishes, provides video previews and download links.

### Run the pipeline without the web app

From the project root:

```powershell
.\venv\Scripts\python.exe run_pipeline.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

Add `--rule-based` to use rule-based segment selection instead of the Groq LLM.

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/process` | Submit `{"url": "https://..."}` and receive a `job_id`. |
| `GET` | `/api/status/{job_id}` | Poll job status and the current `progress` step. |
| `GET` | `/api/jobs/{job_id}/clips` | List completed clips with filename, duration, and reason when available. |
| `GET` | `/api/jobs/{job_id}/clips/{filename}` | Stream a clip with byte-range support for playback; add `?download=true` to download it. |

Jobs are kept in memory, so they do not survive an API server restart. Only one
pipeline job can run at a time because the pipeline uses shared intermediate
files. Completed clip files are saved separately per job under
`clips_output_jobs/`.

## Project structure

```text
shorts-clipper/
├── api.py                         # FastAPI job and clip endpoints
├── run_pipeline.py                # Pipeline orchestrator
├── requirements.txt               # Python dependencies
├── src/                            # Transcription, selection, cutting, reframing
│   ├── select_segments.py         # Optional rule-based segment selection
│   └── legacy_or_optional/        # Standalone alternatives not used by the API flow
├── models/                         # Face detection model
├── frontend/src/
│   ├── api/client.js              # Shared API requests and error handling
│   ├── components/                # Form, progress, results, and feature UI
│   ├── hooks/useVideoJob.js       # Job submission and progress polling
│   ├── App.jsx                    # Page composition
│   └── style.css                  # Responsive visual system
├── clips_output/                   # Pipeline output (generated)
└── clips_output_jobs/              # Per-job API clip snapshots (generated)
```

The pipeline writes intermediate files and its latest output under the project
root. Generated media and frontend build/dependency directories are excluded
from version control.

# 🎬 Shorts Clipper

**Turn any YouTube video into ready-to-post vertical shorts — automatically.**

Shorts Clipper ingests a long-form YouTube video, transcribes it, intelligently identifies the most "clip-worthy" moments, cuts them into short vertical clips, and burns in auto-captions — all with free, open-source tools.

---

## ✨ Features

- 📥 **Download** any YouTube video via `yt-dlp`
- 🗣️ **Transcribe** with word-level timestamps using local, free `faster-whisper`
- 🎯 **Auto-detect** the best 30–90 second segments (hook + payoff, never cuts mid-sentence)
- ✂️ **Auto-cut** clips with `ffmpeg`
- 💬 **Auto-caption** clips, karaoke-style word-by-word highlighting
- 📱 **Smart vertical reframing** — keeps the speaker in frame when converting 16:9 → 9:16
- 🆓 **100% free stack** — no paid APIs required

---

## 🧱 Tech Stack

| Task | Tool |
|---|---|
| Video download | [yt-dlp](https://github.com/yt-dlp/yt-dlp) |
| Transcription | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) |
| Segment selection | Rule-based scoring / LLM (optional) |
| Video cutting & captions | [ffmpeg](https://ffmpeg.org/) |
| Face detection / reframing | [MediaPipe](https://github.com/google/mediapipe) + [OpenCV](https://opencv.org/) |
| JS runtime (for yt-dlp) | [Deno](https://deno.com/) |

---

## 🚧 Project Status

Currently in active development, built step by step as a learning project.

- [x] **Phase 1 — Download & Transcribe**: YouTube video download + word-level timestamped transcript (JSON output)
- [ ] **Phase 2 — Segment Selection**: Auto-detect clip-worthy moments
- [ ] **Phase 3 — Clip Cutting**: Auto-generate short `.mp4` clips from selected segments
- [ ] **Phase 4 — Auto-Captions**: Burn in styled, animated captions
- [ ] **Phase 5 — Smart Reframing**: Convert to vertical 9:16 with speaker tracking
- [ ] **Phase 6 — Polish & UI**: Streamlit interface, batch processing, deployment

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) installed and on your PATH
- [Deno](https://deno.com/) installed (required by `yt-dlp` for YouTube's JS challenge)

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/shorts-clipper.git
cd shorts-clipper

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install yt-dlp faster-whisper
```

### Usage

**1. Download a video:**
```bash
python -m yt_dlp -f "bestvideo[height<=720]+bestaudio" -o "test_video.mp4" "YOUTUBE_URL"
```

**2. Transcribe it:**
```bash
python transcribe.py
```

This generates `transcript.json` — a structured transcript with sentence and word-level timestamps, ready for the next stage of the pipeline (segment selection).

---

## 📂 Project Structure

```
shorts-clipper/
├── venv/                 # virtual environment (not tracked)
├── transcribe.py         # download → transcribe pipeline
├── transcript.json        # generated transcript with timestamps
├── test_video.mp4         # sample downloaded video (not tracked)
└── .gitignore
```

---

## 🗺️ Roadmap

This project is being built in public, phase by phase — see the [Project Status](#-project-status) above for what's done and what's next. Follow along as segment selection, captions, and vertical reframing get added.

---

## 📄 License

MIT — free to use, modify, and build on.

---

## 🙌 Acknowledgments

Built on top of these excellent open-source projects: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [ffmpeg](https://ffmpeg.org/), [MediaPipe](https://github.com/google/mediapipe), and [Deno](https://deno.com/).

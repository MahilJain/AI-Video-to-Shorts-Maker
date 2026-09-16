"""Shared path, environment, JSON, and ffmpeg helpers for the shorts pipeline."""

import json
import os
import subprocess
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")


def resolve_project_path(path: str) -> str:
    """Resolve relative artifacts from the project root, not the caller's cwd."""
    return path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)


def load_project_env() -> None:
    """Load the project .env beside the source tree, independent of the caller's cwd."""
    load_dotenv(ENV_PATH)


def get_groq_api_key() -> str | None:
    """Return the configured Groq key, including the project's legacy bare-key format."""
    load_project_env()
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        return api_key

    try:
        with open(ENV_PATH, encoding="utf-8") as env_file:
            lines = [
                line.strip().strip("\"'")
                for line in env_file
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except FileNotFoundError:
        return None
    return lines[0] if len(lines) == 1 and lines[0].startswith("gsk_") else None


def load_json(path: str) -> Any:
    """Load UTF-8 JSON from a project-relative or absolute path."""
    with open(resolve_project_path(path), "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: Any, path: str) -> str:
    """Save UTF-8 JSON and return its absolute output path."""
    output_path = resolve_project_path(path)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    return output_path


def run_ffmpeg(cmd: list[str], output_path: str, error_tail: int = 500) -> bool:
    """Run ffmpeg once and report a useful tail when it fails."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg failed for {output_path}:")
        print(result.stderr[-error_tail:])
        return False
    print(f"Saved: {output_path}")
    return True

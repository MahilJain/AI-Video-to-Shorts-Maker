import argparse
import json
import os

# Keep clips within the target duration range for short-form video.
MIN_CLIP_LEN = 30
MAX_CLIP_LEN = 90

HOOK_KEYWORDS = [
    "why", "how", "what", "secret", "mistake", "never", "always",
    "biggest", "worst", "best", "truth", "actually", "surprising",
    "nobody", "everyone", "stop", "important", "warning"
]

def parse_args() -> argparse.Namespace:
    """Parse the transcript filename supplied on the command line."""
    parser = argparse.ArgumentParser(description="Select clip-worthy transcript segments.")
    parser.add_argument(
        "transcript_filename",
        nargs="?",
        default="transcript.json",
        help="Transcript JSON filename or path (default: transcript.json)",
    )
    return parser.parse_args()


def score_window(segments: list[dict]) -> float:
    """Assign a higher score to windows that are likely to retain attention."""
    text = " ".join(s["text"] for s in segments).lower()
    duration = segments[-1]["end"] - segments[0]["start"]

    score = 0.0

    # Reward hook keywords
    for kw in HOOK_KEYWORDS:
        if kw in text:
            score += 2

    # Reward questions (strong hook signal)
    score += text.count("?") * 3

    # Reward numbers/stats (specific claims are engaging)
    score += sum(1 for word in text.split() if any(c.isdigit() for c in word)) * 1.5

    # Normalize content density so longer windows do not win merely by accumulating hits.
    score_per_second = score / duration if duration > 0 else 0.0

    # Keep length and sentence-boundary preferences deliberately smaller than content density.
    if MIN_CLIP_LEN <= duration <= MAX_CLIP_LEN:
        score_per_second += 0.1
    if segments[-1]["text"].rstrip().endswith((".", "!", "?")):
        score_per_second += 0.15

    return score_per_second


def find_candidate_windows(transcript: list[dict]) -> list[list[dict]]:
    """Build every valid contiguous transcript window up to MAX_CLIP_LEN."""
    candidates = []
    n = len(transcript)

    for i in range(n):
        window = [transcript[i]]
        j = i + 1
        while j < n:
            duration = transcript[j]["end"] - transcript[i]["start"]
            if duration > MAX_CLIP_LEN:
                break
            # Add complete transcript segments so clips do not end mid-sentence.
            window.append(transcript[j])
            j += 1

        duration = window[-1]["end"] - window[0]["start"]
        if duration >= MIN_CLIP_LEN:
            # Discard windows that are too short to be useful clips.
            candidates.append(window)

    return candidates

def pick_top_non_overlapping(
    scored_windows: list[tuple[float, list[dict]]], top_n: int = 5
) -> list[tuple[float, list[dict]]]:
    """Select the highest-scoring windows while avoiding duplicate footage."""
    scored_windows.sort(key=lambda x: x[0], reverse=True)
    chosen = []
    used_ranges = []

    for score, window in scored_windows:
        start, end = window[0]["start"], window[-1]["end"]
        # A candidate is usable only when it is separate from every chosen range.
        overlaps = any(not (end <= u_start or start >= u_end) for u_start, u_end in used_ranges)
        if not overlaps:
            chosen.append((score, window))
            used_ranges.append((start, end))
        # Stop once the requested number of recommendations has been collected.
        if len(chosen) >= top_n:
            break

    return chosen

def main() -> None:
    """Load a transcript, select clips, and save the ranked candidates as JSON."""
    args = parse_args()
    transcript_path = os.path.abspath(args.transcript_filename)
    with open(transcript_path, "r", encoding="utf-8") as file:
        transcript = json.load(file)

    candidates = find_candidate_windows(transcript)
    scored = [(score_window(window), window) for window in candidates]
    # Ranking happens before overlap filtering so the best available moments win.
    top_clips = pick_top_non_overlapping(scored, top_n=5)

    print(f"Found {len(top_clips)} recommended clips:\n")

    results = []
    for rank, (score, window) in enumerate(top_clips, 1):
        # Use the first and last transcript timestamps as the clip boundaries.
        start = window[0]["start"]
        end = window[-1]["end"]
        text = " ".join(s["text"] for s in window)
        print(f"#{rank} | Score: {score:.3f} | {start:.1f}s -> {end:.1f}s ({end-start:.1f}s)")
        print(f"   \"{text[:120]}...\"\n")
        results.append({"rank": rank, "score": score, "start": start, "end": end, "text": text})

    output_path = os.path.abspath("clip_candidates.json")
    print(f"Writing clip candidates to: {output_path}")
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()

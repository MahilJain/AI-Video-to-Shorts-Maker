import json

# Load the timestamped transcript produced by transcribe.py.
with open("transcript.json", "r", encoding="utf-8") as f:
    transcript = json.load(f)

# Keep clips within the target duration range for short-form video.
MIN_CLIP_LEN = 30
MAX_CLIP_LEN = 90

HOOK_KEYWORDS = [
    "why", "how", "what", "secret", "mistake", "never", "always",
    "biggest", "worst", "best", "truth", "actually", "surprising",
    "nobody", "everyone", "stop", "important", "warning"
]

def score_window(segments):
    """Assign a higher score to windows that are likely to retain attention."""
    text = " ".join(s["text"] for s in segments).lower()
    duration = segments[-1]["end"] - segments[0]["start"]

    score = 0

    # Reward ideal clip length (peak around 45-60s)
    if MIN_CLIP_LEN <= duration <= MAX_CLIP_LEN:
        score += 10
    else:
        score -= 5

    # Reward hook keywords
    for kw in HOOK_KEYWORDS:
        if kw in text:
            score += 2

    # Reward questions (strong hook signal)
    score += text.count("?") * 3

    # Reward numbers/stats (specific claims are engaging)
    score += sum(1 for word in text.split() if any(c.isdigit() for c in word)) * 1.5

    return score

def find_candidate_windows(transcript):
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

def pick_top_non_overlapping(scored_windows, top_n=5):
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

candidates = find_candidate_windows(transcript)
scored = [(score_window(w), w) for w in candidates]
# Ranking happens before overlap filtering so the best available moments win.
top_clips = pick_top_non_overlapping(scored, top_n=5)

print(f"Found {len(top_clips)} recommended clips:\n")

results = []
for rank, (score, window) in enumerate(top_clips, 1):
    # Use the first and last transcript timestamps as the clip boundaries.
    start = window[0]["start"]
    end = window[-1]["end"]
    text = " ".join(s["text"] for s in window)
    print(f"#{rank} | Score: {score:.1f} | {start:.1f}s -> {end:.1f}s ({end-start:.1f}s)")
    print(f"   \"{text[:120]}...\"\n")
    results.append({"rank": rank, "score": score, "start": start, "end": end, "text": text})

with open("clip_candidates.json", "w", encoding="utf-8") as f:
    # Keep the JSON output easy to inspect and reuse in the next pipeline stage.
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Saved to clip_candidates.json")

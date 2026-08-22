import json

with open("transcript.json", "r", encoding="utf-8") as f:
    transcript = json.load(f)

MIN_CLIP_LEN = 30
MAX_CLIP_LEN = 90

HOOK_KEYWORDS = [
    "why", "how", "what", "secret", "mistake", "never", "always",
    "biggest", "worst", "best", "truth", "actually", "surprising",
    "nobody", "everyone", "stop", "important", "warning"
]

def score_window(segments):
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
    candidates = []
    n = len(transcript)

    for i in range(n):
        window = [transcript[i]]
        j = i + 1
        while j < n:
            duration = transcript[j]["end"] - transcript[i]["start"]
            if duration > MAX_CLIP_LEN:
                break
            window.append(transcript[j])
            j += 1

        duration = window[-1]["end"] - window[0]["start"]
        if duration >= MIN_CLIP_LEN:
            candidates.append(window)

    return candidates

def pick_top_non_overlapping(scored_windows, top_n=5):
    scored_windows.sort(key=lambda x: x[0], reverse=True)
    chosen = []
    used_ranges = []

    for score, window in scored_windows:
        start, end = window[0]["start"], window[-1]["end"]
        overlaps = any(not (end <= u_start or start >= u_end) for u_start, u_end in used_ranges)
        if not overlaps:
            chosen.append((score, window))
            used_ranges.append((start, end))
        if len(chosen) >= top_n:
            break

    return chosen

candidates = find_candidate_windows(transcript)
scored = [(score_window(w), w) for w in candidates]
top_clips = pick_top_non_overlapping(scored, top_n=5)

print(f"Found {len(top_clips)} recommended clips:\n")

results = []
for rank, (score, window) in enumerate(top_clips, 1):
    start = window[0]["start"]
    end = window[-1]["end"]
    text = " ".join(s["text"] for s in window)
    print(f"#{rank} | Score: {score:.1f} | {start:.1f}s -> {end:.1f}s ({end-start:.1f}s)")
    print(f"   \"{text[:120]}...\"\n")
    results.append({"rank": rank, "score": score, "start": start, "end": end, "text": text})

with open("clip_candidates.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Saved to clip_candidates.json")

import json
import os
import sys
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

MODEL = "openai/gpt-oss-20b"


def load_transcript(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt(transcript: list[dict]) -> str:
    lines = []
    for seg in transcript:
        lines.append(f"[{seg['start']:.1f}s -> {seg['end']:.1f}s] {seg['text']}")
    transcript_text = "\n".join(lines)

    prompt = f"""You are an expert short-form video editor. Below is a timestamped transcript.

Identify 3-5 self-contained segments, each 30-60 seconds long, that would make compelling
standalone short-form clips (like YouTube Shorts or Instagram Reels). Each clip must:
- Have a clear hook at the start
- Be understandable without any other context
- Never start or end mid-sentence
- Contain a complete thought, story, or payoff

Return ONLY valid JSON, no other text, in this exact format:
[
  {{"start": 123.4, "end": 178.9, "reason": "short explanation of why this works as a clip"}}
]

Transcript:
{transcript_text}
"""
    return prompt


def call_groq(prompt: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set.")

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
        reasoning_effort="low",
    )
    return response.choices[0].message.content


def main():
    transcript_path = sys.argv[1] if len(sys.argv) > 1 else "transcript.json"
    transcript = load_transcript(transcript_path)

    print(f"Sending transcript ({len(transcript)} segments) to Groq ({MODEL})...")
    prompt = build_prompt(transcript)
    raw_response = call_groq(prompt)

    print(f"DEBUG raw response length: {len(raw_response)}")
    print(f"DEBUG raw response repr: {raw_response!r}")
    start_idx = raw_response.find("[")
    end_idx = raw_response.rfind("]") + 1
    json_str = raw_response[start_idx:end_idx]

    try:
        clips = json.loads(json_str)
    except json.JSONDecodeError:
        print("Could not parse model response as JSON. Raw output:\n")
        print(raw_response)
        return

    print(f"\nFound {len(clips)} LLM-recommended clips:\n")
    for i, clip in enumerate(clips, 1):
        duration = clip["end"] - clip["start"]
        print(f"#{i} | {clip['start']:.1f}s -> {clip['end']:.1f}s ({duration:.1f}s)")
        print(f"   Reason: {clip['reason']}\n")

    with open("clip_candidates_llm.json", "w", encoding="utf-8") as f:
        json.dump(clips, f, indent=2, ensure_ascii=False)
    print("Saved to clip_candidates_llm.json")


if __name__ == "__main__":
    main()

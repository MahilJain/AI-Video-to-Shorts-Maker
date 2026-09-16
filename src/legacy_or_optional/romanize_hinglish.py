"""Optional Groq-powered conversion of Hindi transcript text to Roman Hinglish."""

import os
import sys
from groq import Groq
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import get_groq_api_key, load_json, save_json

MODEL = "openai/gpt-oss-20b"


def romanize_batch(client: Groq, texts: list[str]) -> list[str]:
    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    prompt = f"""Convert the following Hindi/Hinglish sentences into natural, casual Hinglish
written in Roman (English) script — the way young Indians actually text and caption videos.
Keep any existing English words as-is. Do not translate to English, only romanize the Hindi parts.
Keep the same numbering. Return ONLY the numbered list, nothing else.

{numbered}
"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    result = response.choices[0].message.content.strip()

    lines = result.split("\n")
    romanized = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # strip leading "1. " style numbering
        parts = line.split(".", 1)
        if len(parts) == 2 and parts[0].strip().isdigit():
            romanized.append(parts[1].strip())
        else:
            romanized.append(line)
    return romanized


def main():
    transcript_path = sys.argv[1] if len(sys.argv) > 1 else "transcript.json"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "transcript_hinglish.json"

    transcript = load_json(transcript_path)
    api_key = get_groq_api_key()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set (check your .env file).")
    client = Groq(api_key=api_key)

    batch_size = 20
    print(f"Romanizing {len(transcript)} segments in batches of {batch_size}...\n")

    for i in range(0, len(transcript), batch_size):
        batch = transcript[i:i + batch_size]
        texts = [seg["text"] for seg in batch]

        try:
            romanized_texts = romanize_batch(client, texts)
            if len(romanized_texts) != len(texts):
                print(f"  Warning: batch {i}-{i+len(texts)} count mismatch, keeping original text.")
                continue
            for seg, new_text in zip(batch, romanized_texts):
                seg["text"] = new_text
        except Exception as e:
            print(f"  Error on batch {i}: {e}. Keeping original text for this batch.")

        print(f"  Processed segments {i+1}-{min(i+batch_size, len(transcript))}")

    saved_path = save_json(transcript, output_path)
    print(f"\nSaved Hinglish transcript to {saved_path}")


if __name__ == "__main__":
    main()

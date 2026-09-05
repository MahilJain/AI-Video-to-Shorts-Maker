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

    transcript = load_transcript(transcript_path)
    api_key = os.environ.get("GROQ_API_KEY")
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

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, ensure_ascii=False)

    print(f"\nSaved Hinglish transcript to {os.path.abspath(output_path)}")


if __name__ == "__main__":
    main()

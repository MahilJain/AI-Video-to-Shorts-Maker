"""Use Groq's LLM to select compelling, self-contained transcript segments."""

import json
import re
import sys
import time
from collections import deque

from groq import Groq

from .utils import GROQ_API_KEY, load_json, resolve_project_path, save_json

MODEL = "openai/gpt-oss-20b"
MAX_CHUNK_TOKENS = 2500
TPM_BUDGET = 7500
PROMPT_TOKEN_RESERVE = 300
OUTPUT_TOKEN_RESERVE = 256
RETRY_OUTPUT_TOKEN_RESERVE = 1024
TPM_WINDOW_SECONDS = 60


def configure_console_output() -> None:
    """Prevent model-generated Unicode from crashing on legacy Windows consoles."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")


def estimate_text_tokens(text: str) -> int:
    """Conservatively estimate tokens without depending on a model tokenizer."""
    if any(ord(character) > 127 for character in text):
        return (len(text) * 3 + 1) // 2
    return max(len(text.split()) * 2, (len(text) + 2) // 3)


def estimate_segment_tokens(segment: dict) -> int:
    return estimate_text_tokens(str(segment.get("text", ""))) + 12


def split_long_segment(segment: dict) -> list[dict]:
    """Split an unusually long transcript segment on word boundaries."""
    text = str(segment.get("text", "")).strip()
    words = text.split()
    if not words:
        return [segment]

    pieces = []
    current_words = []
    for word in words:
        candidate = " ".join([*current_words, word])
        if current_words and estimate_text_tokens(candidate) + 12 > MAX_CHUNK_TOKENS:
            pieces.append(" ".join(current_words))
            current_words = [word]
        else:
            current_words.append(word)
    if current_words:
        pieces.append(" ".join(current_words))

    start = float(segment["start"])
    end = float(segment["end"])
    total_characters = max(1, sum(len(piece) for piece in pieces))
    elapsed_characters = 0
    split_segments = []
    for index, piece in enumerate(pieces):
        piece_start = start + (end - start) * elapsed_characters / total_characters
        elapsed_characters += len(piece)
        piece_end = (
            end
            if index == len(pieces) - 1
            else start + (end - start) * elapsed_characters / total_characters
        )
        split_segments.append({"start": piece_start, "end": piece_end, "text": piece})
    return split_segments


def chunk_transcript(transcript: list[dict]) -> list[list[dict]]:
    chunks = []
    current_chunk = []
    current_tokens = 0

    for original_segment in transcript:
        for segment in split_long_segment(original_segment):
            segment_tokens = estimate_segment_tokens(segment)
            if current_chunk and current_tokens + segment_tokens > MAX_CHUNK_TOKENS:
                chunks.append(current_chunk)
                current_chunk = []
                current_tokens = 0
            current_chunk.append(segment)
            current_tokens += segment_tokens

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def build_prompt(transcript: list[dict], single_clip: bool = False) -> str:
    lines = [
        f"[{seg['start']:.1f}s -> {seg['end']:.1f}s] {seg['text']}"
        for seg in transcript
    ]
    transcript_text = "\n".join(lines)
    selection_instruction = (
        "Identify the single strongest self-contained segment, 30-60 seconds long, "
        "that would make a compelling standalone short-form clip."
        if single_clip
        else "Identify 3-5 self-contained segments, each 30-60 seconds long, that "
        "would make compelling standalone short-form clips."
    )
    output_example = (
        '[{"start": 123.4, "end": 178.9, "reason": "short explanation"}]'
        if single_clip
        else '[\n  {"start": 123.4, "end": 178.9, "reason": "short explanation"}\n]'
    )
    return f"""You are an expert short-form video editor. Below is a timestamped transcript.

{selection_instruction} Each clip must:
- Have a clear hook at the start
- Be understandable without any other context
- Never start or end mid-sentence
- Contain a complete thought, story, or payoff

Return ONLY valid JSON, no other text, in this exact format:
{output_example}

Transcript:
{transcript_text}
"""


class TokenBudget:
    def __init__(self) -> None:
        self.requests: deque[tuple[float, int]] = deque()

    def wait_for_capacity(
        self, estimated_tokens: int, output_tokens: int = OUTPUT_TOKEN_RESERVE
    ) -> None:
        request_tokens = estimated_tokens + PROMPT_TOKEN_RESERVE + output_tokens
        if request_tokens > TPM_BUDGET:
            raise ValueError(
                f"Estimated request size ({request_tokens} tokens) exceeds the "
                f"configured Groq budget ({TPM_BUDGET} tokens per minute)."
            )

        while True:
            now = time.monotonic()
            while self.requests and now - self.requests[0][0] >= TPM_WINDOW_SECONDS:
                self.requests.popleft()

            used_tokens = sum(tokens for _, tokens in self.requests)
            if used_tokens + request_tokens <= TPM_BUDGET:
                self.requests.append((now, request_tokens))
                return

            wait_seconds = TPM_WINDOW_SECONDS - (now - self.requests[0][0]) + 0.1
            print(
                f"Waiting {wait_seconds:.0f}s to stay within Groq's "
                "token-per-minute limit..."
            )
            time.sleep(wait_seconds)


def parse_clips(raw_response: str, chunk: list[dict]) -> list[dict]:
    decoder = json.JSONDecoder()
    clips = None
    for index, character in enumerate(raw_response):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(raw_response[index:])
        except json.JSONDecodeError:
            continue

        if isinstance(value, list):
            clips = value
            break
        if isinstance(value, dict):
            wrapped_clips = next(
                (
                    value[key]
                    for key in ("clips", "candidates", "results")
                    if isinstance(value.get(key), list)
                ),
                None,
            )
            if wrapped_clips is not None:
                clips = wrapped_clips
                break
            if "start" in value and "end" in value:
                clips = [value]
                break

    if clips is None:
        raise RuntimeError("Groq returned a response without a JSON clip list.")

    chunk_start = float(chunk[0]["start"])
    chunk_end = float(chunk[-1]["end"])
    validated = []
    for clip in clips:
        if not isinstance(clip, dict):
            continue
        start = clip.get("start")
        end = clip.get("end")
        if (
            not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or not chunk_start <= start < end <= chunk_end
        ):
            continue
        validated.append(
            {
                "start": float(start),
                "end": float(end),
                "reason": str(clip.get("reason", "")).strip(),
            }
        )
    return validated


def call_groq(
    client: Groq,
    prompt: str,
    token_budget: TokenBudget,
    estimated_tokens: int,
    output_token_limits: tuple[int, ...] = (
        OUTPUT_TOKEN_RESERVE,
        RETRY_OUTPUT_TOKEN_RESERVE,
    ),
) -> str:
    for output_tokens in output_token_limits:
        for attempt in range(3):
            token_budget.wait_for_capacity(estimated_tokens, output_tokens)
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=output_tokens,
                    reasoning_effort="low",
                )
            except Exception as error:
                if getattr(error, "status_code", None) != 429 or attempt == 2:
                    raise
                headers = getattr(getattr(error, "response", None), "headers", {})
                wait_value = headers.get("retry-after") or headers.get(
                    "x-ratelimit-reset-tokens"
                )
                match = re.fullmatch(
                    r"\s*(\d+(?:\.\d+)?)\s*s?\s*", str(wait_value or "")
                )
                wait_seconds = float(match.group(1)) if match else TPM_WINDOW_SECONDS
                print(
                    f"Groq rate limit reached; retrying in {wait_seconds:.0f}s "
                    f"(attempt {attempt + 2}/3)..."
                )
                time.sleep(wait_seconds)
                continue

            choices = response.choices
            message = choices[0].message if choices else None
            content = message.content if message else None
            if isinstance(content, str) and content.strip():
                finish_reason = choices[0].finish_reason if choices else None
                if finish_reason == "length":
                    if output_tokens == output_token_limits[-1]:
                        raise RuntimeError(
                            "Groq's clip-selection response was truncated after "
                            f"{output_tokens} output tokens."
                        )
                    print(
                        "Groq's clip-selection response was truncated; retrying "
                        f"with {RETRY_OUTPUT_TOKEN_RESERVE} output tokens."
                    )
                    break
                return content

            finish_reason = choices[0].finish_reason if choices else "no choices"
            if output_tokens == OUTPUT_TOKEN_RESERVE:
                print(
                    "Groq returned no clip-selection text; retrying with "
                    f"{RETRY_OUTPUT_TOKEN_RESERVE} output tokens "
                    f"(finish reason: {finish_reason})."
                )
            else:
                raise RuntimeError(
                    "Groq returned an empty clip-selection response after "
                    f"{output_tokens} output tokens (finish reason: {finish_reason})."
                )
            break

    raise RuntimeError("Groq could not return a clip-selection response.")


def select_chunk(
    client: Groq,
    prompt: str,
    token_budget: TokenBudget,
    estimated_tokens: int,
    chunk: list[dict],
) -> list[dict]:
    raw_response = call_groq(client, prompt, token_budget, estimated_tokens)
    try:
        return parse_clips(raw_response, chunk)
    except RuntimeError:
        print("Groq returned an invalid clip format; retrying with a stricter JSON prompt.")

    retry_prompt = (
        f"{prompt}\n\nYour previous response was not a valid JSON clip list. "
        "Return only a JSON array of clip objects with numeric start and end "
        "timestamps and a reason. Do not include markdown or commentary."
    )
    raw_response = call_groq(
        client,
        retry_prompt,
        token_budget,
        estimated_tokens,
        output_token_limits=(RETRY_OUTPUT_TOKEN_RESERVE,),
    )
    try:
        return parse_clips(raw_response, chunk)
    except RuntimeError as error:
        raise RuntimeError(
            "Groq returned an invalid clip-selection response after one retry."
        ) from error


def main() -> None:
    configure_console_output()
    transcript_path = resolve_project_path(
        sys.argv[1] if len(sys.argv) > 1 else "transcript.json"
    )
    transcript = load_json(transcript_path)
    chunks = chunk_transcript(transcript)
    if not chunks:
        raise RuntimeError("The transcript is empty; there is nothing to select.")

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY environment variable not set.")

    client = Groq(api_key=GROQ_API_KEY)
    token_budget = TokenBudget()
    clips = []

    print(
        f"Selecting clips from {len(transcript)} transcript segments in "
        f"{len(chunks)} Groq-sized chunk(s) ({MODEL})..."
    )
    for index, chunk in enumerate(chunks, start=1):
        estimated_tokens = sum(estimate_segment_tokens(segment) for segment in chunk)
        prompt = build_prompt(chunk, single_clip=len(chunks) > 1)
        print(
            f"Analyzing chunk {index}/{len(chunks)} "
            f"({estimated_tokens} estimated transcript tokens)..."
        )
        chunk_clips = select_chunk(
            client,
            prompt,
            token_budget,
            estimated_tokens,
            chunk,
        )
        if not chunk_clips:
            print(f"No valid clip candidates returned for chunk {index}.")
        clips.extend(chunk_clips)

    if not clips:
        raise RuntimeError("Groq did not return any valid clip candidates.")

    print(f"\nFound {len(clips)} LLM-recommended clips:\n")
    for i, clip in enumerate(clips, 1):
        duration = clip["end"] - clip["start"]
        print(f"#{i} | {clip['start']:.1f}s -> {clip['end']:.1f}s ({duration:.1f}s)")
        print(f"   Reason: {clip['reason']}\n")

    output_path = save_json(clips, "clip_candidates_llm.json")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()

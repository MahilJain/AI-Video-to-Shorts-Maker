import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from backend.pipeline.select_segments_groq import (
    OUTPUT_TOKEN_RESERVE,
    RETRY_OUTPUT_TOKEN_RESERVE,
    TokenBudget,
    call_groq,
    configure_console_output,
    parse_clips,
    select_chunk,
)


def response(content: str | None, finish_reason: str = "stop") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ]
    )


class CallGroqTests(unittest.TestCase):
    def test_console_output_escapes_unrepresentable_unicode(self) -> None:
        output = io.BytesIO()
        console = io.TextIOWrapper(output, encoding="cp1252")

        with patch("sys.stdout", console):
            configure_console_output()
            print("non-breaking hyphen: \u2011")
            console.flush()

        self.assertEqual(
            output.getvalue(),
            b"non-breaking hyphen: \\u2011\r\n",
        )

    def test_retries_empty_response_with_larger_output_limit(self) -> None:
        client = Mock()
        client.chat.completions.create.side_effect = [
            response(None, "length"),
            response('[{"start": 10, "end": 40}]'),
        ]
        budget = TokenBudget()

        with patch.object(budget, "wait_for_capacity") as wait_for_capacity:
            result = call_groq(client, "prompt", budget, estimated_tokens=500)

        self.assertEqual(result, '[{"start": 10, "end": 40}]')
        self.assertEqual(
            [
                request.kwargs["max_tokens"]
                for request in client.chat.completions.create.call_args_list
            ],
            [OUTPUT_TOKEN_RESERVE, RETRY_OUTPUT_TOKEN_RESERVE],
        )
        self.assertEqual(
            wait_for_capacity.call_args_list,
            [
                call(500, OUTPUT_TOKEN_RESERVE),
                call(500, RETRY_OUTPUT_TOKEN_RESERVE),
            ],
        )

    def test_reports_finish_reason_when_larger_response_is_also_empty(self) -> None:
        client = Mock()
        client.chat.completions.create.side_effect = [
            response(None, "length"),
            response(None, "length"),
        ]
        budget = TokenBudget()

        with (
            patch.object(budget, "wait_for_capacity"),
            self.assertRaisesRegex(
                RuntimeError,
                r"empty clip-selection response after 1024 output tokens "
                r"\(finish reason: length\)",
            ),
        ):
            call_groq(client, "prompt", budget, estimated_tokens=500)

    def test_retries_truncated_nonempty_response_with_larger_output_limit(self) -> None:
        client = Mock()
        client.chat.completions.create.side_effect = [
            response('[{"start": 10', "length"),
            response('[{"start": 10, "end": 40}]'),
        ]
        budget = TokenBudget()

        with patch.object(budget, "wait_for_capacity") as wait_for_capacity:
            result = call_groq(client, "prompt", budget, estimated_tokens=500)

        self.assertEqual(result, '[{"start": 10, "end": 40}]')
        self.assertEqual(
            wait_for_capacity.call_args_list,
            [
                call(500, OUTPUT_TOKEN_RESERVE),
                call(500, RETRY_OUTPUT_TOKEN_RESERVE),
            ],
        )


class ParseClipsTests(unittest.TestCase):
    def test_parses_clip_list_with_markdown_fence_and_surrounding_text(self) -> None:
        clips = parse_clips(
            'Here are the clips:\n```json\n[{"start": 10, "end": 40}]\n```',
            [{"start": 0, "end": 60}],
        )

        self.assertEqual(clips, [{"start": 10.0, "end": 40.0, "reason": ""}])

    def test_parses_wrapped_or_single_clip_object(self) -> None:
        chunk = [{"start": 0, "end": 60}]

        self.assertEqual(
            parse_clips(
                '{"clips": [{"start": 10, "end": 40, "reason": "complete thought"}]}',
                chunk,
            ),
            [{"start": 10.0, "end": 40.0, "reason": "complete thought"}],
        )
        self.assertEqual(
            parse_clips('{"start": 10, "end": 40}', chunk),
            [{"start": 10.0, "end": 40.0, "reason": ""}],
        )


class SelectChunkTests(unittest.TestCase):
    def test_retries_unparseable_response_with_strict_json_prompt(self) -> None:
        chunk = [{"start": 0, "end": 60}]
        with patch(
            "backend.pipeline.select_segments_groq.call_groq",
            side_effect=[
                "I could not produce the requested format.",
                '[{"start": 10, "end": 40}]',
            ],
        ) as call_groq_mock:
            clips = select_chunk(
                Mock(),
                "Original prompt",
                TokenBudget(),
                estimated_tokens=100,
                chunk=chunk,
            )

        self.assertEqual(clips, [{"start": 10.0, "end": 40.0, "reason": ""}])
        self.assertIn("Return only a JSON array", call_groq_mock.call_args.args[1])
        self.assertEqual(
            call_groq_mock.call_args.kwargs["output_token_limits"],
            (RETRY_OUTPUT_TOKEN_RESERVE,),
        )


if __name__ == "__main__":
    unittest.main()

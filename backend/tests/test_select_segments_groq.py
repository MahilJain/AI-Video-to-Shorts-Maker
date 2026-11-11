import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from backend.pipeline.select_segments_groq import (
    OUTPUT_TOKEN_RESERVE,
    RETRY_OUTPUT_TOKEN_RESERVE,
    TokenBudget,
    call_groq,
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


if __name__ == "__main__":
    unittest.main()

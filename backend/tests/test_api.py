import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.api import PipelineRequest, process_video


class ProcessVideoTests(unittest.TestCase):
    def test_requires_groq_key_before_creating_a_job(self) -> None:
        with patch("backend.api.GROQ_API_KEY", None):
            with self.assertRaises(HTTPException) as raised:
                process_video(PipelineRequest(url="https://youtu.be/example"))

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("GROQ_API_KEY", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()

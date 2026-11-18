import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from backend.run_pipeline import build_download_command, main, run_download_step


class DownloadCommandTests(unittest.TestCase):
    def test_builds_download_command_without_browser_cookies_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            command = build_download_command("input.mp4", "https://youtu.be/example")

        self.assertIn("-m", command)
        self.assertIn("yt_dlp", command)
        format_index = command.index("-f") + 1
        self.assertEqual(
            command[format_index],
            "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        )
        self.assertIn("--remux-video", command)
        self.assertIn("mp4", command)
        self.assertIn("--retries", command)
        self.assertIn("--fragment-retries", command)
        self.assertNotIn("--cookies-from-browser", command)
        self.assertEqual(command[-1], "https://youtu.be/example")

    def test_adds_configured_browser_cookies(self) -> None:
        with patch.dict(os.environ, {"YTDLP_COOKIES_FROM_BROWSER": "chrome"}):
            command = build_download_command("input.mp4", "https://youtu.be/example")

        option_index = command.index("--cookies-from-browser")
        self.assertEqual(command[option_index + 1], "chrome")
        self.assertEqual(command[-1], "https://youtu.be/example")

    def test_ignores_empty_browser_cookie_setting(self) -> None:
        with patch.dict(os.environ, {"YTDLP_COOKIES_FROM_BROWSER": "  "}):
            command = build_download_command("input.mp4", "https://youtu.be/example")

        self.assertNotIn("--cookies-from-browser", command)

    def test_prefers_cookies_file_when_both_cookie_options_are_set(self) -> None:
        with tempfile.NamedTemporaryFile() as cookie_file:
            with patch.dict(
                os.environ,
                {
                    "YTDLP_COOKIES_FILE": cookie_file.name,
                    "YTDLP_COOKIES_FROM_BROWSER": "chrome",
                },
            ):
                command = build_download_command(
                    "input.mp4", "https://youtu.be/example"
                )

        self.assertIn("--cookies", command)
        self.assertNotIn("--cookies-from-browser", command)

    def test_rejects_missing_cookies_file(self) -> None:
        with patch.dict(
            os.environ,
            {"YTDLP_COOKIES_FILE": "missing-ytdlp-cookies.txt"},
        ):
            with self.assertRaisesRegex(FileNotFoundError, "YTDLP_COOKIES_FILE"):
                build_download_command("input.mp4", "https://youtu.be/example")

    def test_retries_without_browser_cookies_if_cookie_database_cannot_be_copied(
        self,
    ) -> None:
        failed_attempt = Mock(
            stdout=io.StringIO("ERROR: Could not copy Chrome cookie database.\n"),
            wait=Mock(return_value=1),
        )
        successful_attempt = Mock(
            stdout=io.StringIO("Downloaded video\n"),
            wait=Mock(return_value=0),
        )
        command = [
            "python",
            "-m",
            "yt_dlp",
            "--cookies-from-browser",
            "chrome",
            "https://youtu.be/example",
        ]

        with (
            patch(
                "backend.run_pipeline.subprocess.Popen",
                side_effect=[failed_attempt, successful_attempt],
            ) as popen,
            redirect_stdout(io.StringIO()),
        ):
            run_download_step(command)

        retried_command = popen.call_args_list[1].args[0]
        self.assertNotIn("--cookies-from-browser", retried_command)
        self.assertEqual(retried_command[-1], "https://youtu.be/example")

    def test_missing_groq_key_fails_before_cleaning_previous_outputs(self) -> None:
        with (
            patch("sys.argv", ["run_pipeline.py", "https://youtu.be/example"]),
            patch("backend.run_pipeline.load_project_env"),
            patch("backend.run_pipeline.GROQ_API_KEY", None),
            patch("backend.run_pipeline.clean_previous_run") as clean_previous_run,
            self.assertRaisesRegex(RuntimeError, "GROQ_API_KEY"),
        ):
            main()

        clean_previous_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()

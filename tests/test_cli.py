from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock

from godot_playwright.cli import main as cli_main


class CliConnectionTests(unittest.TestCase):
    def test_health_accepts_port_after_subcommand(self) -> None:
        client = mock.Mock()
        client.health.return_value = {"ok": True}
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.GodotClient", return_value=client) as client_type:
            with redirect_stdout(stdout):
                code = cli_main(["health", "--port", "12345"])

        self.assertEqual(code, 0)
        client_type.assert_called_once_with("127.0.0.1", 12345)
        self.assertIn('"ok": true', stdout.getvalue())

    def test_launch_defaults_to_auto_port_and_prints_selected_port(self) -> None:
        godot = mock.Mock()
        godot.host = "127.0.0.1"
        godot.port = 23456
        godot.process = mock.Mock()
        godot.process.poll.return_value = 0
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.Godot", return_value=godot) as godot_type:
            with redirect_stdout(stdout):
                code = cli_main(["launch", "/tmp/project"])

        self.assertEqual(code, 0)
        self.assertIsNone(godot_type.call_args.kwargs["port"])
        self.assertIn("http://127.0.0.1:23456", stdout.getvalue())
        godot.close.assert_called_once()

    def test_launch_accepts_explicit_port_after_subcommand(self) -> None:
        godot = mock.Mock()
        godot.host = "127.0.0.1"
        godot.port = 34567
        godot.process = mock.Mock()
        godot.process.poll.return_value = 0
        with mock.patch("godot_playwright.cli.Godot", return_value=godot) as godot_type:
            with redirect_stdout(StringIO()):
                code = cli_main(["launch", "/tmp/project", "--port", "34567"])

        self.assertEqual(code, 0)
        self.assertEqual(godot_type.call_args.kwargs["port"], 34567)


if __name__ == "__main__":
    unittest.main()

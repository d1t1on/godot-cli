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

    def test_design_ui_forwards_generation_options(self) -> None:
        stdout = StringIO()
        report = {
            "ok": True,
            "target_scene": "res://scenes/ui/menu.tscn",
            "node_count": 3,
            "report_html": "/tmp/report.html",
            "issues": [],
        }
        with mock.patch("godot_playwright.cli.generate_design_ui", return_value=report) as design_ui:
            with redirect_stdout(stdout):
                code = cli_main(
                    [
                        "design-ui",
                        "/tmp/project",
                        "/tmp/spec.json",
                        "--scene",
                        "res://scenes/ui/menu.tscn",
                        "--viewport",
                        "900x600",
                        "--viewport",
                        "800x450",
                        "--dry-run",
                        "--no-screenshots",
                        "--force",
                    ]
                )

        self.assertEqual(code, 0)
        self.assertIn("Design UI PASS", stdout.getvalue())
        design_ui.assert_called_once()
        self.assertEqual(design_ui.call_args.args[:2], ("/tmp/project", "/tmp/spec.json"))
        self.assertEqual(design_ui.call_args.kwargs["scene"], "res://scenes/ui/menu.tscn")
        self.assertEqual(design_ui.call_args.kwargs["viewports"], [(900, 600), (800, 450)])
        self.assertTrue(design_ui.call_args.kwargs["dry_run"])
        self.assertTrue(design_ui.call_args.kwargs["no_screenshots"])
        self.assertTrue(design_ui.call_args.kwargs["force"])

    def test_module_list_prints_available_modules(self) -> None:
        stdout = StringIO()
        modules = [
            {
                "name": "save_load",
                "version": "0.1.0",
                "display_name": "Save Load",
                "description": "JSON save/load service for Godot projects.",
                "godot_version": ">=4.6",
            }
        ]
        with mock.patch("godot_playwright.cli.list_modules", return_value=modules) as list_call:
            with redirect_stdout(stdout):
                code = cli_main(["module", "list"])

        self.assertEqual(code, 0)
        list_call.assert_called_once_with()
        self.assertIn("save_load 0.1.0 - JSON save/load service for Godot projects.", stdout.getvalue())

    def test_module_add_forwards_install_options(self) -> None:
        stdout = StringIO()
        report = {
            "ok": True,
            "module": "save_load",
            "version": "0.1.0",
            "project": "/tmp/project",
            "demo": True,
            "copied": [
                {"target": "res://addons/save_load/save_service.gd"},
                {"target": "res://scenes/save_load_demo/save_load_demo.tscn"},
            ],
            "autoloads": [{"name": "SaveService", "path": "res://addons/save_load/save_service.gd"}],
            "warnings": [],
            "errors": [],
        }
        with mock.patch("godot_playwright.cli.add_module", return_value=report) as add_call:
            with redirect_stdout(stdout):
                code = cli_main(["module", "add", "/tmp/project", "save_load", "--demo", "--force"])

        self.assertEqual(code, 0)
        add_call.assert_called_once_with("/tmp/project", "save_load", demo=True, force=True)
        output = stdout.getvalue()
        self.assertIn("PASS module save_load 0.1.0", output)
        self.assertIn("demo: installed", output)
        self.assertIn("autoload SaveService", output)


if __name__ == "__main__":
    unittest.main()

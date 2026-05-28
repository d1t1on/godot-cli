from __future__ import annotations

import shutil
import subprocess
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from godot_playwright.cli import main as cli_main
from godot_playwright.export import ExportError, export_project
from godot_playwright.project import init_project


class ExportUnitTests(unittest.TestCase):
    def test_export_project_runs_godot_and_reports_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (project / "export_presets.cfg").write_text(
                textwrap.dedent(
                    """\
                    [preset.0]
                    name="Linux"
                    platform="Linux"
                    runnable=false
                    export_filter="all_resources"
                    export_path="build/game.pck"
                    """
                ),
                encoding="utf-8",
            )

            def fake_run(cmd, **kwargs):
                output = Path(cmd[-1])
                output.write_bytes(b"pck")
                return subprocess.CompletedProcess(cmd, 0, stdout="exported\n")

            with mock.patch("godot_playwright.export.subprocess.run", side_effect=fake_run) as run:
                report = export_project(project, "Linux", "build/game.pck", mode="pack", executable="godot-test")

            self.assertTrue(report["ok"])
            self.assertEqual(report["exit_code"], 0)
            self.assertEqual(report["output_bytes"], 3)
            self.assertTrue(report["preset_found"])
            self.assertEqual(report["preset_state"]["platform"], "Linux")
            self.assertEqual(report["preset_export_path"], "build/game.pck")
            self.assertEqual(report["output_relative_path"], "build/game.pck")
            self.assertTrue(report["output_matches_preset"])
            self.assertTrue(report["preset_output_state"]["exists"])
            self.assertEqual(report["preset_output_state"]["bytes"], 3)
            self.assertEqual(run.call_args.kwargs["env"]["GODOT_PLAYWRIGHT_PORT"], "0")
            self.assertEqual(report["export_presets"]["count"], 1)
            self.assertFalse(report["output_preexisting"])
            self.assertTrue(report["output_changed"])
            self.assertIsNone(report["output_mtime_before_ns"])
            self.assertIsInstance(report["output_mtime_after_ns"], int)
            self.assertEqual(report["diagnostic_count"], 0)
            self.assertEqual(report["log_summary"]["error_count"], 0)
            self.assertTrue(Path(report["log_path"]).exists())
            self.assertIn("--export-pack", report["command"])
            self.assertIn("Linux", report["command"])
            self.assertEqual(run.call_args.kwargs["cwd"], project.resolve())

    def test_export_project_reports_preset_output_mismatch_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (project / "export_presets.cfg").write_text(
                textwrap.dedent(
                    """\
                    [preset.0]
                    name="Linux"
                    platform="Linux"
                    export_path="configured/game.pck"
                    """
                ),
                encoding="utf-8",
            )

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(
                    cmd,
                    1,
                    stdout="ERROR: Missing export template\n   at: export_project (editor/export/editor_export.cpp:101)\n",
                )

            with mock.patch("godot_playwright.export.subprocess.run", side_effect=fake_run):
                report = export_project(project, "Linux", "build/game.pck", mode="pack")

            self.assertFalse(report["ok"])
            self.assertEqual(report["preset_export_path"], "configured/game.pck")
            self.assertEqual(report["output_relative_path"], "build/game.pck")
            self.assertFalse(report["output_matches_preset"])
            self.assertFalse(report["preset_output_state"]["exists"])
            self.assertEqual(report["diagnostic_count"], 1)
            self.assertEqual(report["diagnostics"][0]["kind"], "ERROR")
            self.assertEqual(report["diagnostics"][0]["path"], "editor/export/editor_export.cpp")
            self.assertEqual(report["diagnostics"][0]["line"], 101)

    def test_export_project_can_raise_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(cmd, 1, stdout="missing templates\n")

            with mock.patch("godot_playwright.export.subprocess.run", side_effect=fake_run):
                with self.assertRaises(ExportError) as raised:
                    export_project(project, "Linux", "build/game.x86_64", check=True)

            self.assertFalse(raised.exception.report["ok"])
            self.assertEqual(raised.exception.report["exit_code"], 1)
            self.assertFalse(raised.exception.report["preset_found"])
            self.assertFalse(raised.exception.report["output_changed"])
            self.assertIn("missing templates", "\n".join(raised.exception.report["stdout_tail"]))

    def test_cli_export_invokes_runner(self) -> None:
        report = {
            "ok": True,
            "preset": "Linux",
            "mode": "pack",
            "output_path": "/tmp/game.pck",
            "output_exists": True,
            "output_bytes": 3,
            "preset_found": True,
            "preset_state": {"platform": "Linux", "export_path": "build/game.pck"},
            "output_changed": True,
            "output_matches_preset": True,
            "diagnostics": [],
            "log_path": "/tmp/game.pck.log",
            "exit_code": 0,
            "duration_ms": 1.0,
            "stdout_tail": [],
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.export_project", return_value=report) as export:
            with redirect_stdout(stdout):
                code = cli_main(["export", "/tmp/project", "Linux", "build/game.pck", "--mode", "pack"])

        self.assertEqual(code, 0)
        self.assertIn("PASS export Linux", stdout.getvalue())
        self.assertIn("preset: found platform=Linux configured_path=build/game.pck", stdout.getvalue())
        self.assertIn("output_changed: True", stdout.getvalue())
        self.assertIn("output_matches_preset: True", stdout.getvalue())
        export.assert_called_once()
        self.assertEqual(export.call_args.args[:3], ("/tmp/project", "Linux", "build/game.pck"))
        self.assertEqual(export.call_args.kwargs["mode"], "pack")


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class ExportIntegrationTests(unittest.TestCase):
    def test_export_project_reports_real_godot_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Export Probe")
            report = export_project(
                project,
                "Missing Preset",
                root / "build" / "missing.pck",
                mode="pack",
                timeout=30,
            )

            self.assertFalse(report["ok"])
            self.assertNotEqual(report["exit_code"], 0)
            self.assertFalse(report["output_exists"])
            self.assertTrue(Path(report["log_path"]).exists())
            self.assertIn("--export-pack", report["command"])
            self.assertTrue(report["stdout_tail"])


if __name__ == "__main__":
    unittest.main()

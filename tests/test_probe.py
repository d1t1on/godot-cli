from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from godot_playwright.cli import main as cli_main
from godot_playwright.probe import ProbeError, probe_project, probe_project_scenes, summarize_godot_output
from godot_playwright.project import init_project


class ProbeUnitTests(unittest.TestCase):
    def test_probe_project_reports_clean_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(cmd, 0, stdout="Godot Engine\n")

            with mock.patch("godot_playwright.probe.subprocess.run", side_effect=fake_run) as run:
                report = probe_project(project, scene="res://scenes/main.tscn", executable="godot-test", frames=3)

            self.assertTrue(report["ok"])
            self.assertEqual(report["exit_code"], 0)
            self.assertEqual(report["log_summary"]["error_count"], 0)
            self.assertIn("--quit-after", report["command"])
            self.assertIn("--scene", report["command"])
            self.assertTrue(Path(report["log_path"]).exists())
            self.assertEqual(run.call_args.kwargs["cwd"], project.resolve())

    def test_probe_project_detects_logged_errors_and_can_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")

            output = (
                "USER ERROR: Agent runtime failure\n"
                "   at: push_error (core/variant/variant_utility.cpp:1111)\n"
            )

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(cmd, 0, stdout=output)

            with mock.patch("godot_playwright.probe.subprocess.run", side_effect=fake_run):
                with self.assertRaises(ProbeError) as raised:
                    probe_project(project, check=True)

            report = raised.exception.report
            self.assertFalse(report["ok"])
            self.assertEqual(report["log_summary"]["error_count"], 1)
            self.assertEqual(report["log_summary"]["diagnostics"][0]["kind"], "USER ERROR")

    def test_cli_probe_invokes_runner(self) -> None:
        report = {
            "ok": True,
            "scene": "res://scenes/main.tscn",
            "log_path": "/tmp/probe.log",
            "exit_code": 0,
            "duration_ms": 1.0,
            "log_summary": {"error_count": 0, "warning_count": 0, "diagnostics": []},
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.probe_project", return_value=report) as probe:
            with redirect_stdout(stdout):
                code = cli_main(["probe", "/tmp/project", "--scene", "res://scenes/main.tscn"])

        self.assertEqual(code, 0)
        self.assertIn("PASS probe res://scenes/main.tscn", stdout.getvalue())
        probe.assert_called_once()
        self.assertEqual(probe.call_args.args[:1], ("/tmp/project",))
        self.assertEqual(probe.call_args.kwargs["scene"], "res://scenes/main.tscn")

    def test_probe_project_scenes_discovers_and_aggregates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "scenes").mkdir(parents=True)
            (project / "addons" / "tool").mkdir(parents=True)
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (project / "scenes" / "main.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
            (project / "scenes" / "broken.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
            (project / "addons" / "tool" / "ignored.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                scene = cmd[cmd.index("--scene") + 1]
                if scene.endswith("broken.tscn"):
                    return subprocess.CompletedProcess(cmd, 0, stdout="ERROR: Broken scene\n")
                return subprocess.CompletedProcess(cmd, 0, stdout="Godot Engine\n")

            with mock.patch("godot_playwright.probe.subprocess.run", side_effect=fake_run):
                report = probe_project_scenes(project, exclude=["addons/**"], frames=2)

            self.assertFalse(report["ok"])
            self.assertEqual(report["scene_count"], 2)
            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["failed"], 1)
            self.assertEqual([scene["scene"] for scene in report["scenes"]], [
                "res://scenes/broken.tscn",
                "res://scenes/main.tscn",
            ])
            self.assertEqual(report["diagnostics"][0]["scene"], "res://scenes/broken.tscn")
            self.assertEqual(report["diagnostics"][0]["kind"], "ERROR")

    def test_cli_probe_scenes_invokes_runner(self) -> None:
        report = {
            "ok": True,
            "scene_count": 2,
            "passed": 2,
            "failed": 0,
            "duration_ms": 1.0,
            "artifacts_dir": "/tmp/artifacts",
            "scenes": [
                {
                    "ok": True,
                    "scene": "res://scenes/main.tscn",
                    "log_path": "/tmp/main.log",
                    "log_summary": {"error_count": 0, "warning_count": 0, "diagnostics": []},
                }
            ],
            "diagnostics": [],
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.probe_project_scenes", return_value=report) as probe:
            with redirect_stdout(stdout):
                code = cli_main(["probe-scenes", "/tmp/project", "res://scenes", "--exclude", "addons/**"])

        self.assertEqual(code, 0)
        self.assertIn("PASS scene probes 2/2 passed", stdout.getvalue())
        probe.assert_called_once()
        self.assertEqual(probe.call_args.args[:2], ("/tmp/project", ["res://scenes"]))
        self.assertEqual(probe.call_args.kwargs["exclude"], ["addons/**"])

    def test_summarize_godot_output_extracts_diagnostics(self) -> None:
        summary = summarize_godot_output(
            "SCRIPT ERROR: Parse Error: Bad thing.\n"
            "          at: GDScript::reload (res://scripts/bad.gd:9)\n"
            "USER WARNING: Careful.\n"
        )

        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["warning_count"], 1)
        self.assertEqual(summary["diagnostics"][0]["path"], "res://scripts/bad.gd")
        self.assertEqual(summary["diagnostics"][0]["line"], 9)
        self.assertEqual(summary["diagnostics"][1]["kind"], "USER WARNING")


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class ProbeIntegrationTests(unittest.TestCase):
    def test_probe_project_reports_real_runtime_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Probe Project")
            artifacts = root / "artifacts"

            clean = probe_project(project, frames=3, artifacts_dir=artifacts)
            self.assertTrue(clean["ok"])
            self.assertEqual(clean["log_summary"]["error_count"], 0)

            (project / "scripts" / "main.gd").write_text(
                'extends Control\n\nfunc _ready() -> void:\n\tpush_error("Agent runtime failure")\n',
                encoding="utf-8",
            )
            failed = probe_project(project, frames=3, artifacts_dir=artifacts)
            self.assertFalse(failed["ok"])
            self.assertGreaterEqual(failed["log_summary"]["error_count"], 1)
            self.assertTrue(
                any("Agent runtime failure" in item["message"] for item in failed["log_summary"]["diagnostics"]),
                failed,
            )
            self.assertTrue(Path(failed["log_path"]).exists())

    def test_probe_project_scenes_reports_real_runtime_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Scene Probe Project")
            artifacts = root / "artifacts"

            (project / "scripts" / "broken_scene.gd").write_text(
                'extends Control\n\nfunc _ready() -> void:\n\tpush_error("Agent scene probe failure")\n',
                encoding="utf-8",
            )
            (project / "scenes" / "broken_scene.tscn").write_text(
                '[gd_scene load_steps=2 format=3]\n\n'
                '[ext_resource type="Script" path="res://scripts/broken_scene.gd" id="1_broken"]\n\n'
                '[node name="BrokenScene" type="Control"]\n'
                'script = ExtResource("1_broken")\n',
                encoding="utf-8",
            )

            report = probe_project_scenes(project, ["res://scenes"], frames=3, artifacts_dir=artifacts)

            self.assertFalse(report["ok"])
            self.assertGreaterEqual(report["scene_count"], 3)
            self.assertGreaterEqual(report["failed"], 1)
            self.assertIn("res://scenes/broken_scene.tscn", {scene["scene"] for scene in report["scenes"]})
            self.assertTrue(
                any("Agent scene probe failure" in item["message"] for item in report["diagnostics"]),
                report,
            )
            self.assertTrue(all(Path(scene["log_path"]).exists() for scene in report["scenes"]))


if __name__ == "__main__":
    unittest.main()

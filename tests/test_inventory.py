from __future__ import annotations

import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from godot_playwright.cli import main as cli_main
from godot_playwright.inventory import ProjectInventoryError, inspect_export_presets, inspect_project


class ProjectInventoryTests(unittest.TestCase):
    def test_inspect_project_reports_settings_files_autoloads_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "scenes").mkdir(parents=True)
            (project / "scripts").mkdir()
            (project / "data").mkdir()
            (project / "assets").mkdir()
            (project / "addons" / "ignored").mkdir(parents=True)
            (project / "project.godot").write_text(
                textwrap.dedent(
                    """\
                    config_version=5

                    [application]
                    config/name="Agent Game"
                    run/main_scene="res://scenes/main.tscn"
                    config/features=PackedStringArray("4.6")

                    [autoload]
                    AgentState="*res://scripts/state.gd"
                    MissingState="*res://scripts/missing.gd"
                    """
                ),
                encoding="utf-8",
            )
            (project / "export_presets.cfg").write_text(
                textwrap.dedent(
                    """\
                    [preset.0]
                    name="Agent Linux"
                    platform="Linux"
                    runnable=false
                    export_filter="all_resources"
                    export_path="build/agent.x86_64"

                    [preset.0.options]
                    binary_format/embed_pck=false
                    """
                ),
                encoding="utf-8",
            )
            (project / "scenes" / "main.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
            (project / "scenes" / "secondary.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
            (project / "scripts" / "state.gd").write_text("extends Node\n", encoding="utf-8")
            (project / "scripts" / "main.gd").write_text("extends Node\n", encoding="utf-8")
            (project / "data" / "item.tres").write_text("[gd_resource format=3]\n", encoding="utf-8")
            (project / "assets" / "pixel.png").write_bytes(b"png")
            (project / "addons" / "ignored" / "ignored.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")

            report = inspect_project(project, exclude=["addons/**"])

            self.assertFalse(report["ok"])
            self.assertEqual(report["name"], "Agent Game")
            self.assertEqual(report["project_file"]["values"]["application"]["config/features"]["args"], ["4.6"])
            self.assertEqual(report["main_scene"]["path"], "res://scenes/main.tscn")
            self.assertTrue(report["main_scene"]["exists"])
            self.assertEqual(report["autoload_count"], 2)
            self.assertEqual(report["autoloads"][0]["name"], "AgentState")
            self.assertTrue(report["autoloads"][0]["exists"])
            self.assertEqual(report["diagnostics"][0]["kind"], "AUTOLOAD_MISSING")
            self.assertEqual(report["export_presets"]["count"], 1)
            self.assertEqual(report["export_presets"]["presets"][0]["name"], "Agent Linux")
            self.assertFalse(report["export_presets"]["presets"][0]["runnable"])
            self.assertFalse(report["export_presets"]["presets"][0]["options"]["binary_format/embed_pck"])
            export_presets = inspect_export_presets(project, include_settings=False)
            self.assertEqual(export_presets["count"], 1)
            self.assertEqual(export_presets["presets"][0]["export_path"], "build/agent.x86_64")
            self.assertNotIn("values", export_presets)
            summary_only = inspect_project(project, exclude=["addons/**"], include_settings=False)
            self.assertEqual(summary_only["name"], "Agent Game")
            self.assertEqual(summary_only["main_scene"]["path"], "res://scenes/main.tscn")
            self.assertEqual(summary_only["autoload_count"], 2)
            self.assertEqual(summary_only["project_file"]["values"], {})
            self.assertEqual(summary_only["project_file"]["entries"], {})
            self.assertEqual(report["files"]["scene_count"], 2)
            self.assertEqual(report["files"]["script_count"], 2)
            self.assertEqual(report["files"]["resource_count"], 1)
            self.assertEqual(report["files"]["asset_count"], 1)
            self.assertEqual(report["files"]["extension_counts"][".tscn"], 2)
            self.assertEqual(report["files"]["extension_counts"][".gd"], 2)
            self.assertEqual(report["files"]["extension_counts"][".png"], 1)
            self.assertEqual(report["files"]["scale"]["file_count"], report["files"]["count"])
            self.assertEqual(report["files"]["scale"]["directory_count"], 5)
            self.assertEqual(report["files"]["scale"]["max_path_depth"], 2)
            self.assertEqual(report["files"]["scale"]["category_counts"]["scenes"], 2)
            self.assertEqual(report["files"]["scale"]["category_counts"]["scripts"], 2)
            self.assertEqual(report["files"]["scale"]["category_counts"]["resources"], 1)
            self.assertEqual(report["files"]["scale"]["category_counts"]["assets"], 1)
            self.assertEqual(report["files"]["scale"]["category_counts"]["other"], 2)
            self.assertTrue(any(entry["path"] == "res://" for entry in report["files"]["scale"]["top_directories"]))
            self.assertEqual(
                report["files"]["total_bytes"],
                sum(entry["bytes"] for entry in report["files"]["files"]),
            )
            self.assertGreaterEqual(len(report["files"]["largest_files"]), 1)
            self.assertGreaterEqual(len(report["files"]["newest_files"]), 1)
            self.assertIsInstance(report["files"]["files"][0]["mtime_ns"], int)
            with self.assertRaises(ProjectInventoryError):
                inspect_project(project, exclude=["addons/**"], check=True)

    def test_inspect_project_resolves_uid_main_scene_and_autoloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "scenes").mkdir(parents=True)
            (project / "scripts").mkdir()
            (project / "project.godot").write_text(
                textwrap.dedent(
                    """\
                    config_version=5

                    [application]
                    config/name="UID Game"
                    run/main_scene="uid://mainuid"

                    [autoload]
                    AgentState="*uid://stateuid"
                    """
                ),
                encoding="utf-8",
            )
            (project / "scenes" / "main.tscn").write_text(
                '[gd_scene format=3 uid="uid://mainuid"]\n',
                encoding="utf-8",
            )
            (project / "scripts" / "state.gd").write_text("extends Node\n", encoding="utf-8")
            (project / "scripts" / "state.gd.uid").write_text("uid://stateuid\n", encoding="utf-8")

            report = inspect_project(project)

            self.assertTrue(report["ok"])
            self.assertEqual(report["main_scene"]["path"], "res://scenes/main.tscn")
            self.assertEqual(report["main_scene"]["raw_path"], "uid://mainuid")
            self.assertEqual(report["main_scene"]["uid"], "uid://mainuid")
            self.assertTrue(report["main_scene"]["exists"])
            self.assertEqual(report["autoloads"][0]["path"], "res://scripts/state.gd")
            self.assertEqual(report["autoloads"][0]["raw_path"], "uid://stateuid")
            self.assertEqual(report["autoloads"][0]["uid"], "uid://stateuid")
            self.assertTrue(report["autoloads"][0]["exists"])

    def test_inspect_project_can_omit_settings_and_report_missing_project_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()

            report = inspect_project(project, include_settings=False)

            self.assertFalse(report["ok"])
            self.assertFalse(report["project_file"]["exists"])
            self.assertEqual(report["project_file"]["values"], {})
            self.assertEqual(report["diagnostics"][0]["kind"], "PROJECT_FILE_MISSING")
            self.assertEqual(report["files"]["total_bytes"], 0)
            self.assertEqual(report["files"]["extension_counts"], {})
            self.assertEqual(report["files"]["largest_files"], [])
            self.assertEqual(report["files"]["scale"]["file_count"], 0)
            self.assertEqual(report["files"]["scale"]["directory_count"], 0)

    def test_cli_inspect_project_invokes_inventory(self) -> None:
        report = {
            "ok": True,
            "project": "/tmp/project",
            "name": "Agent Game",
            "main_scene": {"path": "res://scenes/main.tscn", "exists": True},
            "autoload_count": 0,
            "autoloads": [],
            "export_presets": {"count": 0, "presets": []},
            "files": {
                "scene_count": 1,
                "script_count": 1,
                "resource_count": 0,
                "asset_count": 0,
                "total_bytes": 256,
                "extension_counts": {".gd": 1, ".tscn": 1},
                "scale": {
                    "file_count": 2,
                    "directory_count": 2,
                    "total_bytes": 256,
                    "average_file_bytes": 128.0,
                    "largest_file_bytes": 192,
                    "max_path_depth": 2,
                    "top_directories": [
                        {"path": "res://scenes", "count": 1, "bytes": 192},
                        {"path": "res://scripts", "count": 1, "bytes": 64},
                    ],
                },
                "largest_files": [{"path": "res://scenes/main.tscn", "bytes": 192}],
            },
            "duration_ms": 1.0,
            "diagnostics": [],
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.inspect_project", return_value=report) as inspect:
            with redirect_stdout(stdout):
                code = cli_main(["inspect-project", "/tmp/project", "--exclude", "addons/**", "--no-settings"])

        self.assertEqual(code, 0)
        self.assertIn("PASS project /tmp/project", stdout.getvalue())
        self.assertIn("bytes=256", stdout.getvalue())
        self.assertIn("extensions: .gd=1 .tscn=1", stdout.getvalue())
        self.assertIn("scale: dirs=2 max_depth=2 avg_file_bytes=128.0 largest_file_bytes=192", stdout.getvalue())
        self.assertIn("top_dirs: res://scenes=1 files/192 bytes", stdout.getvalue())
        self.assertIn("large res://scenes/main.tscn: 192 bytes", stdout.getvalue())
        inspect.assert_called_once()
        self.assertEqual(inspect.call_args.args[:1], ("/tmp/project",))
        self.assertEqual(inspect.call_args.kwargs["exclude"], ["addons/**"])
        self.assertFalse(inspect.call_args.kwargs["include_settings"])


if __name__ == "__main__":
    unittest.main()

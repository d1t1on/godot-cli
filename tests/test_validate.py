from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from godot_playwright.cli import main as cli_main
from godot_playwright.validate import ProjectValidationError, validate_project


class ProjectValidationTests(unittest.TestCase):
    def test_validate_project_aggregates_checks_and_can_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()

            scripts = {
                "ok": True,
                "script_count": 2,
                "passed": 2,
                "failed": 0,
                "diagnostics": [],
                "diagnostic_count": 0,
            }
            resources = {
                "ok": False,
                "resource_count": 1,
                "passed": 0,
                "failed": 1,
                "diagnostics": [
                    {
                        "kind": "MISSING_RESOURCE_DEPENDENCY",
                        "message": "Missing external resource: res://data/missing.tres",
                        "path": "res://data/missing.tres",
                        "resource": "res://scenes/main.tscn",
                    }
                ],
                "diagnostic_count": 1,
            }
            scene_inspect = {
                "ok": True,
                "scene_count": 1,
                "passed": 1,
                "failed": 0,
                "diagnostics": [],
                "diagnostic_count": 0,
            }
            runtime = {
                "ok": True,
                "scene_count": 1,
                "passed": 1,
                "failed": 0,
                "diagnostics": [],
                "diagnostic_count": 0,
            }
            inventory = {
                "ok": True,
                "files": {
                    "count": 4,
                    "total_bytes": 512,
                    "scale": {
                        "file_count": 4,
                        "directory_count": 3,
                        "total_bytes": 512,
                        "average_file_bytes": 128.0,
                        "largest_file_bytes": 256,
                        "max_path_depth": 2,
                        "category_counts": {"scenes": 1, "scripts": 1, "resources": 1, "assets": 1, "other": 0},
                        "category_bytes": {"scenes": 128, "scripts": 128, "resources": 128, "assets": 128, "other": 0},
                        "top_extensions": [{"extension": ".gd", "count": 1, "bytes": 128}],
                        "top_directories": [{"path": "res://scenes", "count": 1, "bytes": 128}],
                    },
                },
                "autoload_count": 1,
                "export_presets": {"count": 1},
                "diagnostics": [],
                "diagnostic_count": 0,
            }

            with (
                mock.patch("godot_playwright.validate.inspect_project", return_value=inventory) as inspect_inventory,
                mock.patch("godot_playwright.validate.check_project_scripts", return_value=scripts) as check_scripts,
                mock.patch("godot_playwright.validate.check_project_resources", return_value=resources) as check_resources,
                mock.patch("godot_playwright.validate.inspect_project_scenes", return_value=scene_inspect) as inspect_scenes,
                mock.patch("godot_playwright.validate.probe_project_scenes", return_value=runtime) as probe_scenes,
            ):
                report = validate_project(
                    project,
                    ["res://scenes"],
                    exclude=["addons/**"],
                    executable="godot-test",
                    frames=2,
                    artifacts_dir=Path(tmp) / "artifacts",
                )

            self.assertFalse(report["ok"])
            self.assertEqual(report["check_count"], 5)
            self.assertEqual(report["failed_checks"], ["resources"])
            self.assertEqual(report["diagnostics"][0]["check"], "resources")
            self.assertEqual(report["checks"]["inventory"]["files"]["count"], 4)
            self.assertEqual(report["scale"]["file_count"], 4)
            self.assertEqual(report["scale"]["directory_count"], 3)
            self.assertEqual(report["scale"]["max_path_depth"], 2)
            inspect_inventory.assert_called_once()
            self.assertEqual(inspect_inventory.call_args.args[:1], (project.resolve(),))
            self.assertEqual(inspect_inventory.call_args.kwargs["exclude"], ["addons/**"])
            self.assertFalse(inspect_inventory.call_args.kwargs["include_settings"])
            check_scripts.assert_called_once()
            self.assertEqual(check_scripts.call_args.args[:2], (project.resolve(), ["res://scenes"]))
            self.assertEqual(check_scripts.call_args.kwargs["exclude"], ["addons/**"])
            self.assertEqual(check_scripts.call_args.kwargs["executable"], "godot-test")
            self.assertTrue(check_scripts.call_args.kwargs["ensure_import_cache"])
            check_resources.assert_called_once()
            inspect_scenes.assert_called_once()
            probe_scenes.assert_called_once()
            self.assertEqual(probe_scenes.call_args.kwargs["frames"], 2)

            with (
                mock.patch("godot_playwright.validate.inspect_project", return_value=inventory),
                mock.patch("godot_playwright.validate.check_project_scripts", return_value=scripts),
                mock.patch("godot_playwright.validate.check_project_resources", return_value=resources),
                mock.patch("godot_playwright.validate.inspect_project_scenes", return_value=scene_inspect),
                mock.patch("godot_playwright.validate.probe_project_scenes", return_value=runtime),
            ):
                with self.assertRaises(ProjectValidationError):
                    validate_project(project, check=True)

    def test_validate_project_skip_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            with (
                mock.patch("godot_playwright.validate.inspect_project") as inspect_inventory,
                mock.patch("godot_playwright.validate.check_project_scripts") as check_scripts,
                mock.patch("godot_playwright.validate.check_project_resources") as check_resources,
                mock.patch("godot_playwright.validate.inspect_project_scenes") as inspect_scenes,
                mock.patch("godot_playwright.validate.probe_project_scenes") as probe_scenes,
            ):
                report = validate_project(
                    project,
                    skip_inventory=True,
                    skip_scripts=True,
                    skip_resources=True,
                    skip_scene_inspect=True,
                    skip_runtime=True,
                )

            self.assertTrue(report["ok"])
            self.assertEqual(report["check_count"], 0)
            inspect_inventory.assert_not_called()
            check_scripts.assert_not_called()
            check_resources.assert_not_called()
            inspect_scenes.assert_not_called()
            probe_scenes.assert_not_called()

    def test_cli_validate_invokes_project_validation(self) -> None:
        report = {
            "ok": True,
            "check_count": 5,
            "passed": 5,
            "failed": 0,
            "duration_ms": 1.0,
            "artifacts_dir": "/tmp/report",
            "scale": {
                "file_count": 8,
                "directory_count": 4,
                "total_bytes": 1024,
                "max_path_depth": 3,
                "top_extensions": [
                    {"extension": ".gd", "count": 2, "bytes": 512},
                    {"extension": ".tscn", "count": 2, "bytes": 512},
                ],
            },
            "checks": {
                "inventory": {
                    "ok": True,
                    "files": {
                        "count": 8,
                        "total_bytes": 1024,
                        "scale": {"directory_count": 4, "max_path_depth": 3},
                    },
                    "autoload_count": 1,
                    "export_presets": {"count": 1},
                },
                "scripts": {"ok": True, "passed": 2, "script_count": 2},
                "resources": {"ok": True, "passed": 2, "resource_count": 2},
                "scene_inspect": {"ok": True, "passed": 2, "scene_count": 2},
                "runtime": {"ok": True, "passed": 2, "scene_count": 2},
            },
            "diagnostics": [
                {
                    "check": "inventory",
                    "kind": "MAIN_SCENE_NOT_CONFIGURED",
                    "message": "application/run/main_scene is not configured",
                    "path": "project.godot",
                    "line": None,
                }
            ],
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.validate_project", return_value=report) as validate:
            with redirect_stdout(stdout):
                code = cli_main(
                    [
                        "validate",
                        "/tmp/project",
                        "res://scenes",
                        "--exclude",
                        "addons/**",
                        "--skip-runtime",
                    ]
                )

        self.assertEqual(code, 0)
        self.assertIn("PASS validation 5/5 checks passed", stdout.getvalue())
        self.assertIn("scale: files=8 dirs=4 bytes=1024 max_depth=3", stdout.getvalue())
        self.assertIn("scale_extensions: .gd=2 .tscn=2", stdout.getvalue())
        self.assertIn("PASS inventory: 8 files, 1024 bytes, 1 autoloads, 1 export presets", stdout.getvalue())
        self.assertIn("inventory: MAIN_SCENE_NOT_CONFIGURED: application/run/main_scene is not configured (project.godot)", stdout.getvalue())
        self.assertNotIn("project.godot:None", stdout.getvalue())
        validate.assert_called_once()
        self.assertEqual(validate.call_args.args[:2], ("/tmp/project", ["res://scenes"]))
        self.assertEqual(validate.call_args.kwargs["exclude"], ["addons/**"])
        self.assertFalse(validate.call_args.kwargs["skip_inventory"])
        self.assertTrue(validate.call_args.kwargs["skip_runtime"])
        self.assertTrue(validate.call_args.kwargs["ensure_import_cache"])

        with mock.patch("godot_playwright.cli.validate_project", return_value=report) as validate:
            with redirect_stdout(StringIO()):
                cli_main(["validate", "/tmp/project", "--no-import-cache"])
        self.assertFalse(validate.call_args.kwargs["ensure_import_cache"])


if __name__ == "__main__":
    unittest.main()

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

from godot_playwright.checks import (
    ResourceCheckError,
    ScriptCheckError,
    check_project_resources,
    check_resource_dependencies,
    check_script,
    check_project_scripts,
    expect_script_file,
)
from godot_playwright.cli import main as cli_main
from godot_playwright.project import init_project


class ScriptCheckUnitTests(unittest.TestCase):
    def test_check_script_reports_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (project / "scripts").mkdir()
            (project / "scripts" / "agent.gd").write_text("extends Node\n", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(cmd, 0, stdout="Godot Engine\n")

            with mock.patch("godot_playwright.checks.subprocess.run", side_effect=fake_run) as run:
                report = check_script(project, "res://scripts/agent.gd", executable="godot-test")

            self.assertTrue(report["ok"])
            self.assertEqual(report["diagnostic_count"], 0)
            self.assertTrue(report["import_cache"]["ok"])
            self.assertIn("--check-only", report["command"])
            self.assertIn("res://scripts/agent.gd", report["command"])
            self.assertIn("--import", run.call_args_list[0].args[0])
            self.assertEqual(run.call_args_list[0].kwargs["env"]["GODOT_PLAYWRIGHT_PORT"], "0")
            self.assertTrue(Path(report["log_path"]).exists())
            self.assertEqual(run.call_args.kwargs["cwd"], project.resolve())

    def test_expect_script_file_checks_source_and_godot_parser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (project / "scripts").mkdir()
            (project / "scripts" / "agent.gd").write_text(
                "class_name AgentTool\nextends Node\n\nstatic func make() -> int:\n\treturn 7\n",
                encoding="utf-8",
            )

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(cmd, 0, stdout="Godot Engine\n")

            script = expect_script_file(
                project,
                "res://scripts/agent.gd",
                executable="godot-test",
                artifacts_dir=Path(tmp) / "artifacts",
            )
            with mock.patch("godot_playwright.checks.subprocess.run", side_effect=fake_run):
                self.assertTrue(script.to_exist(timeout=0.1)["exists"])
                self.assertEqual(script.to_extend("Node", timeout=0.1), "Node")
                self.assertEqual(script.to_have_class_name("AgentTool", timeout=0.1), "AgentTool")
                self.assertTrue(script.to_define_function("make", timeout=0.1)["static"])
                self.assertIn("return 7", script.to_contain_source("return 7", timeout=0.1))
                self.assertTrue(script.to_pass_godot_check(timeout=0.1)["ok"])
                script.not_to_have_diagnostic(kind="SCRIPT ERROR", timeout=0.1)

    def test_expect_script_file_can_match_expected_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (project / "scripts").mkdir()
            (project / "scripts" / "broken.gd").write_text("extends Node\n\nfunc value():\n\treturn \n", encoding="utf-8")

            output = textwrap.dedent(
                """\
                SCRIPT ERROR: Parse Error: Expected expression.
                          at: GDScript::reload (res://scripts/broken.gd:4)
                """
            )

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(cmd, 1, stdout=output)

            script = expect_script_file(
                project,
                "res://scripts/broken.gd",
                executable="godot-test",
                artifacts_dir=Path(tmp) / "artifacts",
            )
            with mock.patch("godot_playwright.checks.subprocess.run", side_effect=fake_run):
                diagnostic = script.to_have_diagnostic(
                    "Expected expression",
                    kind="SCRIPT ERROR",
                    path="res://scripts/broken.gd",
                    line=4,
                    timeout=0.1,
                )
                self.assertEqual(diagnostic["severity"], "error")
                with self.assertRaisesRegex(AssertionError, "pass Godot check"):
                    script.to_pass_godot_check(timeout=0.01, interval=0.001)

    def test_check_script_parses_errors_and_can_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")

            output = textwrap.dedent(
                """\
                SCRIPT ERROR: Parse Error: Expected expression.
                          at: GDScript::reload (res://scripts/broken.gd:4)
                ERROR: Failed to load script "res://scripts/broken.gd" with error "Parse error".
                   at: load (modules/gdscript/gdscript.cpp:2907)
                """
            )

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(cmd, 1, stdout=output)

            with mock.patch("godot_playwright.checks.subprocess.run", side_effect=fake_run):
                with self.assertRaises(ScriptCheckError) as raised:
                    check_script(project, "res://scripts/broken.gd", check=True)

            report = raised.exception.report
            self.assertFalse(report["ok"])
            self.assertEqual(report["diagnostics"][0]["kind"], "SCRIPT ERROR")
            self.assertEqual(report["diagnostics"][0]["path"], "res://scripts/broken.gd")
            self.assertEqual(report["diagnostics"][0]["line"], 4)

    def test_cli_check_script_invokes_runner(self) -> None:
        report = {
            "ok": True,
            "script": "res://scripts/agent.gd",
            "log_path": "/tmp/agent-check.log",
            "exit_code": 0,
            "duration_ms": 1.0,
            "diagnostics": [],
            "stdout_tail": [],
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.check_script", return_value=report) as check:
            with redirect_stdout(stdout):
                code = cli_main(["check-script", "/tmp/project", "res://scripts/agent.gd"])

        self.assertEqual(code, 0)
        self.assertIn("PASS script res://scripts/agent.gd", stdout.getvalue())
        check.assert_called_once()
        self.assertEqual(check.call_args.args[:2], ("/tmp/project", "res://scripts/agent.gd"))
        self.assertTrue(check.call_args.kwargs["ensure_import_cache"])

        with mock.patch("godot_playwright.cli.check_script", return_value=report) as check:
            with redirect_stdout(StringIO()):
                cli_main(["check-script", "/tmp/project", "res://scripts/agent.gd", "--no-import-cache"])
        self.assertFalse(check.call_args.kwargs["ensure_import_cache"])

    def test_check_project_scripts_discovers_and_aggregates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (project / "scripts").mkdir()
            (project / "addons").mkdir()
            (project / "scripts" / "ok.gd").write_text("extends Node\n", encoding="utf-8")
            (project / "scripts" / "bad.gd").write_text("extends Node\n", encoding="utf-8")
            (project / "addons" / "ignored.gd").write_text("extends Node\n", encoding="utf-8")

            def fake_check(project_path, script, **kwargs):
                ok = str(script).endswith("ok.gd")
                return {
                    "project": str(project_path),
                    "script": str(script),
                    "ok": ok,
                    "diagnostics": []
                    if ok
                    else [
                        {
                            "kind": "SCRIPT ERROR",
                            "message": "Parse Error: Expected expression.",
                            "path": str(script),
                            "line": 3,
                        }
                    ],
                    "diagnostic_count": 0 if ok else 1,
                    "log_path": f"/tmp/{Path(str(script)).name}.log",
                }

            with (
                mock.patch("godot_playwright.checks.ensure_project_import_cache", return_value={"enabled": True, "ok": True}) as ensure,
                mock.patch("godot_playwright.checks.check_script", side_effect=fake_check),
            ):
                report = check_project_scripts(project, ["res://scripts", "res://addons"], exclude=["addons/**"])

            self.assertFalse(report["ok"])
            ensure.assert_called_once()
            self.assertTrue(report["import_cache"]["ok"])
            self.assertEqual(report["script_count"], 2)
            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["diagnostic_count"], 1)
            self.assertEqual(report["diagnostics"][0]["script"], "res://scripts/bad.gd")

    def test_cli_check_scripts_invokes_runner(self) -> None:
        report = {
            "ok": False,
            "script_count": 2,
            "passed": 1,
            "failed": 1,
            "duration_ms": 1.0,
            "diagnostics": [
                {
                    "script": "res://scripts/bad.gd",
                    "kind": "SCRIPT ERROR",
                    "message": "Parse Error",
                    "path": "res://scripts/bad.gd",
                    "line": 3,
                }
            ],
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.check_project_scripts", return_value=report) as check:
            with redirect_stdout(stdout):
                code = cli_main(["check-scripts", "/tmp/project", "res://scripts", "--exclude", "addons/**"])

        self.assertEqual(code, 1)
        self.assertIn("FAIL scripts 1/2 passed", stdout.getvalue())
        check.assert_called_once()
        self.assertEqual(check.call_args.args[:2], ("/tmp/project", ["res://scripts"]))
        self.assertEqual(check.call_args.kwargs["exclude"], ["addons/**"])
        self.assertTrue(check.call_args.kwargs["ensure_import_cache"])

        with mock.patch("godot_playwright.cli.check_project_scripts", return_value=report) as check:
            with redirect_stdout(StringIO()):
                cli_main(["check-scripts", "/tmp/project", "res://scripts", "--no-import-cache"])
        self.assertFalse(check.call_args.kwargs["ensure_import_cache"])

    def test_check_resource_dependencies_reports_missing_ext_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (project / "scenes").mkdir()
            (project / "scripts").mkdir()
            (project / "scripts" / "main.gd").write_text("extends Node\n", encoding="utf-8")
            (project / "scenes" / "relative_data.tres").write_text("[gd_resource format=3]\n", encoding="utf-8")
            (project / "scenes" / "main.tscn").write_text(
                textwrap.dedent(
                    """\
                    [gd_scene load_steps=4 format=3]

                    [ext_resource type="Script" uid="uid://main" path="res://scripts/main.gd" id="1_main"]
                    [ext_resource type="Resource" path="relative_data.tres" id="2_relative"]
                    [ext_resource type="Resource" path="res://data/missing_resource.tres" id="3_missing"]

                    [node name="Main" type="Node"]
                    script = ExtResource("1_main")
                    """
                ),
                encoding="utf-8",
            )

            report = check_resource_dependencies(project, "res://scenes/main.tscn")

            self.assertFalse(report["ok"])
            self.assertEqual(report["dependency_count"], 3)
            self.assertEqual(report["missing_count"], 1)
            self.assertEqual(report["diagnostics"][0]["kind"], "MISSING_RESOURCE_DEPENDENCY")
            self.assertEqual(report["diagnostics"][0]["path"], "res://data/missing_resource.tres")
            relative = next(dependency for dependency in report["dependencies"] if dependency["id"] == "2_relative")
            self.assertEqual(relative["path"], "res://scenes/relative_data.tres")
            self.assertTrue(relative["exists"])

    def test_check_project_resources_discovers_excludes_and_can_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (project / "scenes").mkdir()
            (project / "addons").mkdir()
            (project / "scripts").mkdir()
            (project / "scripts" / "ok.gd").write_text("extends Node\n", encoding="utf-8")
            (project / "scenes" / "ok.tscn").write_text(
                '[gd_scene load_steps=2 format=3]\n\n'
                '[ext_resource type="Script" path="res://scripts/ok.gd" id="1_ok"]\n',
                encoding="utf-8",
            )
            (project / "scenes" / "bad.tscn").write_text(
                '[gd_scene load_steps=2 format=3]\n\n'
                '[ext_resource type="Resource" path="res://data/missing.tres" id="1_missing"]\n',
                encoding="utf-8",
            )
            (project / "addons" / "ignored.tscn").write_text(
                '[gd_scene load_steps=2 format=3]\n\n'
                '[ext_resource type="Resource" path="res://missing/ignored.tres" id="1_ignored"]\n',
                encoding="utf-8",
            )

            report = check_project_resources(project, ["res://scenes", "res://addons"], exclude=["addons/**"])

            self.assertFalse(report["ok"])
            self.assertEqual(report["resource_count"], 2)
            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["diagnostic_count"], 1)
            self.assertEqual(report["diagnostics"][0]["resource"], "res://scenes/bad.tscn")
            with self.assertRaises(ResourceCheckError) as raised:
                check_project_resources(project, ["res://scenes"], check=True)
            self.assertEqual(raised.exception.report["failed"], 1)

    def test_cli_check_resources_invokes_runner(self) -> None:
        report = {
            "ok": False,
            "resource_count": 2,
            "passed": 1,
            "failed": 1,
            "duration_ms": 1.0,
            "diagnostics": [
                {
                    "resource": "res://scenes/bad.tscn",
                    "kind": "MISSING_RESOURCE_DEPENDENCY",
                    "message": "Missing external resource: res://data/missing.tres",
                    "path": "res://data/missing.tres",
                    "line": 3,
                }
            ],
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.check_project_resources", return_value=report) as check:
            with redirect_stdout(stdout):
                code = cli_main(["check-resources", "/tmp/project", "res://scenes", "--exclude", "addons/**"])

        self.assertEqual(code, 1)
        self.assertIn("FAIL resources 1/2 passed", stdout.getvalue())
        check.assert_called_once()
        self.assertEqual(check.call_args.args[:2], ("/tmp/project", ["res://scenes"]))
        self.assertEqual(check.call_args.kwargs["exclude"], ["addons/**"])


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class ScriptCheckIntegrationTests(unittest.TestCase):
    def test_check_script_validates_real_gdscript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Script Check Probe")
            scripts = project / "scripts"
            valid = scripts / "agent_valid.gd"
            invalid = scripts / "agent_invalid.gd"
            valid.write_text("extends Node\n\nfunc value() -> int:\n\treturn 1\n", encoding="utf-8")
            invalid.write_text("extends Node\n\nfunc value() -> int:\n\treturn \n", encoding="utf-8")
            artifacts = root / "artifacts"

            valid_report = check_script(project, "res://scripts/agent_valid.gd", artifacts_dir=artifacts)
            invalid_report = check_script(project, "res://scripts/agent_invalid.gd", artifacts_dir=artifacts)
            project_report = check_project_scripts(
                project,
                ["res://scripts/agent_valid.gd", "res://scripts/agent_invalid.gd"],
                artifacts_dir=artifacts,
            )
            valid_expect = expect_script_file(project, "res://scripts/agent_valid.gd", artifacts_dir=artifacts)
            invalid_expect = expect_script_file(project, "res://scripts/agent_invalid.gd", artifacts_dir=artifacts)

            self.assertTrue(valid_report["ok"])
            self.assertEqual(valid_report["diagnostic_count"], 0)
            self.assertTrue(valid_expect.to_pass_godot_check(timeout=5)["ok"])
            valid_expect.to_extend("Node", timeout=0.1)
            valid_expect.to_define_function("value", timeout=0.1)
            self.assertFalse(invalid_report["ok"])
            self.assertGreaterEqual(invalid_report["diagnostic_count"], 1)
            self.assertEqual(invalid_report["diagnostics"][0]["kind"], "SCRIPT ERROR")
            self.assertEqual(invalid_report["diagnostics"][0]["path"], "res://scripts/agent_invalid.gd")
            self.assertEqual(invalid_report["diagnostics"][0]["line"], 4)
            invalid_expect.to_have_diagnostic(kind="SCRIPT ERROR", path="res://scripts/agent_invalid.gd", timeout=5)
            self.assertTrue(Path(invalid_report["log_path"]).exists())
            self.assertFalse(project_report["ok"])
            self.assertEqual(project_report["script_count"], 2)
            self.assertEqual(project_report["passed"], 1)
            self.assertEqual(project_report["failed"], 1)
            self.assertEqual(project_report["diagnostics"][0]["script"], "res://scripts/agent_invalid.gd")

    def test_check_project_scripts_warms_global_class_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Script Class Cache Probe")
            scripts = project / "scripts"
            (scripts / "agent_base.gd").write_text("class_name AgentBase\nextends Node\n", encoding="utf-8")
            (scripts / "agent_child.gd").write_text("extends AgentBase\n\nfunc value() -> int:\n\treturn 1\n", encoding="utf-8")
            shutil.rmtree(project / ".godot", ignore_errors=True)

            report = check_project_scripts(
                project,
                ["res://scripts/agent_child.gd"],
                artifacts_dir=root / "artifacts",
            )

            self.assertTrue(report["import_cache"]["ok"], report["import_cache"]["stdout_tail"])
            self.assertTrue(report["ok"], report["diagnostics"])
            self.assertEqual(report["passed"], 1)


if __name__ == "__main__":
    unittest.main()

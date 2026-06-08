from __future__ import annotations

import json
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from godot_playwright import Godot, run_tests
from godot_playwright.checks import check_project_resources, check_project_scripts
from godot_playwright.modules import (
    ModuleError,
    add_module,
    default_module_roots,
    list_modules,
    load_module_manifest,
)
from godot_playwright.probe import probe_project
from godot_playwright.project import init_project


class ModuleInstallerUnitTests(unittest.TestCase):
    def test_list_modules_reads_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module_root = Path(tmp) / "modules"
            _write_module_fixture(module_root)

            modules = list_modules(module_root=module_root)

        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["name"], "save_load")
        self.assertEqual(modules[0]["version"], "0.1.0")
        self.assertEqual(modules[0]["description"], "JSON save/load service for Godot projects.")

    def test_repository_save_load_module_is_discoverable(self) -> None:
        modules = list_modules()
        save_load = next(module for module in modules if module["name"] == "save_load")
        self.assertEqual(save_load["version"], "0.1.0")
        self.assertEqual(save_load["godot_version"], ">=4.6")

    def test_packaged_save_load_module_mirror_exists(self) -> None:
        bundled_root = default_module_roots()[1]
        manifest = load_module_manifest("save_load", module_root=bundled_root)
        self.assertEqual(manifest["name"], "save_load")
        self.assertTrue((bundled_root / "save_load" / "addons" / "save_load" / "save_service.gd").exists())

    def test_pyproject_includes_bundled_gameplay_module_data(self) -> None:
        pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"bundled_gameplay_modules/save_load/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/save_load/addons/save_load/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/save_load/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/save_load/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/save_load/tests/*"', pyproject)

    def test_source_and_packaged_save_load_trees_are_identical(self) -> None:
        source_root, bundled_root = default_module_roots()
        source = source_root / "save_load"
        bundled = bundled_root / "save_load"
        source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
        bundled_files = sorted(path.relative_to(bundled) for path in bundled.rglob("*") if path.is_file())

        self.assertEqual([path.as_posix() for path in source_files], [path.as_posix() for path in bundled_files])
        for relative_path in source_files:
            self.assertEqual(
                (source / relative_path).read_bytes(),
                (bundled / relative_path).read_bytes(),
                relative_path.as_posix(),
            )

    def test_save_load_docs_exist_for_humans_and_agents(self) -> None:
        source_root = default_module_roots()[0] / "save_load"
        bundled_root = default_module_roots()[1] / "save_load"
        for root in (source_root, bundled_root):
            readme = (root / "README.md").read_text(encoding="utf-8")
            agent = (root / "AGENT.md").read_text(encoding="utf-8")
            self.assertIn("godot-playwright module add /path/to/project save_load", readme)
            self.assertIn("SaveService.save_slot", readme)
            self.assertIn("save_participants", agent)
            self.assertIn("NodePath fallback", agent)
            self.assertIn("JSON-compatible", agent)

    def test_save_service_rejects_non_finite_float_states(self) -> None:
        source_root = default_module_roots()[0]
        service_source = (source_root / "save_load" / "addons" / "save_load" / "save_service.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("is_nan(value)", service_source)
        self.assertIn("is_inf(value)", service_source)

    def test_load_module_manifest_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module_root = Path(tmp) / "modules"
            module_dir = _write_module_fixture(module_root)
            manifest_path = module_dir / "module.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["unexpected"] = True
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ModuleError, "Unsupported manifest field"):
                load_module_manifest("save_load", module_root=module_root)

    def test_add_module_copies_files_and_registers_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            module_root = root / "modules"
            _write_module_fixture(module_root)

            report = add_module(project, "save_load", module_root=module_root)

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "save_load")
            self.assertTrue((project / "addons" / "save_load" / "save_service.gd").exists())
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertIn('[autoload]', project_text)
            self.assertIn('SaveService="*res://addons/save_load/save_service.gd"', project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertIn("res://addons/save_load/save_service.gd", copied_targets)
            self.assertEqual(report["autoloads"][0]["name"], "SaveService")

    def test_add_module_rejects_existing_files_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            module_root = root / "modules"
            _write_module_fixture(module_root)
            add_module(project, "save_load", module_root=module_root)

            with self.assertRaisesRegex(ModuleError, "Target already exists"):
                add_module(project, "save_load", module_root=module_root)

    def test_add_module_rejects_existing_autoload_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            module_root = root / "modules"
            _write_module_fixture(module_root)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8")
                + '\n[autoload]\n\nSaveService="*res://scripts/other_save_service.gd"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ModuleError, "Autoload already exists"):
                add_module(project, "save_load", module_root=module_root)

    def test_add_module_force_overwrites_module_path_and_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            module_root = root / "modules"
            _write_module_fixture(module_root)
            target_dir = project / "addons" / "save_load"
            target_dir.mkdir(parents=True)
            (target_dir / "save_service.gd").write_text("extends Node\n# stale\n", encoding="utf-8")
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8")
                + '\n[autoload]\n\nSaveService="*res://scripts/other_save_service.gd"\n',
                encoding="utf-8",
            )

            report = add_module(project, "save_load", module_root=module_root, force=True)

            self.assertTrue(report["ok"], report)
            self.assertEqual(
                (target_dir / "save_service.gd").read_text(encoding="utf-8"),
                "extends Node\n",
            )
            self.assertIn(
                'SaveService="*res://addons/save_load/save_service.gd"',
                project_file.read_text(encoding="utf-8"),
            )

    def test_add_module_force_rejects_file_targeting_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            module_root = root / "modules"
            module_dir = _write_module_fixture(module_root)
            (module_dir / "loose_save_service.gd").write_text("extends Node\n", encoding="utf-8")
            manifest_path = module_dir / "module.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["copy"] = [{"from": "loose_save_service.gd", "to": "addons"}]
            manifest["autoloads"] = []
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            addons_dir = project / "addons"
            addons_dir.mkdir()
            unrelated_file = addons_dir / "unrelated.gd"
            unrelated_file.write_text("extends Node\n# keep\n", encoding="utf-8")

            raised: ModuleError | None = None
            try:
                add_module(project, "save_load", module_root=module_root, force=True)
            except ModuleError as exc:
                raised = exc

            self.assertTrue(unrelated_file.exists())
            self.assertEqual(unrelated_file.read_text(encoding="utf-8"), "extends Node\n# keep\n")
            self.assertIsNotNone(raised)
            self.assertRegex(str(raised), "existing directory")

    def test_add_module_rejects_duplicate_planned_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            module_root = root / "modules"
            module_dir = _write_module_fixture(module_root)
            (module_dir / "first.gd").write_text("extends Node\n# first\n", encoding="utf-8")
            (module_dir / "second.gd").write_text("extends Node\n# second\n", encoding="utf-8")
            manifest_path = module_dir / "module.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["copy"] = [
                {"from": "first.gd", "to": "addons/save_load/duplicate.gd"},
                {"from": "second.gd", "to": "addons/save_load/duplicate.gd"},
            ]
            manifest["autoloads"] = []
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ModuleError, "Duplicate copy target"):
                add_module(project, "save_load", module_root=module_root)

    def test_add_module_with_demo_copies_demo_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            module_root = root / "modules"
            _write_module_fixture(module_root)

            report = add_module(project, "save_load", module_root=module_root, demo=True)

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["demo"])
            self.assertTrue((project / "scenes" / "save_load_demo" / "save_load_demo.tscn").exists())
            self.assertTrue((project / "scripts" / "save_load_demo" / "save_load_demo.gd").exists())
            self.assertTrue((project / "tests" / "save_load_demo" / "test_save_load_demo.py").exists())

    def test_add_module_requires_godot_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module_root = Path(tmp) / "modules"
            _write_module_fixture(module_root)
            project = Path(tmp) / "not_project"
            project.mkdir()

            with self.assertRaisesRegex(ModuleError, "Godot project not found"):
                add_module(project, "save_load", module_root=module_root)


def _write_project(project: Path) -> Path:
    project.mkdir(parents=True)
    (project / "project.godot").write_text(
        textwrap.dedent(
            """\
            config_version=5

            [application]

            config/name="Module Test"
            run/main_scene="res://scenes/main.tscn"
            """
        ),
        encoding="utf-8",
    )
    return project


def _write_module_fixture(module_root: Path) -> Path:
    module_dir = module_root / "save_load"
    (module_dir / "addons" / "save_load").mkdir(parents=True)
    (module_dir / "demo" / "scenes").mkdir(parents=True)
    (module_dir / "demo" / "scripts").mkdir(parents=True)
    (module_dir / "tests").mkdir(parents=True)
    (module_dir / "addons" / "save_load" / "save_service.gd").write_text("extends Node\n", encoding="utf-8")
    (module_dir / "demo" / "scenes" / "save_load_demo.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
    (module_dir / "demo" / "scripts" / "save_load_demo.gd").write_text("extends Node\n", encoding="utf-8")
    (module_dir / "tests" / "test_save_load_demo.py").write_text("def test_demo():\n    pass\n", encoding="utf-8")
    (module_dir / "module.json").write_text(
        json.dumps(
            {
                "name": "save_load",
                "version": "0.1.0",
                "display_name": "Save Load",
                "description": "JSON save/load service for Godot projects.",
                "godot_version": ">=4.6",
                "copy": [{"from": "addons/save_load", "to": "addons/save_load"}],
                "autoloads": [
                    {"name": "SaveService", "path": "res://addons/save_load/save_service.gd"}
                ],
                "demo": {
                    "copy": [
                        {"from": "demo/scenes", "to": "scenes/save_load_demo"},
                        {"from": "demo/scripts", "to": "scripts/save_load_demo"},
                        {"from": "tests", "to": "tests/save_load_demo"},
                    ]
                },
                "validation": {
                    "commands": [
                        "godot-playwright check-scripts /path/to/project res://addons/save_load --exclude addons/godot_playwright/**",
                        "godot-playwright check-resources /path/to/project res://addons/save_load --exclude addons/godot_playwright/**",
                    ]
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return module_dir


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class SaveLoadModuleGodotTests(unittest.TestCase):
    def test_installed_save_load_scripts_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Save Load Parse Probe")
            add_module(project, "save_load", demo=True)

            report = check_project_scripts(
                project,
                ["res://addons/save_load", "res://scripts/save_load_demo"],
                artifacts_dir=root / "artifacts",
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_installed_save_load_cold_launches_without_global_class_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Save Load Cold Launch Probe")
            add_module(project, "save_load")
            shutil.rmtree(project / ".godot", ignore_errors=True)

            report = probe_project(project, frames=2, artifacts_dir=root / "artifacts")

        self.assertTrue(report["ok"], report["log_summary"]["tail"])

    def test_save_load_demo_round_trip_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Save Load Runtime Probe")
            add_module(project, "save_load", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/save_load_demo/save_load_demo.tscn"',
                ),
                encoding="utf-8",
            )

            resource_report = check_project_resources(
                project,
                ["res://scenes/save_load_demo"],
            )
            self.assertTrue(resource_report["ok"], resource_report["diagnostics"])

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                unrelated_result = godot.locator("/root/SaveService").call("save_slot", "unrelated_slot")
                self.assertTrue(unrelated_result["ok"], unrelated_result)
                result = godot.locator("#SaveLoadDemo").call("run_round_trip")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["saved_coins"], 2)
        self.assertEqual(result["restored_coins"], 2)
        self.assertEqual(result["restored_position"], [4.0, 8.0])
        self.assertEqual(result["slot_count_after_save"], 1)
        self.assertTrue(result["has_slot_after_save"])
        self.assertFalse(result["has_slot_after_delete"])

    def test_installed_save_load_demo_test_runs_without_main_scene_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Save Load Demo Test Probe")
            add_module(project, "save_load", demo=True)

            report = run_tests(
                project,
                [project / "tests" / "save_load_demo"],
                artifacts_dir=root / "artifacts",
                trace="off",
                timeout=30,
            )

        self.assertEqual(report["failed"], 0, report["tests"])
        self.assertEqual(report["passed"], 1)


if __name__ == "__main__":
    unittest.main()

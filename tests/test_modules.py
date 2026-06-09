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

    def test_repository_inventory_module_is_discoverable(self) -> None:
        modules = list_modules()
        inventory = next(module for module in modules if module["name"] == "inventory")
        self.assertEqual(inventory["version"], "0.1.0")
        self.assertEqual(inventory["godot_version"], ">=4.6")
        self.assertEqual(inventory["autoloads"], [])

    def test_add_inventory_module_copies_files_without_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "inventory")

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "inventory")
            self.assertEqual(report["autoloads"], [])
            self.assertTrue((project / "addons" / "inventory" / "inventory.gd").exists())
            self.assertTrue((project / "addons" / "inventory" / "inventory_item_database.gd").exists())
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertNotIn("InventoryService", project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertIn("res://addons/inventory/inventory.gd", copied_targets)

    def test_add_inventory_module_with_demo_copies_demo_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "inventory", demo=True)

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["demo"])
            self.assertTrue((project / "scenes" / "inventory_demo" / "inventory_demo.tscn").exists())
            self.assertTrue((project / "scripts" / "inventory_demo" / "inventory_demo.gd").exists())
            self.assertTrue((project / "resources" / "inventory_demo" / "item_database.tres").exists())
            self.assertTrue((project / "tests" / "inventory_demo" / "test_inventory_demo.py").exists())

    def test_packaged_save_load_module_mirror_exists(self) -> None:
        bundled_root = default_module_roots()[1]
        manifest = load_module_manifest("save_load", module_root=bundled_root)
        self.assertEqual(manifest["name"], "save_load")
        self.assertTrue((bundled_root / "save_load" / "addons" / "save_load" / "save_service.gd").exists())

    def test_packaged_inventory_module_mirror_exists(self) -> None:
        bundled_root = default_module_roots()[1]
        manifest = load_module_manifest("inventory", module_root=bundled_root)
        self.assertEqual(manifest["name"], "inventory")
        self.assertEqual(manifest["autoloads"], [])
        self.assertTrue((bundled_root / "inventory" / "addons" / "inventory" / "inventory.gd").exists())

    def test_pyproject_includes_bundled_gameplay_module_data(self) -> None:
        pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"bundled_addons/godot_playwright/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/save_load/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/save_load/addons/save_load/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/save_load/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/save_load/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/save_load/tests/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/inventory/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/inventory/addons/inventory/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/inventory/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/inventory/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/inventory/demo/resources/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/inventory/tests/*"', pyproject)

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

    def test_source_and_packaged_inventory_trees_are_identical(self) -> None:
        source_root, bundled_root = default_module_roots()
        source = source_root / "inventory"
        bundled = bundled_root / "inventory"
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

    def test_inventory_source_defines_resource_helpers(self) -> None:
        source_root = default_module_roots()[0]
        inventory_root = source_root / "inventory" / "addons" / "inventory"
        definition = (inventory_root / "inventory_item_definition.gd").read_text(encoding="utf-8")
        database = (inventory_root / "inventory_item_database.gd").read_text(encoding="utf-8")
        result = (inventory_root / "inventory_result.gd").read_text(encoding="utf-8")

        self.assertIn("class_name InventoryItemDefinition", definition)
        self.assertIn("@export var item_id: StringName", definition)
        self.assertIn("@export_range(1, 999, 1) var max_stack: int = 99", definition)
        self.assertIn("class_name InventoryItemDatabase", database)
        self.assertIn("func get_item(item_id: String) -> Resource", database)
        self.assertIn("func validate() -> Dictionary", database)
        self.assertIn("class_name InventoryResult", result)
        self.assertIn("static func add_error", result)

    def test_inventory_source_defines_core_stack_api(self) -> None:
        source_root = default_module_roots()[0]
        inventory_source = (source_root / "inventory" / "addons" / "inventory" / "inventory.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("class_name Inventory", inventory_source)
        self.assertIn("@export var database: Resource", inventory_source)
        self.assertIn("@export_range(0, 999, 1) var capacity: int = 12", inventory_source)
        self.assertIn("func add_item(item_id: String, quantity: int = 1) -> Dictionary", inventory_source)
        self.assertIn("func remove_item(item_id: String, quantity: int = 1) -> Dictionary", inventory_source)
        self.assertIn("func has_item(item_id: String, quantity: int = 1) -> bool", inventory_source)
        self.assertIn("func get_quantity(item_id: String) -> int", inventory_source)
        self.assertIn("func get_stacks() -> Array", inventory_source)
        self.assertIn("func _validate_database(result: Dictionary) -> bool", inventory_source)

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

    def test_add_module_force_overwrites_module_path_and_module_autoload(self) -> None:
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
                + '\n[autoload]\n\nSaveService="*res://addons/save_load/save_service.gd"\n',
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

    def test_add_module_force_rejects_unrelated_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            module_root = root / "modules"
            _write_module_fixture(module_root)
            target_dir = project / "addons" / "save_load"
            target_dir.mkdir(parents=True)
            (target_dir / "save_service.gd").write_text("extends Node\n# stale\n", encoding="utf-8")
            unrelated_service = project / "scripts" / "other_save_service.gd"
            unrelated_service.parent.mkdir(parents=True)
            unrelated_service.write_text("extends Node\n", encoding="utf-8")
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8")
                + '\n[autoload]\n\nSaveService="*res://scripts/other_save_service.gd"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ModuleError, "Autoload already exists"):
                add_module(project, "save_load", module_root=module_root, force=True)

            self.assertTrue(unrelated_service.exists())
            self.assertIn(
                'SaveService="*res://scripts/other_save_service.gd"',
                project_file.read_text(encoding="utf-8"),
            )

    def test_add_module_force_rejects_symlinked_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")
            module_root = root / "modules"
            _write_module_fixture(module_root)
            victim = root / "victim.gd"
            victim.write_text("extends Node\n# keep outside\n", encoding="utf-8")
            target_dir = project / "addons" / "save_load"
            target_dir.mkdir(parents=True)
            symlink_target = target_dir / "save_service.gd"
            symlink_target.symlink_to(victim)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8")
                + '\n[autoload]\n\nSaveService="*res://addons/save_load/save_service.gd"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ModuleError, "symbolic link"):
                add_module(project, "save_load", module_root=module_root, force=True)

            self.assertEqual(victim.read_text(encoding="utf-8"), "extends Node\n# keep outside\n")
            self.assertTrue(symlink_target.is_symlink())

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
class InventorySeedModuleGodotTests(unittest.TestCase):
    def test_installed_inventory_seed_demo_scene_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Inventory Seed Scene Probe")
            add_module(project, "inventory", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/inventory_demo/inventory_demo.tscn"',
                ),
                encoding="utf-8",
            )

            report = probe_project(project, frames=2, artifacts_dir=root / "artifacts")

        self.assertTrue(report["ok"], report["log_summary"]["tail"])

    def test_inventory_database_validation_handles_invalid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Inventory Database Probe")
            add_module(project, "inventory")
            _write_inventory_database_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/inventory_database_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#InventoryDatabaseProbe").call("run_probe")

        self.assertTrue(result["ok"], result)

    def test_inventory_core_stack_operations_run_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Inventory Stack Probe")
            add_module(project, "inventory")
            _write_inventory_stack_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/inventory_stack_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#InventoryStackProbe").call("run_probe")

        self.assertTrue(result["ok"], result)


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

    def test_load_slot_does_not_mutate_when_participant_discovery_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Save Load Duplicate Probe")
            add_module(project, "save_load")
            _write_duplicate_load_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/duplicate_load_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#DuplicateLoadProbe").call("run_duplicate_load")

        self.assertFalse(result["load_result"]["ok"], result)
        self.assertIn("Duplicate save_id: dup", result["load_result"]["errors"])
        self.assertEqual(result["a_value"], 0)
        self.assertEqual(result["b_value"], 0)


def _write_inventory_database_probe(project: Path) -> None:
    (project / "scripts" / "inventory_database_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const InventoryItemDefinitionData := preload("res://addons/inventory/inventory_item_definition.gd")
            const InventoryItemDatabaseData := preload("res://addons/inventory/inventory_item_database.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []

                var potion = InventoryItemDefinitionData.new()
                potion.item_id = &"potion"
                potion.display_name = "Potion"
                potion.max_stack = 5
                var valid_database = InventoryItemDatabaseData.new()
                valid_database.items.append(potion)
                var valid_result: Dictionary = valid_database.validate()
                _assert_bool(bool(valid_result.get("ok", false)), "valid database should pass", errors)
                _assert_bool(valid_database.has_item("potion"), "valid database should find potion", errors)
                _assert_int(5, valid_database.get_max_stack("potion"), "valid database max_stack", errors)

                var invalid_resource_database = InventoryItemDatabaseData.new()
                invalid_resource_database.items.append(Resource.new())
                var invalid_resource_result: Dictionary = invalid_resource_database.validate()
                _assert_bool(not bool(invalid_resource_result.get("ok", true)), "plain Resource should fail validation", errors)
                _assert_contains(invalid_resource_result.get("errors", []), "InventoryItemDefinition", "plain Resource validation error", errors)

                var whitespace_item = InventoryItemDefinitionData.new()
                whitespace_item.item_id = &" potion "
                whitespace_item.max_stack = 5
                var whitespace_database = InventoryItemDatabaseData.new()
                whitespace_database.items.append(whitespace_item)
                var whitespace_result: Dictionary = whitespace_database.validate()
                _assert_bool(not bool(whitespace_result.get("ok", true)), "whitespace item_id should fail validation", errors)
                _assert_contains(whitespace_result.get("errors", []), "whitespace", "whitespace validation error", errors)

                var duplicate_item = InventoryItemDefinitionData.new()
                duplicate_item.item_id = &"potion"
                duplicate_item.max_stack = 1
                var duplicate_database = InventoryItemDatabaseData.new()
                duplicate_database.items.append(potion)
                duplicate_database.items.append(duplicate_item)
                var duplicate_result: Dictionary = duplicate_database.validate()
                _assert_bool(not bool(duplicate_result.get("ok", true)), "duplicate item_id should fail validation", errors)
                _assert_contains(duplicate_result.get("errors", []), "Duplicate item_id", "duplicate validation error", errors)

                var bad_stack_item = InventoryItemDefinitionData.new()
                bad_stack_item.item_id = &"bad_stack"
                bad_stack_item.max_stack = 0
                var bad_stack_database = InventoryItemDatabaseData.new()
                bad_stack_database.items.append(bad_stack_item)
                var bad_stack_result: Dictionary = bad_stack_database.validate()
                _assert_bool(not bool(bad_stack_result.get("ok", true)), "max_stack <= 0 should fail validation", errors)
                _assert_contains(bad_stack_result.get("errors", []), "max_stack", "max_stack validation error", errors)

                return {"ok": errors.is_empty(), "errors": errors}


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %d, got %d" % [label, expected, actual])


            func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        return
                errors.append("%s: missing %s in %s" % [label, needle, str(messages)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "inventory_database_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/inventory_database_probe.gd" id="1_probe_script"]

            [node name="InventoryDatabaseProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )


def _write_inventory_stack_probe(project: Path) -> None:
    (project / "scripts" / "inventory_stack_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const InventoryData := preload("res://addons/inventory/inventory.gd")
            const InventoryItemDefinitionData := preload("res://addons/inventory/inventory_item_definition.gd")
            const InventoryItemDatabaseData := preload("res://addons/inventory/inventory_item_database.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                var inventory = InventoryData.new()
                add_child(inventory)
                inventory.database = _make_database()
                inventory.capacity = 2

                var add_result: Dictionary = inventory.add_item("potion", 12)
                _assert_bool(bool(add_result.get("ok", false)), "partial add should still be ok", errors)
                _assert_int(10, int(add_result.get("added", -1)), "partial add added count", errors)
                _assert_int(2, int(add_result.get("remainder", -1)), "partial add remainder", errors)
                _assert_bool(not (add_result.get("warnings", []) as Array).is_empty(), "partial add should warn", errors)
                _assert_int(10, inventory.get_quantity("potion"), "potion quantity after partial add", errors)
                _assert_int(2, inventory.get_stacks().size(), "stack count after partial add", errors)

                var no_room_result: Dictionary = inventory.add_item("key", 1)
                _assert_bool(not bool(no_room_result.get("ok", true)), "no-room add should fail", errors)
                _assert_int(0, inventory.get_quantity("key"), "key quantity after no-room add", errors)
                _assert_int(10, inventory.get_quantity("potion"), "potion quantity after no-room add", errors)

                var insufficient_remove: Dictionary = inventory.remove_item("potion", 11)
                _assert_bool(not bool(insufficient_remove.get("ok", true)), "insufficient remove should fail", errors)
                _assert_int(10, inventory.get_quantity("potion"), "potion quantity after insufficient remove", errors)

                var remove_result: Dictionary = inventory.remove_item("potion", 6)
                _assert_bool(bool(remove_result.get("ok", false)), "remove should succeed", errors)
                _assert_int(6, int(remove_result.get("removed", -1)), "removed count", errors)
                _assert_int(4, inventory.get_quantity("potion"), "potion quantity after remove", errors)
                _assert_int(1, inventory.get_stacks().size(), "stack count after remove", errors)

                var copied_stacks: Array = inventory.get_stacks()
                copied_stacks[0]["quantity"] = 999
                _assert_int(4, inventory.get_quantity("potion"), "get_stacks should return copies", errors)

                _assert_error(inventory.add_item("potion", 0), "quantity", "zero quantity add", errors)
                _assert_error(inventory.add_item(" ", 1), "item_id", "empty item_id add", errors)
                _assert_error(inventory.add_item("missing", 1), "Unknown item_id", "unknown item add", errors)

                var no_database_inventory = InventoryData.new()
                _assert_error(no_database_inventory.add_item("potion", 1), "database must be assigned", "missing database", errors)

                var invalid_database_inventory = InventoryData.new()
                invalid_database_inventory.database = Resource.new()
                _assert_error(invalid_database_inventory.add_item("potion", 1), "InventoryItemDatabase", "plain Resource database", errors)

                return {"ok": errors.is_empty(), "errors": errors}


            func _make_database():
                var potion = InventoryItemDefinitionData.new()
                potion.item_id = &"potion"
                potion.display_name = "Potion"
                potion.max_stack = 5

                var key = InventoryItemDefinitionData.new()
                key.item_id = &"key"
                key.display_name = "Key"
                key.max_stack = 1

                var database = InventoryItemDatabaseData.new()
                database.items.append(potion)
                database.items.append(key)
                return database


            func _assert_error(result: Dictionary, expected_text: String, label: String, errors: Array[String]) -> void:
                _assert_bool(not bool(result.get("ok", true)), "%s should fail" % label, errors)
                _assert_contains(result.get("errors", []), expected_text, label, errors)


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %d, got %d" % [label, expected, actual])


            func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        return
                errors.append("%s: missing %s in %s" % [label, needle, str(messages)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "inventory_stack_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/inventory_stack_probe.gd" id="1_probe_script"]

            [node name="InventoryStackProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )


def _write_duplicate_load_probe(project: Path) -> None:
    (project / "scripts" / "duplicate_load_participant.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            @export var save_id: StringName = &"dup"

            var value: int = 0


            func _enter_tree() -> void:
                add_to_group(&"save_participants")


            func get_save_id() -> String:
                return String(save_id)


            func save_state() -> Dictionary:
                return {"value": value}


            func load_state(data: Dictionary) -> void:
                value = int(data.get("value", 0))
            """
        ),
        encoding="utf-8",
    )
    (project / "scripts" / "duplicate_load_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            @onready var actor_a: Node = $ActorA
            @onready var actor_b: Node = $ActorB


            func run_duplicate_load() -> Dictionary:
                var save_service: Node = get_node("/root/SaveService")
                actor_a.set("value", 0)
                actor_b.set("value", 0)
                DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("user://saves"))
                var file := FileAccess.open("user://saves/duplicate_slot.json", FileAccess.WRITE)
                file.store_string(JSON.stringify({
                    "schema_version": 1,
                    "module_version": "0.1.0",
                    "saved_at": "2026-06-08T00:00:00Z",
                    "scene": "res://scenes/duplicate_load_probe.tscn",
                    "participants": {"dup": {"value": 5}},
                }))
                file = null
                var load_result: Dictionary = save_service.call("load_slot", "duplicate_slot")
                return {
                    "load_result": load_result,
                    "a_value": int(actor_a.get("value")),
                    "b_value": int(actor_b.get("value")),
                }
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "duplicate_load_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=3 format=3]

            [ext_resource type="Script" path="res://scripts/duplicate_load_probe.gd" id="1_root"]
            [ext_resource type="Script" path="res://scripts/duplicate_load_participant.gd" id="2_actor"]

            [node name="DuplicateLoadProbe" type="Node"]
            script = ExtResource("1_root")

            [node name="ActorA" type="Node" parent="."]
            script = ExtResource("2_actor")
            save_id = &"dup"

            [node name="ActorB" type="Node" parent="."]
            script = ExtResource("2_actor")
            save_id = &"dup"
            """
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()

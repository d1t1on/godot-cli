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

    def test_repository_state_machine_module_is_discoverable(self) -> None:
        modules = list_modules()
        state_machine = next(module for module in modules if module["name"] == "state_machine")
        self.assertEqual(state_machine["version"], "0.1.0")
        self.assertEqual(state_machine["godot_version"], ">=4.6")
        self.assertEqual(state_machine["autoloads"], [])

    def test_repository_interaction_module_is_discoverable(self) -> None:
        modules = list_modules()
        interaction = next(module for module in modules if module["name"] == "interaction")
        self.assertEqual(interaction["version"], "0.1.0")
        self.assertEqual(interaction["godot_version"], ">=4.6")
        self.assertEqual(interaction["autoloads"], [])

    def test_repository_effects_module_is_discoverable(self) -> None:
        modules = list_modules()
        effects = next(module for module in modules if module["name"] == "effects")
        self.assertEqual(effects["version"], "0.1.0")
        self.assertEqual(effects["godot_version"], ">=4.6")
        self.assertEqual(effects["autoloads"], [])

    def test_repository_abilities_module_is_discoverable(self) -> None:
        modules = list_modules()
        abilities = next(module for module in modules if module["name"] == "abilities")
        self.assertEqual(abilities["version"], "0.1.0")
        self.assertEqual(abilities["godot_version"], ">=4.6")
        self.assertEqual(abilities["autoloads"], [])

    def test_repository_stats_module_is_discoverable(self) -> None:
        modules = list_modules()
        stats = next(module for module in modules if module["name"] == "stats")
        self.assertEqual(stats["version"], "0.1.0")
        self.assertEqual(stats["godot_version"], ">=4.6")
        self.assertEqual(stats["autoloads"], [])
        self.assertIn("demo", stats)

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

    def test_add_state_machine_module_copies_files_without_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "state_machine")

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "state_machine")
            self.assertEqual(report["autoloads"], [])
            self.assertTrue((project / "addons" / "state_machine" / "state_machine.gd").exists())
            self.assertTrue((project / "addons" / "state_machine" / "state.gd").exists())
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertNotIn("StateMachineService", project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertIn("res://addons/state_machine/state_machine.gd", copied_targets)

    def test_add_effects_module_copies_files_without_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "effects")

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "effects")
            self.assertEqual(report["autoloads"], [])
            self.assertTrue((project / "addons" / "effects" / "effect_container.gd").exists())
            self.assertTrue((project / "addons" / "effects" / "effect_definition.gd").exists())
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertNotIn("EffectService", project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertIn("res://addons/effects/effect_container.gd", copied_targets)

    def test_add_abilities_module_copies_files_without_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "abilities")

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "abilities")
            self.assertEqual(report["autoloads"], [])
            expected_scripts = {
                "ability_constants.gd",
                "ability_result.gd",
                "ability_definition.gd",
                "ability_database.gd",
                "ability_container.gd",
            }
            for script_name in expected_scripts:
                self.assertTrue((project / "addons" / "abilities" / script_name).exists(), script_name)
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertNotIn("AbilityService", project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertTrue(
                {f"res://addons/abilities/{script_name}" for script_name in expected_scripts}.issubset(copied_targets),
                copied_targets,
            )

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

    def test_add_state_machine_module_with_demo_copies_demo_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "state_machine", demo=True)

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["demo"])
            self.assertTrue((project / "scenes" / "state_machine_demo" / "state_machine_demo.tscn").exists())
            self.assertTrue((project / "scripts" / "state_machine_demo" / "state_machine_demo.gd").exists())
            self.assertTrue((project / "tests" / "state_machine_demo" / "test_state_machine_demo.py").exists())

    def test_add_interaction_module_copies_files_without_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "interaction")

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "interaction")
            self.assertEqual(report["autoloads"], [])
            self.assertTrue((project / "addons" / "interaction" / "interactable.gd").exists())
            self.assertTrue((project / "addons" / "interaction" / "interactor_2d.gd").exists())
            self.assertTrue((project / "addons" / "interaction" / "interactor_3d.gd").exists())
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertNotIn("InteractionService", project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertIn("res://addons/interaction/interactable.gd", copied_targets)

    def test_add_stats_module_copies_files_without_autoload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "stats")

            self.assertTrue(report["ok"], report)
            self.assertFalse(report["demo"])
            self.assertEqual(report["module"], "stats")
            self.assertEqual(report["autoloads"], [])
            expected_scripts = {
                "stat_constants.gd",
                "stat_result.gd",
                "stat_definition.gd",
                "stat_database.gd",
                "stat_container.gd",
            }
            for script_name in expected_scripts:
                self.assertTrue((project / "addons" / "stats" / script_name).exists(), script_name)
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertNotIn("StatsService", project_text)
            copied_targets = {entry["target"] for entry in report["copied"]}
            self.assertTrue(
                {f"res://addons/stats/{script_name}" for script_name in expected_scripts}.issubset(copied_targets),
                copied_targets,
            )

    def test_add_interaction_module_with_demo_copies_demo_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "interaction", demo=True)

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["demo"])
            self.assertTrue((project / "scenes" / "interaction_demo" / "interaction_demo.tscn").exists())
            self.assertTrue((project / "scripts" / "interaction_demo" / "interaction_demo.gd").exists())
            self.assertTrue((project / "scripts" / "interaction_demo" / "interaction_demo_pickup.gd").exists())
            self.assertTrue((project / "scripts" / "interaction_demo" / "interaction_demo_door.gd").exists())
            self.assertTrue((project / "tests" / "interaction_demo" / "test_interaction_demo.py").exists())

    def test_add_effects_module_with_demo_copies_demo_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "effects", demo=True)

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["demo"])
            self.assertTrue((project / "scenes" / "effects_demo" / "effects_demo.tscn").exists())
            self.assertTrue((project / "scripts" / "effects_demo" / "effects_demo.gd").exists())
            self.assertTrue((project / "resources" / "effects_demo" / "effect_database.tres").exists())
            self.assertTrue((project / "tests" / "effects_demo" / "test_effects_demo.py").exists())

    def test_add_stats_module_with_demo_copies_demo_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = _write_project(root / "project")

            report = add_module(project, "stats", demo=True)

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["demo"])
            self.assertTrue((project / "scenes" / "stats_demo" / "stats_demo.tscn").exists())
            self.assertTrue((project / "scripts" / "stats_demo" / "stats_demo.gd").exists())
            self.assertTrue((project / "resources" / "stats_demo" / "stat_database.tres").exists())
            self.assertTrue((project / "tests" / "stats_demo" / "test_stats_demo.py").exists())

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

    def test_packaged_state_machine_module_mirror_exists(self) -> None:
        bundled_root = default_module_roots()[1]
        manifest = load_module_manifest("state_machine", module_root=bundled_root)
        self.assertEqual(manifest["name"], "state_machine")
        self.assertEqual(manifest["autoloads"], [])
        self.assertTrue(
            (bundled_root / "state_machine" / "addons" / "state_machine" / "state_machine.gd").exists()
        )

    def test_packaged_interaction_module_mirror_exists(self) -> None:
        bundled_root = default_module_roots()[1]
        manifest = load_module_manifest("interaction", module_root=bundled_root)
        self.assertEqual(manifest["name"], "interaction")
        self.assertEqual(manifest["autoloads"], [])
        self.assertTrue((bundled_root / "interaction" / "addons" / "interaction" / "interactable.gd").exists())

    def test_packaged_effects_module_mirror_exists(self) -> None:
        bundled_root = default_module_roots()[1]
        manifest = load_module_manifest("effects", module_root=bundled_root)
        self.assertEqual(manifest["name"], "effects")
        self.assertEqual(manifest["autoloads"], [])
        self.assertTrue((bundled_root / "effects" / "addons" / "effects" / "effect_container.gd").exists())

    def test_packaged_stats_module_mirror_exists(self) -> None:
        bundled_root = default_module_roots()[1]
        manifest = load_module_manifest("stats", module_root=bundled_root)
        self.assertEqual(manifest["name"], "stats")
        self.assertEqual(manifest["autoloads"], [])
        self.assertTrue((bundled_root / "stats" / "addons" / "stats" / "stat_container.gd").exists())

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
        self.assertIn('"bundled_gameplay_modules/state_machine/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/state_machine/addons/state_machine/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/state_machine/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/state_machine/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/state_machine/tests/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/interaction/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/interaction/addons/interaction/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/interaction/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/interaction/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/interaction/tests/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/effects/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/effects/addons/effects/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/effects/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/effects/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/effects/demo/resources/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/effects/tests/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/addons/stats/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/demo/scenes/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/demo/scripts/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/demo/resources/*"', pyproject)
        self.assertIn('"bundled_gameplay_modules/stats/tests/*"', pyproject)

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

    def test_source_and_packaged_state_machine_trees_are_identical(self) -> None:
        source_root, bundled_root = default_module_roots()
        source = source_root / "state_machine"
        bundled = bundled_root / "state_machine"

        source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
        bundled_files = sorted(path.relative_to(bundled) for path in bundled.rglob("*") if path.is_file())

        self.assertEqual([path.as_posix() for path in source_files], [path.as_posix() for path in bundled_files])
        for relative_path in source_files:
            self.assertEqual(
                (source / relative_path).read_bytes(),
                (bundled / relative_path).read_bytes(),
                relative_path.as_posix(),
            )

    def test_source_and_packaged_interaction_trees_are_identical(self) -> None:
        source_root, bundled_root = default_module_roots()
        source = source_root / "interaction"
        bundled = bundled_root / "interaction"

        source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
        bundled_files = sorted(path.relative_to(bundled) for path in bundled.rglob("*") if path.is_file())

        self.assertEqual([path.as_posix() for path in source_files], [path.as_posix() for path in bundled_files])
        for relative_path in source_files:
            self.assertEqual(
                (source / relative_path).read_bytes(),
                (bundled / relative_path).read_bytes(),
                relative_path.as_posix(),
            )

    def test_source_and_packaged_effects_trees_are_identical(self) -> None:
        source_root, bundled_root = default_module_roots()
        source = source_root / "effects"
        bundled = bundled_root / "effects"

        source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
        bundled_files = sorted(path.relative_to(bundled) for path in bundled.rglob("*") if path.is_file())

        self.assertEqual([path.as_posix() for path in source_files], [path.as_posix() for path in bundled_files])
        for relative_path in source_files:
            self.assertEqual(
                (source / relative_path).read_bytes(),
                (bundled / relative_path).read_bytes(),
                relative_path.as_posix(),
            )

    def test_source_and_packaged_stats_trees_are_identical(self) -> None:
        source_root, bundled_root = default_module_roots()
        source = source_root / "stats"
        bundled = bundled_root / "stats"
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

    def test_inventory_docs_exist_for_humans_and_agents(self) -> None:
        source_root = default_module_roots()[0] / "inventory"
        bundled_root = default_module_roots()[1] / "inventory"
        for root in (source_root, bundled_root):
            readme = (root / "README.md").read_text(encoding="utf-8")
            agent = (root / "AGENT.md").read_text(encoding="utf-8")
            self.assertIn("godot-playwright module add /path/to/project inventory", readme)
            self.assertIn("Inventory.add_item", readme)
            self.assertIn("InventoryItemDatabase", readme)
            self.assertIn("save_load", readme)
            self.assertIn("item_id", agent)
            self.assertIn("Resource", agent)
            self.assertIn("SaveService", agent)

    def test_state_machine_docs_exist_for_humans_and_agents(self) -> None:
        source_root = default_module_roots()[0] / "state_machine"
        bundled_root = default_module_roots()[1] / "state_machine"
        for root in (source_root, bundled_root):
            readme = (root / "README.md").read_text(encoding="utf-8")
            agent = (root / "AGENT.md").read_text(encoding="utf-8")
            self.assertIn("godot-playwright module add /path/to/project state_machine", readme)
            self.assertIn("StateMachine.transition_to", readme)
            self.assertIn("state_id", agent)
            self.assertIn("request_transition", agent)
            self.assertIn("save_load", agent)

    def test_interaction_docs_exist_for_humans_and_agents(self) -> None:
        source_root = default_module_roots()[0] / "interaction"
        bundled_root = default_module_roots()[1] / "interaction"
        for root in (source_root, bundled_root):
            readme = (root / "README.md").read_text(encoding="utf-8")
            agent = (root / "AGENT.md").read_text(encoding="utf-8")
            self.assertIn("godot-playwright module add /path/to/project interaction", readme)
            self.assertIn("Interactor2D", readme)
            self.assertIn("Interactor3D", readme)
            self.assertIn("Interactable.interact", readme)
            self.assertIn("get_state", readme)
            self.assertIn("pickups", agent)
            self.assertIn("interaction_id", agent)
            self.assertIn("SaveService", agent)

    def test_stats_docs_exist_for_humans_and_agents(self) -> None:
        source_root = default_module_roots()[0] / "stats"
        bundled_root = default_module_roots()[1] / "stats"
        for root in (source_root, bundled_root):
            readme = (root / "README.md").read_text(encoding="utf-8")
            agent = (root / "AGENT.md").read_text(encoding="utf-8")
            self.assertIn("godot-playwright module add /path/to/project stats", readme)
            self.assertIn("godot-playwright module add /path/to/project stats --demo", readme)
            self.assertIn("StatContainer.set_value", readme)
            self.assertIn("StatContainer.apply_state(data: Dictionary)", readme)
            self.assertIn("StatDefinition", readme)
            self.assertIn("pool", readme)
            self.assertIn("stat_changed", readme)
            self.assertIn("save_load", readme)
            self.assertIn("save_participants", readme)
            self.assertIn("before the node enters the tree", readme)
            self.assertIn("godot-playwright check-scripts", readme)
            self.assertIn("stat_id", agent)
            self.assertIn("Resource", agent)
            self.assertIn("SaveService", agent)
            self.assertIn("combat", agent)
            self.assertIn("Do not use this module as a combat system", agent)
            self.assertIn("save_participants", agent)
            self.assertIn("before the node enters the tree", agent)
            self.assertIn("godot-playwright validate", agent)

    def test_readme_gameplay_module_commands_include_current_modules(self) -> None:
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

        self.assertIn("godot-playwright module add /tmp/agent-game inventory --demo", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game interaction", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game interaction --demo", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game effects", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game effects --demo", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game stats", readme)
        self.assertIn("godot-playwright module add /tmp/agent-game stats --demo", readme)

    def test_effects_docs_exist_for_humans_and_agents(self) -> None:
        source_root = default_module_roots()[0] / "effects"
        bundled_root = default_module_roots()[1] / "effects"
        for root in (source_root, bundled_root):
            readme = (root / "README.md").read_text(encoding="utf-8")
            agent = (root / "AGENT.md").read_text(encoding="utf-8")
            self.assertIn("godot-playwright module add /path/to/project effects", readme)
            self.assertIn("EffectContainer.add_effect", readme)
            self.assertIn("EffectDefinition", readme)
            self.assertIn("save_load", readme)
            self.assertIn("effect_id", agent)
            self.assertIn("auto_update", agent)
            self.assertIn("stats", agent)

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

    def test_effects_source_defines_resource_helpers(self) -> None:
        source_root = default_module_roots()[0]
        effects_root = source_root / "effects" / "addons" / "effects"
        definition = (effects_root / "effect_definition.gd").read_text(encoding="utf-8")
        database = (effects_root / "effect_database.gd").read_text(encoding="utf-8")
        result = (effects_root / "effect_result.gd").read_text(encoding="utf-8")
        constants = (effects_root / "effect_constants.gd").read_text(encoding="utf-8")

        self.assertIn("class_name EffectDefinition", definition)
        self.assertIn("@export var effect_id: StringName", definition)
        self.assertIn("@export var tags: Array[StringName] = []", definition)
        self.assertIn('@export_enum("refresh", "stack", "ignore") var stack_mode: String = "refresh"', definition)
        self.assertIn("class_name EffectDatabase", database)
        self.assertIn("func get_effect(effect_id: String) -> Resource", database)
        self.assertIn("func validate() -> Dictionary", database)
        self.assertIn("class_name EffectResult", result)
        self.assertIn("static func add_event", result)
        self.assertIn('const STACK_REFRESH: String = "refresh"', constants)

    def test_abilities_source_defines_resource_helpers(self) -> None:
        source_root = default_module_roots()[0]
        abilities_root = source_root / "abilities" / "addons" / "abilities"
        definition = (abilities_root / "ability_definition.gd").read_text(encoding="utf-8")
        database = (abilities_root / "ability_database.gd").read_text(encoding="utf-8")
        result = (abilities_root / "ability_result.gd").read_text(encoding="utf-8")
        constants = (abilities_root / "ability_constants.gd").read_text(encoding="utf-8")

        self.assertIn("class_name AbilityDefinition", definition)
        self.assertIn("@export var ability_id: StringName", definition)
        self.assertIn("@export var display_name: String", definition)
        self.assertIn("@export_multiline var description: String", definition)
        self.assertIn("@export var tags: Array[StringName] = []", definition)
        self.assertIn("@export var cooldown: float = 0.0", definition)
        self.assertIn("@export_range(0, 999, 1) var max_charges: int = 1", definition)
        self.assertIn("@export_range(0, 999, 1) var initial_charges: int = 1", definition)
        self.assertIn("@export var charge_recovery_time: float = 0.0", definition)
        self.assertIn("@export var enabled_by_default: bool = true", definition)
        self.assertIn("@export var costs: Dictionary = {}", definition)
        self.assertIn("@export var default_data: Dictionary = {}", definition)
        self.assertIn("class_name AbilityDatabase", database)
        self.assertIn("func get_ability(ability_id: String) -> Resource", database)
        self.assertIn("func has_ability(ability_id: String) -> bool", database)
        self.assertIn("func get_ability_ids() -> Array[String]", database)
        self.assertIn("func validate() -> Dictionary", database)
        self.assertIn("abilities[%d] is null", database)
        self.assertIn("must be an AbilityDefinition", database)
        self.assertIn("ability_id must be non-empty", database)
        self.assertIn("Duplicate ability_id", database)
        self.assertIn("_is_json_compatible", database)
        self.assertIn("class_name AbilityResult", result)
        self.assertIn('"ability_id": ability_id', result)
        self.assertIn('"costs": {}', result)
        self.assertIn('"context": {}', result)
        self.assertIn("static func add_event", result)
        self.assertIn("static func add_warning", result)
        self.assertIn("static func add_error", result)
        self.assertIn("const SCHEMA_VERSION: int = 1", constants)

    def test_abilities_source_defines_container_api(self) -> None:
        source_root = default_module_roots()[0]
        container = (source_root / "abilities" / "addons" / "abilities" / "ability_container.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("class_name AbilityContainer", container)
        self.assertIn("@export var database: Resource", container)
        self.assertIn("@export var save_id: StringName", container)
        self.assertIn("@export var initialize_on_ready: bool = true", container)
        self.assertIn("@export var auto_update: bool = true", container)
        self.assertIn("signal ability_activated", container)
        self.assertIn("signal ability_failed", container)
        self.assertIn("signal ability_enabled_changed", container)
        self.assertIn("signal ability_cooldown_ready", container)
        self.assertIn("signal ability_charge_recovered", container)
        self.assertIn("signal abilities_changed", container)
        self.assertIn("func initialize_abilities(reset: bool = false) -> Dictionary", container)
        self.assertIn("func has_ability(ability_id: String) -> bool", container)
        self.assertIn("func can_activate(ability_id: String, context: Dictionary = {}) -> Dictionary", container)
        self.assertIn("func activate(ability_id: String, context: Dictionary = {}) -> Dictionary", container)
        self.assertIn("func set_enabled(ability_id: String, enabled: bool) -> Dictionary", container)
        self.assertIn("func is_enabled(ability_id: String) -> bool", container)
        self.assertIn("func get_ability_runtime(ability_id: String) -> Dictionary", container)
        self.assertIn("func get_abilities() -> Array", container)
        self.assertIn("func update_abilities(delta: float) -> Array[Dictionary]", container)
        self.assertIn("func clear_runtime_state() -> void", container)
        self.assertIn("func get_state() -> Dictionary", container)
        self.assertIn("func apply_state(data: Dictionary) -> Dictionary", container)
        self.assertIn("func save_state() -> Dictionary", container)
        self.assertIn("func load_state(data: Dictionary) -> void", container)
        self.assertIn("AbilityConstantsData.SCHEMA_VERSION", container)
        self.assertIn("_parse_integer_field", container)

    def test_stats_source_defines_resource_helpers(self) -> None:
        source_root = default_module_roots()[0]
        stats_root = source_root / "stats" / "addons" / "stats"
        definition = (stats_root / "stat_definition.gd").read_text(encoding="utf-8")
        database = (stats_root / "stat_database.gd").read_text(encoding="utf-8")
        result = (stats_root / "stat_result.gd").read_text(encoding="utf-8")

        self.assertIn("class_name StatDefinition", definition)
        self.assertIn("@export var stat_id: StringName", definition)
        self.assertIn("@export var display_name: String", definition)
        self.assertIn("@export_multiline var description: String", definition)
        self.assertIn("@export var tags: Array[StringName] = []", definition)
        self.assertIn("@export var default_base_value: float = 0.0", definition)
        self.assertIn("@export var default_current_value: float = 0.0", definition)
        self.assertIn("@export var clamp_min: bool = true", definition)
        self.assertIn("@export var min_value: float = 0.0", definition)
        self.assertIn("@export var clamp_max: bool = false", definition)
        self.assertIn("@export var max_value: float = 100.0", definition)
        self.assertIn("@export var is_pool: bool = false", definition)
        self.assertIn("class_name StatDatabase", database)
        self.assertIn('StatDefinitionData := preload("res://addons/stats/stat_definition.gd")', database)
        self.assertIn('StatResultData := preload("res://addons/stats/stat_result.gd")', database)
        self.assertIn("@export var stats: Array[Resource] = []", database)
        self.assertIn("func get_stat(stat_id: String) -> Resource", database)
        self.assertIn("func has_stat(stat_id: String) -> bool", database)
        self.assertIn("func get_stat_ids() -> Array[String]", database)
        self.assertIn("func validate() -> Dictionary", database)
        self.assertIn("stats[%d] is null", database)
        self.assertIn("must be a StatDefinition", database)
        self.assertIn("stat_id must be non-empty", database)
        self.assertIn("must not contain leading or trailing whitespace", database)
        self.assertIn("Duplicate stat_id", database)
        self.assertIn("ids.append(raw_stat_id)", database)
        self.assertIn("_is_finite_number", database)
        self.assertIn("default_base_value must be finite", database)
        self.assertIn("default_current_value must be finite", database)
        self.assertIn("min_value must be finite", database)
        self.assertIn("max_value must be finite", database)
        self.assertIn("min_value must be <= max_value", database)
        self.assertIn("class_name StatResult", result)
        self.assertIn('"ok": ok', result)
        self.assertIn('"stat_id": stat_id', result)
        self.assertIn('"previous_value": 0.0', result)
        self.assertIn('"current_value": 0.0', result)
        self.assertIn('"previous_base_value": 0.0', result)
        self.assertIn('"base_value": 0.0', result)
        self.assertIn('"requested_value": 0.0', result)
        self.assertIn('"delta": 0.0', result)
        self.assertIn('"clamped": false', result)
        self.assertIn("static func add_event", result)
        self.assertIn("static func add_warning", result)
        self.assertIn("static func add_error", result)
        self.assertIn('"events": []', result)
        self.assertIn('"warnings": []', result)
        self.assertIn('"errors": []', result)

    def test_stats_source_defines_container_api(self) -> None:
        source_root = default_module_roots()[0]
        container = (source_root / "stats" / "addons" / "stats" / "stat_container.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("class_name StatContainer", container)
        self.assertIn("@export var database: Resource", container)
        self.assertIn("@export var save_id: StringName", container)
        self.assertIn("@export var initialize_on_ready: bool = true", container)
        self.assertIn("signal stat_changed", container)
        self.assertIn("signal base_stat_changed", container)
        self.assertIn("signal stat_depleted", container)
        self.assertIn("signal stat_filled", container)
        self.assertIn("signal stats_changed", container)
        self.assertIn("func initialize_stats(reset: bool = false) -> Dictionary", container)
        self.assertIn("func has_stat(stat_id: String) -> bool", container)
        self.assertIn("func get_value(stat_id: String) -> float", container)
        self.assertIn("func get_base_value(stat_id: String) -> float", container)
        self.assertIn("func get_stat(stat_id: String) -> Dictionary", container)
        self.assertIn("func get_stats() -> Array", container)
        self.assertIn("func set_value(stat_id: String, value: float) -> Dictionary", container)
        self.assertIn("func modify_value(stat_id: String, delta: float) -> Dictionary", container)
        self.assertIn("func set_base_value(stat_id: String, value: float) -> Dictionary", container)
        self.assertIn("func modify_base_value(stat_id: String, delta: float) -> Dictionary", container)
        self.assertIn("func get_state() -> Dictionary", container)
        self.assertIn("func apply_state(data: Dictionary) -> Dictionary", container)
        self.assertIn("func get_save_id() -> String", container)
        self.assertIn("func save_state() -> Dictionary", container)
        self.assertIn("func load_state(data: Dictionary) -> void", container)
        self.assertIn("StatConstantsData.SCHEMA_VERSION", container)
        self.assertIn("is_pool", container)
        self.assertIn("clamped", container)

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

    def test_inventory_source_defines_state_and_save_api(self) -> None:
        source_root = default_module_roots()[0]
        inventory_source = (source_root / "inventory" / "addons" / "inventory" / "inventory.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("func get_state() -> Dictionary", inventory_source)
        self.assertIn("func apply_state(data: Dictionary) -> Dictionary", inventory_source)
        self.assertIn("func get_save_id() -> String", inventory_source)
        self.assertIn("func save_state() -> Dictionary", inventory_source)
        self.assertIn("func load_state(data: Dictionary) -> void", inventory_source)
        self.assertIn("InventoryConstantsData.SCHEMA_VERSION", inventory_source)
        self.assertIn("does not fit current capacity", inventory_source)

    def test_interaction_source_defines_core_api(self) -> None:
        source_root = default_module_roots()[0]
        interaction_root = source_root / "interaction" / "addons" / "interaction"
        interactable = (interaction_root / "interactable.gd").read_text(encoding="utf-8")
        interactor_2d = (interaction_root / "interactor_2d.gd").read_text(encoding="utf-8")
        interactor_3d = (interaction_root / "interactor_3d.gd").read_text(encoding="utf-8")
        result = (interaction_root / "interaction_result.gd").read_text(encoding="utf-8")

        self.assertIn("class_name Interactable", interactable)
        self.assertIn("@export var interaction_id: StringName", interactable)
        self.assertIn('prompt: String = "Interact"', interactable)
        self.assertIn("func can_interact(actor: Node, data: Dictionary = {}) -> bool", interactable)
        self.assertIn("func interact(actor: Node, data: Dictionary = {}) -> Dictionary", interactable)
        self.assertIn("func get_state() -> Dictionary", interactable)
        self.assertIn("func apply_state(data: Dictionary) -> Dictionary", interactable)
        self.assertIn("class_name Interactor2D", interactor_2d)
        self.assertIn("extends Area2D", interactor_2d)
        self.assertIn("class_name Interactor3D", interactor_3d)
        self.assertIn("extends Area3D", interactor_3d)
        self.assertIn("class_name InteractionResult", result)
        self.assertIn("static func add_error", result)

    def test_effects_source_defines_container_api(self) -> None:
        source_root = default_module_roots()[0]
        container_source = (source_root / "effects" / "addons" / "effects" / "effect_container.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("class_name EffectContainer", container_source)
        self.assertIn("@export var database: Resource", container_source)
        self.assertIn("@export var save_id: StringName", container_source)
        self.assertIn("@export var auto_update: bool = true", container_source)
        self.assertIn("signal effect_added", container_source)
        self.assertIn("func add_effect(effect_id: String, source: Node = null, stacks: int = 1, data: Dictionary = {}) -> Dictionary", container_source)
        self.assertIn("func remove_effect(effect_id: String, stacks: int = 0) -> Dictionary", container_source)
        self.assertIn("func update_effects(delta: float) -> Array[Dictionary]", container_source)
        self.assertIn("func get_state() -> Dictionary", container_source)
        self.assertIn("func apply_state(data: Dictionary) -> Dictionary", container_source)
        self.assertIn("func save_state() -> Dictionary", container_source)

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
class AbilitiesModuleGodotTests(unittest.TestCase):
    def test_ability_database_validation_runs_in_godot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Abilities Database Probe")
            add_module(project, "abilities")
            _write_abilities_database_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/abilities_database_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#AbilitiesDatabaseProbe").call("run_probe")

        self.assertTrue(result["ok"], result)

    def test_ability_container_runtime_runs_in_godot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Abilities Container Probe")
            add_module(project, "abilities")
            _write_abilities_container_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/abilities_container_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#AbilitiesContainerProbe").call("run_probe")

        self.assertTrue(result["ok"], result)


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class StatsModuleGodotTests(unittest.TestCase):
    def test_installed_stats_scripts_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Parse Probe")
            add_module(project, "stats")

            report = check_project_scripts(
                project,
                ["res://addons/stats"],
                artifacts_dir=root / "artifacts",
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_stats_database_validation_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Database Probe")
            add_module(project, "stats")
            _write_stats_database_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/stats_database_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StatsDatabaseProbe").call("run_probe")

        self.assertTrue(result["ok"], result)

    def test_stats_container_operations_run_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Container Probe")
            add_module(project, "stats")
            _write_stats_container_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/stats_container_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StatsContainerProbe").call("run_probe")

        self.assertTrue(result["ok"], result)

    def test_stats_container_review_regressions_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Container Review Probe")
            add_module(project, "stats")
            _write_stats_container_review_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/stats_container_review_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StatsContainerReviewProbe").call("run_probe")

        self.assertTrue(result["ok"], result)

    def test_installed_stats_demo_resources_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Resource Probe")
            add_module(project, "stats", demo=True)

            report = check_project_resources(
                project,
                ["res://scenes/stats_demo", "res://resources/stats_demo"],
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_stats_demo_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Runtime Probe")
            add_module(project, "stats", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/stats_demo/stats_demo.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StatsDemo").call("run_stats_demo")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["health_after_restore"], 40.0)
        self.assertEqual(result["move_speed_after_restore"], 12.0)
        self.assertFalse(result["missing_stat_ok"])
        self.assertFalse(result["save_load_checked"])

    def test_installed_stats_demo_test_runs_without_main_scene_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Demo Test Probe")
            add_module(project, "stats", demo=True)

            report = run_tests(
                project,
                [project / "tests" / "stats_demo"],
                artifacts_dir=root / "artifacts",
                trace="off",
                timeout=30,
            )

        self.assertEqual(report["failed"], 0, report["tests"])
        self.assertEqual(report["passed"], 1)

    def test_stats_demo_integrates_with_save_load_when_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Stats Save Load Probe")
            add_module(project, "save_load")
            add_module(project, "stats", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/stats_demo/stats_demo.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StatsDemo").call("run_stats_demo")

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["save_load_checked"], result)
        self.assertEqual(result["save_load_health"], 33.0)


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class InteractionSeedModuleGodotTests(unittest.TestCase):
    def test_installed_interaction_seed_demo_scene_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Interaction Seed Scene Probe")
            add_module(project, "interaction", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/interaction_demo/interaction_demo.tscn"',
                ),
                encoding="utf-8",
            )

            report = probe_project(project, frames=2, artifacts_dir=root / "artifacts")

        self.assertTrue(report["ok"], report["log_summary"]["tail"])

    def test_installed_interaction_seed_demo_test_runs_without_main_scene_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Interaction Seed Demo Test Probe")
            add_module(project, "interaction", demo=True)

            report = run_tests(
                project,
                [project / "tests" / "interaction_demo"],
                artifacts_dir=root / "artifacts",
                trace="off",
                timeout=30,
            )

        self.assertEqual(report["failed"], 0, report["tests"])
        self.assertEqual(report["passed"], 1)

    def test_interactable_state_and_default_interaction_run_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Interaction Interactable Probe")
            add_module(project, "interaction")
            _write_interactable_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/interactable_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#InteractableProbe").call("run_probe")

        self.assertTrue(result["ok"], result)

    def test_interactor_candidate_selection_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Interaction Interactor Probe")
            add_module(project, "interaction")
            _write_interactor_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/interactor_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#InteractorProbe").call("run_probe")

        self.assertTrue(result["ok"], result)

    def test_installed_interaction_scripts_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Interaction Parse Probe")
            add_module(project, "interaction", demo=True)

            report = check_project_scripts(
                project,
                ["res://addons/interaction", "res://scripts/interaction_demo"],
                artifacts_dir=root / "artifacts",
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_installed_interaction_demo_resources_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Interaction Resource Probe")
            add_module(project, "interaction", demo=True)

            report = check_project_resources(
                project,
                ["res://scenes/interaction_demo"],
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_interaction_demo_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Interaction Runtime Probe")
            add_module(project, "interaction", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/interaction_demo/interaction_demo.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#InteractionDemo").call("run_interaction_demo")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["best_interaction_id"], "high")
        self.assertEqual(result["disabled_best_interaction_id"], "low")
        self.assertTrue(result["pickup_picked_up"])
        self.assertTrue(result["door_opened"])
        self.assertFalse(result["no_candidate_ok"])

    def test_installed_interaction_demo_test_runs_without_main_scene_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Interaction Demo Test Probe")
            add_module(project, "interaction", demo=True)

            report = run_tests(
                project,
                [project / "tests" / "interaction_demo"],
                artifacts_dir=root / "artifacts",
                trace="off",
                timeout=30,
            )

        self.assertEqual(report["failed"], 0, report["tests"])
        self.assertEqual(report["passed"], 1)

@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class EffectsSeedModuleGodotTests(unittest.TestCase):
    def test_installed_effects_seed_demo_scene_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Effects Seed Scene Probe")
            add_module(project, "effects", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/effects_demo/effects_demo.tscn"',
                ),
                encoding="utf-8",
            )

            report = probe_project(project, frames=2, artifacts_dir=root / "artifacts")

        self.assertTrue(report["ok"], report["log_summary"]["tail"])


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

    def test_inventory_state_and_save_wrappers_run_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Inventory State Probe")
            add_module(project, "inventory")
            _write_inventory_state_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/inventory_state_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#InventoryStateProbe").call("run_probe")

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


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class InventoryModuleGodotTests(unittest.TestCase):
    def test_installed_inventory_scripts_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Inventory Parse Probe")
            add_module(project, "inventory", demo=True)

            report = check_project_scripts(
                project,
                ["res://addons/inventory", "res://scripts/inventory_demo"],
                artifacts_dir=root / "artifacts",
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_installed_inventory_demo_resources_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Inventory Resource Probe")
            add_module(project, "inventory", demo=True)

            report = check_project_resources(
                project,
                ["res://scenes/inventory_demo", "res://resources/inventory_demo"],
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_inventory_demo_round_trip_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Inventory Runtime Probe")
            add_module(project, "inventory", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/inventory_demo/inventory_demo.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#InventoryDemo").call("run_inventory_demo")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["potion_quantity"], 2)
        self.assertEqual(result["key_quantity"], 1)
        self.assertEqual(result["failed_key_add_ok"], False)
        self.assertEqual(result["state_round_trip_quantity"], 2)
        self.assertFalse(result["save_load_checked"])

    def test_installed_inventory_demo_test_runs_without_main_scene_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Inventory Demo Test Probe")
            add_module(project, "inventory", demo=True)

            report = run_tests(
                project,
                [project / "tests" / "inventory_demo"],
                artifacts_dir=root / "artifacts",
                trace="off",
                timeout=30,
            )

        self.assertEqual(report["failed"], 0, report["tests"])
        self.assertEqual(report["passed"], 1)

    def test_inventory_demo_integrates_with_save_load_when_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Inventory Save Load Probe")
            add_module(project, "save_load")
            add_module(project, "inventory", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/inventory_demo/inventory_demo.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#InventoryDemo").call("run_inventory_demo")

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["save_load_checked"], result)
        self.assertEqual(result["save_load_coin_quantity"], 3)
        self.assertEqual(result["potion_quantity"], 2)
        self.assertEqual(result["key_quantity"], 1)
        self.assertEqual(result["state_round_trip_quantity"], 2)


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class EffectsModuleGodotTests(unittest.TestCase):
    def test_effect_database_validation_handles_invalid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Effects Database Probe")
            add_module(project, "effects")
            _write_effect_database_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/effect_database_probe.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#EffectDatabaseProbe").call("run_probe")

        self.assertTrue(result["ok"], result)

    def test_effect_container_runtime_probe_validates_core_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Effects Runtime Probe")
            add_module(project, "effects")
            _write_effect_container_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/effect_container_probe.tscn"',
                ),
                encoding="utf-8",
            )

            resource_report = check_project_resources(project, ["res://scenes/effect_container_probe.tscn"])
            self.assertTrue(resource_report["ok"], resource_report["diagnostics"])

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#EffectContainerProbe").call("run_probe")

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["add_haste"]["ok"], result["add_haste"])
        self.assertEqual(result["haste_stacks"], 1)
        self.assertEqual(result["poison_stacks"], 3)
        self.assertGreaterEqual(result["tick_count"], 2)
        self.assertFalse(result["has_haste_after_expire"])
        self.assertTrue(result["has_shielded_after_update"])
        self.assertEqual(result["round_trip_poison_stacks"], 2)
        self.assertFalse(result["unknown_result"]["ok"], result["unknown_result"])
        self.assertFalse(result["negative_delta_event"]["ok"], result["negative_delta_event"])
        self.assertTrue(result["float_schema_result"]["ok"], result["float_schema_result"])
        self.assertFalse(result["timed_permanent_state"]["ok"], result["timed_permanent_state"])
        self.assertFalse(result["permanent_timed_state"]["ok"], result["permanent_timed_state"])
        self.assertFalse(result["too_long_timed_state"]["ok"], result["too_long_timed_state"])

    def test_installed_effects_scripts_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Effects Parse Probe")
            add_module(project, "effects", demo=True)

            report = check_project_scripts(
                project,
                ["res://addons/effects", "res://scripts/effects_demo"],
                artifacts_dir=root / "artifacts",
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_installed_effects_demo_resources_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Effects Resource Probe")
            add_module(project, "effects", demo=True)

            report = check_project_resources(
                project,
                ["res://scenes/effects_demo", "res://resources/effects_demo"],
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_effects_demo_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Effects Demo Probe")
            add_module(project, "effects", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/effects_demo/effects_demo.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#EffectsDemo").call("run_effects_demo")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["poison_stack_count"], 3)
        self.assertGreaterEqual(result["poison_tick_count"], 2)
        self.assertFalse(result["has_haste_after_expire"])
        self.assertTrue(result["has_shielded_after_update"])
        self.assertFalse(result["missing_database_result"]["ok"], result["missing_database_result"])
        self.assertFalse(result["malformed_state_result"]["ok"], result["malformed_state_result"])
        self.assertFalse(result["save_load_checked"])

    def test_installed_effects_demo_test_runs_without_main_scene_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Effects Demo Test Probe")
            add_module(project, "effects", demo=True)

            report = run_tests(
                project,
                [project / "tests" / "effects_demo"],
                artifacts_dir=root / "artifacts",
                trace="off",
                timeout=30,
            )

        self.assertEqual(report["failed"], 0, report["tests"])
        self.assertEqual(report["passed"], 1)

    def test_effects_demo_integrates_with_save_load_when_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Effects Save Load Probe")
            add_module(project, "save_load")
            add_module(project, "effects", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/effects_demo/effects_demo.tscn"',
                ),
                encoding="utf-8",
            )

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#EffectsDemo").call("run_effects_demo")

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["save_load_checked"], result)
        self.assertEqual(result["save_load_poison_stacks"], 2)


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class StateMachineModuleGodotTests(unittest.TestCase):
    def test_installed_state_machine_scripts_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="State Machine Parse Probe")
            add_module(project, "state_machine")

            report = check_project_scripts(
                project,
                ["res://addons/state_machine"],
                artifacts_dir=root / "artifacts",
            )

        self.assertTrue(report["ok"], report["diagnostics"])

    def test_state_machine_runtime_probe_validates_core_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="State Machine Runtime Probe")
            add_module(project, "state_machine")
            _write_state_machine_runtime_probe(project)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/state_machine_probe.tscn"',
                ),
                encoding="utf-8",
            )

            resource_report = check_project_resources(project, ["res://scenes/state_machine_probe.tscn"])
            self.assertTrue(resource_report["ok"], resource_report["diagnostics"])

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StateMachineProbe").call("run_state_machine_probe")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["initial_state"], "idle")
        self.assertEqual(result["state_ids"], ["idle", "move", "attack", "forbidden", "reentrant"])
        self.assertTrue(result["move_result"]["ok"], result["move_result"])
        self.assertTrue(result["attack_result"]["ok"], result["attack_result"])
        self.assertFalse(result["forbidden_result"]["ok"], result["forbidden_result"])
        self.assertFalse(result["guard_reentrant_result"]["ok"], result["guard_reentrant_result"])
        self.assertIn("StateMachine is already transitioning", result["guard_reentrant_result"]["errors"])
        self.assertFalse(result["reentrant_result"]["ok"], result["reentrant_result"])
        self.assertFalse(result["duplicate_result"]["ok"], result["duplicate_result"])
        self.assertIn("Duplicate state_id: dup", result["duplicate_result"]["errors"])
        self.assertTrue(result["restore_result"]["ok"], result["restore_result"])
        self.assertEqual(result["restored_state"], "attack")
        self.assertEqual(result["snapshot"]["current_state_id"], "attack")
        self.assertEqual(result["snapshot"]["schema_version"], 1)
        self.assertEqual(result["transition_history"], ["idle>move", "move>attack", "attack>idle", "idle>attack"])

    def test_state_machine_demo_runs_in_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="State Machine Demo Probe")
            add_module(project, "state_machine", demo=True)
            project_file = project / "project.godot"
            project_file.write_text(
                project_file.read_text(encoding="utf-8").replace(
                    'run/main_scene="res://scenes/main.tscn"',
                    'run/main_scene="res://scenes/state_machine_demo/state_machine_demo.tscn"',
                ),
                encoding="utf-8",
            )

            resource_report = check_project_resources(project, ["res://scenes/state_machine_demo"])
            self.assertTrue(resource_report["ok"], resource_report["diagnostics"])

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                result = godot.locator("#StateMachineDemo").call("run_state_machine_demo")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["initial_state"], "idle")
        self.assertEqual(result["restored_state"], "attack")
        self.assertFalse(result["forbidden_result"]["ok"], result["forbidden_result"])
        self.assertEqual(result["transition_history"], ["idle>move", "move>attack", "attack>idle", "idle>attack"])

    def test_installed_state_machine_demo_test_runs_without_main_scene_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="State Machine Demo Test Probe")
            add_module(project, "state_machine", demo=True)

            report = run_tests(
                project,
                [project / "tests" / "state_machine_demo"],
                artifacts_dir=root / "artifacts",
                trace="off",
                timeout=30,
            )

        self.assertEqual(report["failed"], 0, report["tests"])
        self.assertEqual(report["passed"], 1)


def _write_interactable_probe(project: Path) -> None:
    (project / "scripts" / "interactable_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const InteractableData := preload("res://addons/interaction/interactable.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                var parent := Node.new()
                parent.name = "Door"
                add_child(parent)
                var interactable = InteractableData.new()
                interactable.name = "Interactable"
                parent.add_child(interactable)

                _assert_string("Door", interactable.get_interaction_id(), "fallback interaction id", errors)
                _assert_string("Interact", interactable.get_interaction_prompt(self), "default prompt", errors)
                _assert_bool(interactable.can_interact(self), "enabled interactable can interact", errors)

                interactable.interaction_id = &"door_01"
                interactable.prompt = "Open"
                interactable.priority = 10
                var result: Dictionary = interactable.interact(self)
                _assert_bool(bool(result.get("ok", false)), "default interaction succeeds", errors)
                _assert_string("door_01", String(result.get("interaction_id", "")), "result interaction id", errors)
                _assert_string("Door", String(result.get("target", "")), "result target", errors)

                var saved_state: Dictionary = interactable.get_state()
                _assert_int(1, int(saved_state.get("schema_version", -1)), "state schema", errors)
                _assert_string("door_01", String(saved_state.get("interaction_id", "")), "state id", errors)
                saved_state["schema_version"] = 1.0
                saved_state["interaction_id"] = "saved_diagnostic"
                saved_state["priority"] = 10.0
                interactable.prompt = "Changed"
                interactable.priority = 0
                interactable.enabled = false
                var apply_result: Dictionary = interactable.apply_state(saved_state)
                _assert_bool(bool(apply_result.get("ok", false)), "apply_state succeeds", errors)
                _assert_string("door_01", interactable.get_interaction_id(), "configured id remains", errors)
                _assert_string("Open", interactable.prompt, "restored prompt", errors)
                _assert_int(10, interactable.priority, "restored priority", errors)
                _assert_bool(interactable.enabled, "restored enabled", errors)

                var bad_state := {"schema_version": 1.0, "interaction_id": "door_01", "enabled": "yes", "prompt": "Should Not Apply", "priority": 99.0}
                var bad_result: Dictionary = interactable.apply_state(bad_state)
                _assert_bool(not bool(bad_result.get("ok", true)), "bad state should fail", errors)
                _assert_contains(bad_result.get("errors", []), "enabled", "bad enabled error", errors)
                _assert_string("Open", interactable.prompt, "bad state should not mutate prompt", errors)
                _assert_int(10, interactable.priority, "bad state should not mutate priority", errors)
                _assert_bool(interactable.enabled, "bad state should not mutate enabled", errors)

                var partial_result: Dictionary = interactable.apply_state({"enabled": false})
                _assert_bool(not bool(partial_result.get("ok", true)), "partial state should fail", errors)
                _assert_contains(partial_result.get("errors", []), "schema_version", "partial state schema error", errors)
                _assert_bool(interactable.enabled, "partial state should not mutate enabled", errors)

                interactable.enabled = false
                var disabled_result: Dictionary = interactable.interact(self)
                _assert_bool(not bool(disabled_result.get("ok", true)), "disabled interaction should fail", errors)
                _assert_contains(disabled_result.get("errors", []), "disabled", "disabled error", errors)

                return {"ok": errors.is_empty(), "errors": errors}


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %d, got %d" % [label, expected, actual])


            func _assert_string(expected: String, actual: String, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, expected, actual])


            func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        return
                errors.append("%s: missing %s in %s" % [label, needle, str(messages)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "interactable_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/interactable_probe.gd" id="1_probe_script"]

            [node name="InteractableProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )


def _write_abilities_database_probe(project: Path) -> None:
    (project / "scripts" / "abilities_database_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const AbilityDefinitionData := preload("res://addons/abilities/ability_definition.gd")
            const AbilityDatabaseData := preload("res://addons/abilities/ability_database.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                var dash := AbilityDefinitionData.new()
                dash.ability_id = &"dash"
                dash.cooldown = 0.5
                dash.max_charges = 1
                dash.initial_charges = 1
                dash.costs = {"stamina": 20.0}
                dash.default_data = {"range": 4.0}

                var valid_database := AbilityDatabaseData.new()
                valid_database.abilities.append(dash)
                _assert_ok(valid_database.validate(), "valid database", errors)
                _assert_bool(valid_database.has_ability("dash"), "has dash", errors)
                _assert_string("dash", String(valid_database.get_ability("dash").ability_id), "dash lookup", errors)
                _assert_int(1, valid_database.get_ability_ids().size(), "ability id count", errors)

                var invalid_resource_database := AbilityDatabaseData.new()
                invalid_resource_database.abilities.append(Resource.new())
                _assert_error(invalid_resource_database.validate(), "must be an AbilityDefinition", "invalid resource", errors)

                var empty_id := AbilityDefinitionData.new()
                empty_id.ability_id = &""
                var empty_database := AbilityDatabaseData.new()
                empty_database.abilities.append(empty_id)
                _assert_error(empty_database.validate(), "ability_id must be non-empty", "empty ability_id", errors)

                var duplicate := AbilityDefinitionData.new()
                duplicate.ability_id = &"dash"
                var duplicate_database := AbilityDatabaseData.new()
                duplicate_database.abilities.append(dash)
                duplicate_database.abilities.append(duplicate)
                _assert_error(duplicate_database.validate(), "Duplicate ability_id", "duplicate ability_id", errors)

                var bad_cooldown := AbilityDefinitionData.new()
                bad_cooldown.ability_id = &"bad_cooldown"
                bad_cooldown.cooldown = -1.0
                var cooldown_database := AbilityDatabaseData.new()
                cooldown_database.abilities.append(bad_cooldown)
                _assert_error(cooldown_database.validate(), "cooldown must be zero or greater", "bad cooldown", errors)

                var infinite_cooldown := AbilityDefinitionData.new()
                infinite_cooldown.ability_id = &"infinite_cooldown"
                infinite_cooldown.cooldown = INF
                var infinite_cooldown_database := AbilityDatabaseData.new()
                infinite_cooldown_database.abilities.append(infinite_cooldown)
                _assert_error(infinite_cooldown_database.validate(), "cooldown must be finite", "infinite cooldown", errors)

                var nan_cooldown := AbilityDefinitionData.new()
                nan_cooldown.ability_id = &"nan_cooldown"
                nan_cooldown.cooldown = NAN
                var nan_cooldown_database := AbilityDatabaseData.new()
                nan_cooldown_database.abilities.append(nan_cooldown)
                _assert_error(nan_cooldown_database.validate(), "cooldown must be finite", "nan cooldown", errors)

                var bad_charges := AbilityDefinitionData.new()
                bad_charges.ability_id = &"bad_charges"
                bad_charges.max_charges = 1
                bad_charges.initial_charges = 2
                var charges_database := AbilityDatabaseData.new()
                charges_database.abilities.append(bad_charges)
                _assert_error(charges_database.validate(), "initial_charges must be <= max_charges", "bad charges", errors)

                var infinite_recovery := AbilityDefinitionData.new()
                infinite_recovery.ability_id = &"infinite_recovery"
                infinite_recovery.charge_recovery_time = INF
                var infinite_recovery_database := AbilityDatabaseData.new()
                infinite_recovery_database.abilities.append(infinite_recovery)
                _assert_error(infinite_recovery_database.validate(), "charge_recovery_time must be finite", "infinite recovery", errors)

                var bad_data := AbilityDefinitionData.new()
                bad_data.ability_id = &"bad_data"
                bad_data.default_data = {"node": self}
                var data_database := AbilityDatabaseData.new()
                data_database.abilities.append(bad_data)
                _assert_error(data_database.validate(), "default_data must be JSON-compatible", "bad default_data", errors)

                var bad_costs := AbilityDefinitionData.new()
                bad_costs.ability_id = &"bad_costs"
                bad_costs.costs = {"node": self}
                var costs_database := AbilityDatabaseData.new()
                costs_database.abilities.append(bad_costs)
                _assert_error(costs_database.validate(), "costs must be JSON-compatible", "bad costs", errors)

                var non_numeric_costs := AbilityDefinitionData.new()
                non_numeric_costs.ability_id = &"non_numeric_costs"
                non_numeric_costs.costs = {"mana": "free"}
                var non_numeric_costs_database := AbilityDatabaseData.new()
                non_numeric_costs_database.abilities.append(non_numeric_costs)
                _assert_error(non_numeric_costs_database.validate(), "scalar costs must be finite numbers", "non-numeric costs", errors)

                var boolean_costs := AbilityDefinitionData.new()
                boolean_costs.ability_id = &"boolean_costs"
                boolean_costs.costs = {"ammo": true}
                var boolean_costs_database := AbilityDatabaseData.new()
                boolean_costs_database.abilities.append(boolean_costs)
                _assert_error(boolean_costs_database.validate(), "scalar costs must be finite numbers", "boolean costs", errors)

                var cyclic_data_value := {}
                cyclic_data_value["self"] = cyclic_data_value
                var cyclic_data := AbilityDefinitionData.new()
                cyclic_data.ability_id = &"cyclic_data"
                cyclic_data.default_data = cyclic_data_value
                var cyclic_data_database := AbilityDatabaseData.new()
                cyclic_data_database.abilities.append(cyclic_data)
                _assert_error(cyclic_data_database.validate(), "default_data must be JSON-compatible", "cyclic default_data", errors)

                var cyclic_costs_value := {}
                cyclic_costs_value["self"] = cyclic_costs_value
                var cyclic_costs := AbilityDefinitionData.new()
                cyclic_costs.ability_id = &"cyclic_costs"
                cyclic_costs.costs = cyclic_costs_value
                var cyclic_costs_database := AbilityDatabaseData.new()
                cyclic_costs_database.abilities.append(cyclic_costs)
                _assert_error(cyclic_costs_database.validate(), "costs must be JSON-compatible", "cyclic costs", errors)

                return {"ok": errors.is_empty(), "errors": errors}


            func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
                if not bool(result.get("ok", false)):
                    errors.append("%s failed: %s" % [label, str(result)])


            func _assert_error(result: Dictionary, needle: String, label: String, errors: Array[String]) -> void:
                if bool(result.get("ok", true)):
                    errors.append("%s should fail" % label)
                    return
                for message in result.get("errors", []):
                    if String(message).contains(needle):
                        return
                errors.append("%s missing %s in %s" % [label, needle, str(result)])


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_string(expected: String, actual: String, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, expected, actual])


            func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %d, got %d" % [label, expected, actual])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "abilities_database_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/abilities_database_probe.gd" id="1_probe_script"]

            [node name="AbilitiesDatabaseProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )


def _write_abilities_container_probe(project: Path) -> None:
    (project / "scripts" / "abilities_container_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const AbilityDefinitionData := preload("res://addons/abilities/ability_definition.gd")
            const AbilityDatabaseData := preload("res://addons/abilities/ability_database.gd")
            const AbilityContainerData := preload("res://addons/abilities/ability_container.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                var database := _make_database()
                var container := AbilityContainerData.new()
                container.initialize_on_ready = false
                container.auto_update = false
                container.database = database
                add_child(container)

                var init_result: Dictionary = container.initialize_abilities()
                _assert_ok(init_result, "initialize_abilities", errors)
                _assert_int(3, container.get_abilities().size(), "initialized ability count", errors)

                var before_can_dash: Dictionary = container.get_ability_runtime("dash")
                var can_dash: Dictionary = container.can_activate("dash", {"actor_id": "probe"})
                _assert_ok(can_dash, "can_activate dash", errors)
                var after_can_dash: Dictionary = container.get_ability_runtime("dash")
                _assert_runtime_equal(before_can_dash, after_can_dash, "can_activate should not mutate dash", errors)

                var dash_context := {"actor_id": "probe", "target": [1.0, 2.0]}
                var activate_dash: Dictionary = container.activate("dash", dash_context)
                _assert_ok(activate_dash, "activate dash", errors)
                _assert_float(20.0, float(activate_dash.get("costs", {}).get("stamina", 0.0)), "dash reported stamina cost", errors)
                _assert_float(4.0, float(activate_dash.get("data", {}).get("range", 0.0)), "dash reported range data", errors)
                _assert_string("probe", String(activate_dash.get("context", {}).get("actor_id", "")), "dash reported context", errors)
                var dash_runtime: Dictionary = container.get_ability_runtime("dash")
                _assert_int(0, int(dash_runtime.get("charges", -1)), "dash charges after activation", errors)
                _assert_float(0.5, float(dash_runtime.get("cooldown_remaining", -1.0)), "dash cooldown after activation", errors)

                var before_second_dash: Dictionary = container.get_ability_runtime("dash")
                var second_dash: Dictionary = container.activate("dash")
                _assert_error(second_dash, "cooldown", "second dash activation", errors)
                var after_second_dash: Dictionary = container.get_ability_runtime("dash")
                _assert_int(int(before_second_dash.get("charges", -1)), int(after_second_dash.get("charges", -2)), "failed dash should not spend charges", errors)
                _assert_float(float(before_second_dash.get("cooldown_remaining", -1.0)), float(after_second_dash.get("cooldown_remaining", -2.0)), "failed dash should not change cooldown", errors)

                var dash_events: Array[Dictionary] = container.update_abilities(0.5)
                _assert_has_event(dash_events, "ability_cooldown_ready", "dash", "dash cooldown ready event", errors)
                _assert_has_event(dash_events, "ability_charge_recovered", "dash", "dash charge recovered event", errors)
                var dash_after_update: Dictionary = container.get_ability_runtime("dash")
                _assert_int(1, int(dash_after_update.get("charges", -1)), "dash charge recovered", errors)
                _assert_float(0.0, float(dash_after_update.get("cooldown_remaining", -1.0)), "dash cooldown recovered", errors)

                var disable_scan: Dictionary = container.set_enabled("scan", false)
                _assert_ok(disable_scan, "disable scan", errors)
                _assert_bool(not container.is_enabled("scan"), "scan should be disabled", errors)
                _assert_error(container.activate("scan"), "disabled", "disabled scan activation", errors)
                var enable_scan: Dictionary = container.set_enabled("scan", true)
                _assert_ok(enable_scan, "enable scan", errors)
                _assert_ok(container.activate("scan"), "enabled scan activation", errors)

                _assert_ok(container.activate("repair"), "first repair", errors)
                _assert_ok(container.activate("repair"), "second repair", errors)
                var repair_empty: Dictionary = container.get_ability_runtime("repair")
                _assert_int(0, int(repair_empty.get("charges", -1)), "repair charges after two activations", errors)
                var repair_events: Array[Dictionary] = container.update_abilities(0.25)
                _assert_has_event(repair_events, "ability_charge_recovered", "repair", "repair charge recovered event", errors)
                var repair_after_update: Dictionary = container.get_ability_runtime("repair")
                _assert_int(1, int(repair_after_update.get("charges", -1)), "repair recovered one charge", errors)

                var before_negative: Array = container.get_abilities()
                var negative_events: Array[Dictionary] = container.update_abilities(-1.0)
                _assert_int(1, negative_events.size(), "negative delta event count", errors)
                if negative_events.size() == 1:
                    _assert_error(negative_events[0], "delta", "negative delta event", errors)
                    _assert_string("ability_update_failed", String(negative_events[0].get("type", "")), "negative delta event type", errors)
                _assert_runtime_arrays_equal(before_negative, container.get_abilities(), "negative delta should not mutate state", errors)

                return {"ok": errors.is_empty(), "errors": errors}


            func _make_database() -> Resource:
                var dash := AbilityDefinitionData.new()
                dash.ability_id = &"dash"
                dash.cooldown = 0.5
                dash.max_charges = 1
                dash.initial_charges = 1
                dash.costs = {"stamina": 20.0}
                dash.default_data = {"range": 4.0}

                var scan := AbilityDefinitionData.new()
                scan.ability_id = &"scan"
                scan.max_charges = 0
                scan.initial_charges = 0
                scan.default_data = {"radius": 10.0}

                var repair := AbilityDefinitionData.new()
                repair.ability_id = &"repair"
                repair.max_charges = 2
                repair.initial_charges = 2
                repair.charge_recovery_time = 0.25
                repair.default_data = {"amount": 15.0}

                var database := AbilityDatabaseData.new()
                database.abilities.append(dash)
                database.abilities.append(scan)
                database.abilities.append(repair)
                return database


            func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
                if not bool(result.get("ok", false)):
                    errors.append("%s failed: %s" % [label, str(result)])


            func _assert_error(result: Dictionary, needle: String, label: String, errors: Array[String]) -> void:
                if bool(result.get("ok", true)):
                    errors.append("%s should fail" % label)
                    return
                for message in result.get("errors", []):
                    if String(message).contains(needle):
                        return
                errors.append("%s missing %s in %s" % [label, needle, str(result)])


            func _assert_has_event(events: Array, event_type: String, ability_id: String, label: String, errors: Array[String]) -> void:
                for event in events:
                    if String(event.get("type", "")) == event_type and String(event.get("ability_id", "")) == ability_id:
                        return
                errors.append("%s missing %s for %s in %s" % [label, event_type, ability_id, str(events)])


            func _assert_runtime_arrays_equal(expected: Array, actual: Array, label: String, errors: Array[String]) -> void:
                if expected.size() != actual.size():
                    errors.append("%s: expected %d abilities, got %d" % [label, expected.size(), actual.size()])
                    return
                for index in range(expected.size()):
                    var expected_runtime: Dictionary = expected[index]
                    var actual_runtime: Dictionary = actual[index]
                    _assert_runtime_equal(expected_runtime, actual_runtime, "%s %d" % [label, index], errors)


            func _assert_runtime_equal(expected_runtime: Dictionary, actual_runtime: Dictionary, label: String, errors: Array[String]) -> void:
                _assert_string(String(expected_runtime.get("ability_id", "")), String(actual_runtime.get("ability_id", "")), "%s ability_id" % label, errors)
                _assert_bool(bool(expected_runtime.get("enabled", false)) == bool(actual_runtime.get("enabled", true)), "%s enabled" % label, errors)
                _assert_int(int(expected_runtime.get("charges", -1)), int(actual_runtime.get("charges", -2)), "%s charges" % label, errors)
                _assert_float(float(expected_runtime.get("cooldown_remaining", -1.0)), float(actual_runtime.get("cooldown_remaining", -2.0)), "%s cooldown" % label, errors)
                _assert_float(float(expected_runtime.get("charge_recovery_remaining", -1.0)), float(actual_runtime.get("charge_recovery_remaining", -2.0)), "%s recovery" % label, errors)


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_string(expected: String, actual: String, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, expected, actual])


            func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %d, got %d" % [label, expected, actual])


            func _assert_float(expected: float, actual: float, label: String, errors: Array[String]) -> void:
                if absf(expected - actual) > 0.0001:
                    errors.append("%s: expected %s, got %s" % [label, str(expected), str(actual)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "abilities_container_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/abilities_container_probe.gd" id="1_probe_script"]

            [node name="AbilitiesContainerProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )


def _write_stats_database_probe(project: Path) -> None:
    (project / "scripts" / "stats_database_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const StatDefinitionData := preload("res://addons/stats/stat_definition.gd")
            const StatDatabaseData := preload("res://addons/stats/stat_database.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                var health := StatDefinitionData.new()
                health.stat_id = &"health"
                health.display_name = "Health"
                health.default_base_value = 100.0
                health.default_current_value = 100.0
                health.clamp_min = true
                health.min_value = 0.0
                health.is_pool = true

                var stamina := StatDefinitionData.new()
                stamina.stat_id = &"stamina"
                stamina.display_name = "Stamina"
                stamina.default_base_value = 50.0
                stamina.default_current_value = 25.0
                stamina.clamp_min = true
                stamina.min_value = 0.0
                stamina.is_pool = true

                var database := StatDatabaseData.new()
                database.stats = [health, stamina]
                var valid_result: Dictionary = database.validate()
                _assert_bool(bool(valid_result.get("ok", false)), "database should validate", errors)
                _assert_bool(database.has_stat("health"), "database has health", errors)
                _assert_bool(database.get_stat("missing") == null, "missing stat returns null", errors)
                _assert_array(["health", "stamina"], database.get_stat_ids(), "stat id order", errors)

                var duplicate := StatDefinitionData.new()
                duplicate.stat_id = &"health"
                var duplicate_database := StatDatabaseData.new()
                duplicate_database.stats = [health, duplicate]
                var duplicate_result: Dictionary = duplicate_database.validate()
                _assert_bool(not bool(duplicate_result.get("ok", true)), "duplicate database should fail", errors)
                _assert_contains(duplicate_result.get("errors", []), "Duplicate stat_id: health", "duplicate error", errors)

                var bad_bounds := StatDefinitionData.new()
                bad_bounds.stat_id = &"bad_bounds"
                bad_bounds.clamp_min = true
                bad_bounds.min_value = 10.0
                bad_bounds.clamp_max = true
                bad_bounds.max_value = 1.0
                var bad_database := StatDatabaseData.new()
                bad_database.stats = [bad_bounds]
                var bad_result: Dictionary = bad_database.validate()
                _assert_bool(not bool(bad_result.get("ok", true)), "bad bounds should fail", errors)
                _assert_contains(bad_result.get("errors", []), "min_value must be <= max_value", "bad bounds error", errors)

                return {"ok": errors.is_empty(), "errors": errors}


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_array(expected: Array, actual: Array, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, str(expected), str(actual)])


            func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        return
                errors.append("%s: missing %s in %s" % [label, needle, str(messages)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "stats_database_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/stats_database_probe.gd" id="1_probe_script"]

            [node name="StatsDatabaseProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )


def _write_stats_container_probe(project: Path) -> None:
    (project / "scripts" / "stats_container_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const StatDefinitionData := preload("res://addons/stats/stat_definition.gd")
            const StatDatabaseData := preload("res://addons/stats/stat_database.gd")
            const StatContainerData := preload("res://addons/stats/stat_container.gd")

            var events: Array[String] = []


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                var container := StatContainerData.new()
                container.name = "Stats"
                container.initialize_on_ready = false
                add_child(container)
                container.database = _make_database()
                container.stat_depleted.connect(func(stat_id: String, _value: float, _result: Dictionary): events.append("depleted:%s" % stat_id))
                container.stat_filled.connect(func(stat_id: String, _value: float, _result: Dictionary): events.append("filled:%s" % stat_id))

                var init_result: Dictionary = container.initialize_stats()
                _assert_ok(init_result, "initialize", errors)
                _assert_float(100.0, container.get_base_value("health"), "health base", errors)
                _assert_float(100.0, container.get_value("health"), "health current", errors)
                _assert_float(4.0, container.get_value("move_speed"), "move speed current", errors)

                var damage_result: Dictionary = container.modify_value("health", -25.0)
                _assert_ok(damage_result, "damage", errors)
                _assert_float(75.0, container.get_value("health"), "health after damage", errors)

                var deplete_result: Dictionary = container.modify_value("health", -999.0)
                _assert_ok(deplete_result, "deplete", errors)
                _assert_bool(bool(deplete_result.get("clamped", false)), "deplete should clamp", errors)
                _assert_float(0.0, container.get_value("health"), "health after depletion", errors)
                _assert_contains(events, "depleted:health", "depletion event", errors)

                var fill_result: Dictionary = container.set_value("health", 100.0)
                _assert_ok(fill_result, "fill", errors)
                _assert_contains(events, "filled:health", "fill event", errors)

                var lower_base_result: Dictionary = container.set_base_value("health", 40.0)
                _assert_ok(lower_base_result, "lower base", errors)
                _assert_float(40.0, container.get_base_value("health"), "lowered base", errors)
                _assert_float(40.0, container.get_value("health"), "pool current clamps to base", errors)

                var speed_result: Dictionary = container.set_base_value("move_speed", 8.0)
                _assert_ok(speed_result, "speed base", errors)
                var speed_current_result: Dictionary = container.set_value("move_speed", 12.0)
                _assert_ok(speed_current_result, "speed current", errors)
                _assert_float(12.0, container.get_value("move_speed"), "non-pool current ignores base maximum", errors)

                var saved_state: Dictionary = container.get_state()
                container.set_value("health", 5.0)
                container.set_value("move_speed", 1.0)
                var restore_result: Dictionary = container.apply_state(saved_state)
                _assert_ok(restore_result, "state restore", errors)
                _assert_float(40.0, container.get_value("health"), "restored health", errors)
                _assert_float(12.0, container.get_value("move_speed"), "restored move speed", errors)

                var bad_result: Dictionary = container.set_value("missing", 1.0)
                _assert_bool(not bool(bad_result.get("ok", true)), "missing stat should fail", errors)
                _assert_contains(bad_result.get("errors", []), "Unknown stat_id: missing", "missing stat error", errors)

                var before_bad_state: Dictionary = container.get_state()
                var bad_state := {"schema_version": 1, "stats": [{"stat_id": "health", "base_value": 100.0, "current_value": 500.0}]}
                var bad_state_result: Dictionary = container.apply_state(bad_state)
                _assert_bool(not bool(bad_state_result.get("ok", true)), "bad state should fail", errors)
                _assert_dictionary(before_bad_state, container.get_state(), "bad state should not mutate", errors)

                return {"ok": errors.is_empty(), "errors": errors, "events": events}


            func _make_database() -> Resource:
                var health := StatDefinitionData.new()
                health.stat_id = &"health"
                health.display_name = "Health"
                health.default_base_value = 100.0
                health.default_current_value = 100.0
                health.clamp_min = true
                health.min_value = 0.0
                health.is_pool = true

                var move_speed := StatDefinitionData.new()
                move_speed.stat_id = &"move_speed"
                move_speed.display_name = "Move Speed"
                move_speed.default_base_value = 4.0
                move_speed.default_current_value = 4.0
                move_speed.clamp_min = true
                move_speed.min_value = 0.0

                var database := StatDatabaseData.new()
                database.stats = [health, move_speed]
                return database


            func _assert_ok(result: Dictionary, label: String, errors: Array[String]) -> void:
                if not bool(result.get("ok", false)):
                    errors.append("%s failed: %s" % [label, str(result)])


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_float(expected: float, actual: float, label: String, errors: Array[String]) -> void:
                if not is_equal_approx(expected, actual):
                    errors.append("%s: expected %s, got %s" % [label, str(expected), str(actual)])


            func _assert_dictionary(expected: Dictionary, actual: Dictionary, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, str(expected), str(actual)])


            func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        return
                errors.append("%s: missing %s in %s" % [label, needle, str(messages)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "stats_container_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/stats_container_probe.gd" id="1_probe_script"]

            [node name="StatsContainerProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )


def _write_stats_container_review_probe(project: Path) -> None:
    (project / "scripts" / "stats_container_review_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const StatContainerData := preload("res://addons/stats/stat_container.gd")
            const StatDefinitionData := preload("res://addons/stats/stat_definition.gd")
            const StatDatabaseData := preload("res://addons/stats/stat_database.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                _validate_missing_stat_fill_uses_clamped_base(errors)
                _validate_stale_runtime_stat_returns_error(errors)
                _validate_malformed_schema_rejected_without_mutation(errors)
                return {"ok": errors.is_empty(), "errors": errors}


            func _validate_missing_stat_fill_uses_clamped_base(errors: Array[String]) -> void:
                var stamina = StatDefinitionData.new()
                stamina.stat_id = &"stamina"
                stamina.default_base_value = 150.0
                stamina.default_current_value = 150.0
                stamina.clamp_min = true
                stamina.min_value = 0.0
                stamina.clamp_max = true
                stamina.max_value = 100.0
                stamina.is_pool = true

                var health = StatDefinitionData.new()
                health.stat_id = &"health"
                health.default_base_value = 10.0
                health.default_current_value = 10.0

                var database = StatDatabaseData.new()
                database.stats.append(health)
                database.stats.append(stamina)

                var container = StatContainerData.new()
                container.initialize_on_ready = false
                container.database = database
                add_child(container)

                var result: Dictionary = container.apply_state({
                    "schema_version": 1,
                    "stats": [{"stat_id": "health", "base_value": 10.0, "current_value": 7.0}],
                })
                _assert_bool(bool(result.get("ok", false)), "apply_state should succeed", errors)
                var restored_stamina := container.get_stat("stamina")
                _assert_float(100.0, float(restored_stamina.get("base_value", -1.0)), "stamina filled base value", errors)
                _assert_float(100.0, float(restored_stamina.get("current_value", -1.0)), "stamina filled current value", errors)
                container.queue_free()


            func _validate_stale_runtime_stat_returns_error(errors: Array[String]) -> void:
                var health = StatDefinitionData.new()
                health.stat_id = &"health"
                health.default_base_value = 10.0
                health.default_current_value = 10.0

                var initial_database = StatDatabaseData.new()
                initial_database.stats.append(health)

                var container = StatContainerData.new()
                container.initialize_on_ready = false
                container.database = initial_database
                add_child(container)

                var initialize_result: Dictionary = container.initialize_stats()
                _assert_bool(bool(initialize_result.get("ok", false)), "initialize_stats should succeed", errors)
                _assert_bool(container.has_stat("health"), "container should have initialized health", errors)

                container.database = StatDatabaseData.new()
                var stale_result: Dictionary = container.set_value("health", 5.0)
                _assert_bool(not bool(stale_result.get("ok", true)), "stale stat mutation should fail", errors)
                _assert_contains(stale_result.get("errors", []), "Unknown stat_id", "stale stat mutation error", errors)
                container.queue_free()


            func _validate_malformed_schema_rejected_without_mutation(errors: Array[String]) -> void:
                var health = StatDefinitionData.new()
                health.stat_id = &"health"
                health.default_base_value = 10.0
                health.default_current_value = 10.0

                var database = StatDatabaseData.new()
                database.stats.append(health)

                var container = StatContainerData.new()
                container.initialize_on_ready = false
                container.database = database
                add_child(container)

                var initialize_result: Dictionary = container.initialize_stats()
                _assert_bool(bool(initialize_result.get("ok", false)), "initialize_stats should succeed for malformed schema probe", errors)

                var before_state: Dictionary = container.get_state()
                var malformed_states: Array = [
                    {"label": "fractional schema", "state": {"schema_version": 1.5, "stats": [{"stat_id": "health", "base_value": 9.0, "current_value": 9.0}]}},
                    {"label": "string schema", "state": {"schema_version": "1", "stats": [{"stat_id": "health", "base_value": 8.0, "current_value": 8.0}]}},
                ]
                for entry in malformed_states:
                    var label := String(entry["label"])
                    var apply_result: Dictionary = container.apply_state(entry["state"])
                    _assert_bool(not bool(apply_result.get("ok", true)), "%s should fail" % label, errors)
                    _assert_contains(apply_result.get("errors", []), "schema_version", "%s schema error" % label, errors)
                    _assert_contains(apply_result.get("errors", []), "integer", "%s integer error" % label, errors)
                    _assert_dictionary(before_state, container.get_state(), "%s should not mutate" % label, errors)

                container.queue_free()


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_float(expected: float, actual: float, label: String, errors: Array[String]) -> void:
                if not is_equal_approx(expected, actual):
                    errors.append("%s: expected %s, got %s" % [label, str(expected), str(actual)])


            func _assert_dictionary(expected: Dictionary, actual: Dictionary, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, str(expected), str(actual)])


            func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        return
                errors.append("%s: missing %s in %s" % [label, needle, str(messages)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "stats_container_review_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/stats_container_review_probe.gd" id="1_probe_script"]

            [node name="StatsContainerReviewProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )


def _write_interactor_probe(project: Path) -> None:
    (project / "scripts" / "data_echo_interactable.gd").write_text(
        textwrap.dedent(
            """\
            extends "res://addons/interaction/interactable.gd"


            func can_interact(actor: Node, data: Dictionary = {}) -> bool:
                return enabled and bool(data.get("allowed", false))


            func interact(actor: Node, data: Dictionary = {}) -> Dictionary:
                var result := super.interact(actor, data)
                result["data_source"] = String(data.get("source", ""))
                return result
            """
        ),
        encoding="utf-8",
    )
    (project / "scripts" / "interactor_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const DataEchoInteractableData := preload("res://scripts/data_echo_interactable.gd")
            const InteractableData := preload("res://addons/interaction/interactable.gd")
            const Interactor2DData := preload("res://addons/interaction/interactor_2d.gd")
            const Interactor3DData := preload("res://addons/interaction/interactor_3d.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                var actor := Node2D.new()
                actor.name = "Actor"
                add_child(actor)
                var interactor = Interactor2DData.new()
                interactor.name = "Interactor2D"
                actor.add_child(interactor)

                var low_area := Area2D.new()
                low_area.name = "LowArea"
                add_child(low_area)
                var low = InteractableData.new()
                low.name = "Interactable"
                low.interaction_id = &"low"
                low.prompt = "Use Low"
                low.priority = 1
                low_area.add_child(low)

                var high_area := Area2D.new()
                high_area.name = "HighArea"
                add_child(high_area)
                var high = DataEchoInteractableData.new()
                high.name = "Interactable"
                high.interaction_id = &"high"
                high.prompt = "Use High"
                high.priority = 10
                high_area.add_child(high)

                interactor.call("_on_node_entered", low_area)
                interactor.call("_on_node_entered", high_area)
                _assert_int(2, interactor.get_candidates().size(), "candidate count", errors)
                _assert_string("high", interactor.get_best_candidate().get_interaction_id(), "priority winner", errors)
                _assert_string("Use High", interactor.get_best_prompt(), "best prompt", errors)
                var high_result: Dictionary = interactor.interact_best({"allowed": true, "source": "best"})
                _assert_bool(bool(high_result.get("ok", false)), "high interaction succeeds", errors)
                _assert_string("high", String(high_result.get("interaction_id", "")), "high result id", errors)
                _assert_string("best", String(high_result.get("data_source", "")), "interact_best data forwarding", errors)

                var success_ambiguous_area := Area2D.new()
                success_ambiguous_area.name = "SuccessAmbiguousArea"
                add_child(success_ambiguous_area)
                var success_first = InteractableData.new()
                success_first.name = "SuccessFirstInteractable"
                success_ambiguous_area.add_child(success_first)
                var success_second = InteractableData.new()
                success_second.name = "SuccessSecondInteractable"
                success_ambiguous_area.add_child(success_second)
                interactor.call("_on_node_entered", success_ambiguous_area)
                var warned_success: Dictionary = interactor.interact_best({"allowed": true, "source": "warned"})
                _assert_bool(bool(warned_success.get("ok", false)), "warning-carrying success should pass", errors)
                _assert_contains(warned_success.get("warnings", []), "Ambiguous", "success ambiguous warning", errors)
                _assert_string("warned", String(warned_success.get("data_source", "")), "warning success data forwarding", errors)
                var clean_success: Dictionary = interactor.interact_best({"allowed": true, "source": "clean"})
                _assert_bool(bool(clean_success.get("ok", false)), "post-warning success should pass", errors)
                _assert_not_contains(clean_success.get("warnings", []), "Ambiguous", "success ambiguous warning should be consumed", errors)
                _assert_string("clean", String(clean_success.get("data_source", "")), "clean success data forwarding", errors)

                high.enabled = false
                _assert_string("low", interactor.get_best_candidate().get_interaction_id(), "disabled high is skipped", errors)
                interactor.call("_on_node_exited", low_area)
                _assert_int(0, interactor.get_candidates().size(), "disabled remaining candidate hidden", errors)

                interactor.clear_candidates()
                var no_candidate: Dictionary = interactor.interact_best()
                _assert_bool(not bool(no_candidate.get("ok", true)), "no candidate should fail", errors)
                _assert_contains(no_candidate.get("errors", []), "No interaction candidate", "no candidate error", errors)

                var ambiguous_area := Area2D.new()
                ambiguous_area.name = "AmbiguousArea"
                add_child(ambiguous_area)
                var first = InteractableData.new()
                first.name = "FirstInteractable"
                ambiguous_area.add_child(first)
                var second = InteractableData.new()
                second.name = "SecondInteractable"
                ambiguous_area.add_child(second)
                interactor.call("_on_node_entered", ambiguous_area)
                var ambiguous_result: Dictionary = interactor.interact_best()
                _assert_bool(not bool(ambiguous_result.get("ok", true)), "ambiguous candidate should not be selected", errors)
                _assert_contains(ambiguous_result.get("warnings", []), "Ambiguous", "ambiguous warning", errors)

                var target_result: Dictionary = interactor.interact_with(low)
                _assert_bool(bool(target_result.get("ok", false)), "targeted interaction works outside candidates", errors)
                _assert_not_contains(target_result.get("warnings", []), "Ambiguous", "ambiguous warning should be consumed", errors)
                _assert_error(interactor.interact_with(Node.new()), "Target must be an Interactable", "wrong target", errors)

                var freed_parent := Node.new()
                add_child(freed_parent)
                var freed_target = InteractableData.new()
                freed_parent.add_child(freed_target)
                freed_target.free()
                var freed_result: Dictionary = interactor.interact_with(freed_target)
                _assert_bool(not bool(freed_result.get("ok", true)), "freed target should fail", errors)
                _assert_contains(freed_result.get("errors", []), "invalid", "freed target error", errors)
                var string_result: Dictionary = interactor.call("interact_with", "not a node")
                _assert_error(string_result, "Target must be an Interactable", "string target", errors)

                var actor_3d := Node3D.new()
                actor_3d.name = "Actor3D"
                add_child(actor_3d)
                var interactor_3d = Interactor3DData.new()
                interactor_3d.name = "Interactor3D"
                actor_3d.add_child(interactor_3d)

                var low_area_3d := Area3D.new()
                low_area_3d.name = "LowArea3D"
                add_child(low_area_3d)
                var low_3d = InteractableData.new()
                low_3d.name = "Interactable"
                low_3d.interaction_id = &"low_3d"
                low_3d.prompt = "Use Low 3D"
                low_3d.priority = 1
                low_area_3d.add_child(low_3d)

                var high_area_3d := Area3D.new()
                high_area_3d.name = "HighArea3D"
                add_child(high_area_3d)
                var high_3d = DataEchoInteractableData.new()
                high_3d.name = "Interactable"
                high_3d.interaction_id = &"high_3d"
                high_3d.prompt = "Use High 3D"
                high_3d.priority = 10
                high_area_3d.add_child(high_3d)

                interactor_3d.call("_on_node_entered", low_area_3d)
                interactor_3d.call("_on_node_entered", high_area_3d)
                _assert_int(2, interactor_3d.get_candidates().size(), "3D candidate count", errors)
                _assert_string("high_3d", interactor_3d.get_best_candidate().get_interaction_id(), "3D priority winner", errors)
                _assert_string("Use High 3D", interactor_3d.get_best_prompt(), "3D best prompt", errors)
                var high_result_3d: Dictionary = interactor_3d.interact_best({"allowed": true, "source": "best_3d"})
                _assert_bool(bool(high_result_3d.get("ok", false)), "3D high interaction succeeds", errors)
                _assert_string("high_3d", String(high_result_3d.get("interaction_id", "")), "3D high result id", errors)
                _assert_string("best_3d", String(high_result_3d.get("data_source", "")), "3D interact_best data forwarding", errors)

                high_3d.enabled = false
                _assert_string("low_3d", interactor_3d.get_best_candidate().get_interaction_id(), "3D disabled high is skipped", errors)
                interactor_3d.call("_on_node_exited", low_area_3d)
                _assert_int(0, interactor_3d.get_candidates().size(), "3D disabled remaining candidate hidden", errors)
                _assert_error(interactor_3d.interact_with(Node.new()), "Target must be an Interactable", "3D wrong target", errors)

                var freed_parent_3d := Node.new()
                add_child(freed_parent_3d)
                var freed_target_3d = InteractableData.new()
                freed_parent_3d.add_child(freed_target_3d)
                freed_target_3d.free()
                var freed_result_3d: Dictionary = interactor_3d.interact_with(freed_target_3d)
                _assert_bool(not bool(freed_result_3d.get("ok", true)), "3D freed target should fail", errors)
                _assert_contains(freed_result_3d.get("errors", []), "invalid", "3D freed target error", errors)

                interactor_3d.clear_candidates()
                var no_candidate_3d: Dictionary = interactor_3d.interact_best()
                _assert_bool(not bool(no_candidate_3d.get("ok", true)), "3D interactor exposes same no-candidate behavior", errors)
                _assert_int(0, interactor_3d.get_candidates().size(), "3D empty candidates", errors)

                return {"ok": errors.is_empty(), "errors": errors}


            func _assert_error(result: Dictionary, expected_text: String, label: String, errors: Array[String]) -> void:
                _assert_bool(not bool(result.get("ok", true)), "%s should fail" % label, errors)
                _assert_contains(result.get("errors", []), expected_text, label, errors)


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %d, got %d" % [label, expected, actual])


            func _assert_string(expected: String, actual: String, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, expected, actual])


            func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        return
                errors.append("%s: missing %s in %s" % [label, needle, str(messages)])


            func _assert_not_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        errors.append("%s: unexpected %s in %s" % [label, needle, str(messages)])
                        return
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "interactor_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/interactor_probe.gd" id="1_probe_script"]

            [node name="InteractorProbe" type="Node"]
            script = ExtResource("1_probe_script")
            """
        ),
        encoding="utf-8",
    )


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


def _write_effect_database_probe(project: Path) -> None:
    (project / "scripts" / "effect_database_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const EffectDefinitionData := preload("res://addons/effects/effect_definition.gd")
            const EffectDatabaseData := preload("res://addons/effects/effect_database.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []

                var haste = EffectDefinitionData.new()
                haste.effect_id = &"haste"
                haste.display_name = "Haste"
                haste.tags.append(&"movement")
                haste.tags.append(&"buff")
                haste.duration = 5.0
                haste.tick_interval = 0.0
                haste.stack_mode = "refresh"
                haste.max_stacks = 1
                haste.default_data = {"speed_multiplier": 1.25}
                var valid_database = EffectDatabaseData.new()
                valid_database.effects.append(haste)
                var valid_result: Dictionary = valid_database.validate()
                _assert_bool(bool(valid_result.get("ok", false)), "valid database should pass", errors)
                _assert_bool(valid_database.has_effect("haste"), "valid database should find haste", errors)
                var found_effect = valid_database.get_effect("haste")
                _assert_bool(found_effect != null, "valid database should return haste", errors)
                if found_effect != null:
                    _assert_int(1, int(found_effect.max_stacks), "valid max stacks", errors)

                var invalid_resource_database = EffectDatabaseData.new()
                invalid_resource_database.effects.append(Resource.new())
                var invalid_resource_result: Dictionary = invalid_resource_database.validate()
                _assert_bool(not bool(invalid_resource_result.get("ok", true)), "plain Resource should fail validation", errors)
                _assert_contains(invalid_resource_result.get("errors", []), "EffectDefinition", "plain Resource validation error", errors)

                var whitespace_effect = EffectDefinitionData.new()
                whitespace_effect.effect_id = &" haste "
                var whitespace_database = EffectDatabaseData.new()
                whitespace_database.effects.append(whitespace_effect)
                var whitespace_result: Dictionary = whitespace_database.validate()
                _assert_bool(not bool(whitespace_result.get("ok", true)), "whitespace effect_id should fail validation", errors)
                _assert_contains(whitespace_result.get("errors", []), "whitespace", "whitespace validation error", errors)

                var duplicate_effect = EffectDefinitionData.new()
                duplicate_effect.effect_id = &"haste"
                var duplicate_database = EffectDatabaseData.new()
                duplicate_database.effects.append(haste)
                duplicate_database.effects.append(duplicate_effect)
                var duplicate_result: Dictionary = duplicate_database.validate()
                _assert_bool(not bool(duplicate_result.get("ok", true)), "duplicate effect_id should fail validation", errors)
                _assert_contains(duplicate_result.get("errors", []), "Duplicate effect_id", "duplicate validation error", errors)

                var bad_stack_mode = EffectDefinitionData.new()
                bad_stack_mode.effect_id = &"bad_mode"
                bad_stack_mode.stack_mode = "combine"
                var bad_stack_mode_database = EffectDatabaseData.new()
                bad_stack_mode_database.effects.append(bad_stack_mode)
                var bad_stack_mode_result: Dictionary = bad_stack_mode_database.validate()
                _assert_bool(not bool(bad_stack_mode_result.get("ok", true)), "invalid stack_mode should fail validation", errors)
                _assert_contains(bad_stack_mode_result.get("errors", []), "stack_mode", "stack_mode validation error", errors)

                var bad_default_data = EffectDefinitionData.new()
                bad_default_data.effect_id = &"bad_data"
                bad_default_data.default_data = {"node": Node.new()}
                var bad_data_database = EffectDatabaseData.new()
                bad_data_database.effects.append(bad_default_data)
                var bad_data_result: Dictionary = bad_data_database.validate()
                _assert_bool(not bool(bad_data_result.get("ok", true)), "non-json default_data should fail validation", errors)
                _assert_contains(bad_data_result.get("errors", []), "JSON-compatible", "default_data validation error", errors)

                var bad_string_name_value = EffectDefinitionData.new()
                bad_string_name_value.effect_id = &"bad_string_name_value"
                bad_string_name_value.default_data = {"kind": &"buff"}
                var bad_string_name_value_database = EffectDatabaseData.new()
                bad_string_name_value_database.effects.append(bad_string_name_value)
                var bad_string_name_value_result: Dictionary = bad_string_name_value_database.validate()
                _assert_bool(not bool(bad_string_name_value_result.get("ok", true)), "StringName default_data value should fail validation", errors)
                _assert_contains(bad_string_name_value_result.get("errors", []), "JSON-compatible", "StringName default_data value error", errors)

                var bad_duration = EffectDefinitionData.new()
                bad_duration.effect_id = &"bad_duration"
                bad_duration.duration = INF
                var bad_duration_database = EffectDatabaseData.new()
                bad_duration_database.effects.append(bad_duration)
                var bad_duration_result: Dictionary = bad_duration_database.validate()
                _assert_bool(not bool(bad_duration_result.get("ok", true)), "non-finite duration should fail validation", errors)
                _assert_contains(bad_duration_result.get("errors", []), "duration", "duration validation error", errors)

                var bad_tick_interval = EffectDefinitionData.new()
                bad_tick_interval.effect_id = &"bad_tick_interval"
                bad_tick_interval.tick_interval = INF
                var bad_tick_interval_database = EffectDatabaseData.new()
                bad_tick_interval_database.effects.append(bad_tick_interval)
                var bad_tick_interval_result: Dictionary = bad_tick_interval_database.validate()
                _assert_bool(not bool(bad_tick_interval_result.get("ok", true)), "non-finite tick_interval should fail validation", errors)
                _assert_contains(bad_tick_interval_result.get("errors", []), "tick_interval", "tick_interval validation error", errors)

                return {"ok": errors.is_empty(), "errors": errors}


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %d, got %d" % [label, expected, actual])


            func _assert_contains(values: Array, text: String, label: String, errors: Array[String]) -> void:
                for value in values:
                    if String(value).contains(text):
                        return
                errors.append("%s: did not find %s in %s" % [label, text, str(values)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "effect_database_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/effect_database_probe.gd" id="1_probe"]

            [node name="EffectDatabaseProbe" type="Node"]
            script = ExtResource("1_probe")
            """
        ),
        encoding="utf-8",
    )


def _write_effect_container_probe(project: Path) -> None:
    scripts_dir = project / "scripts"
    scenes_dir = project / "scenes"
    resources_dir = project / "resources" / "effects_probe"
    scripts_dir.mkdir(exist_ok=True)
    scenes_dir.mkdir(exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)
    (resources_dir / "haste.tres").write_text(
        textwrap.dedent(
            """\
            [gd_resource type="Resource" script_class="EffectDefinition" load_steps=2 format=3]

            [ext_resource type="Script" path="res://addons/effects/effect_definition.gd" id="1_haste"]

            [resource]
            script = ExtResource("1_haste")
            effect_id = &"haste"
            display_name = "Haste"
            description = "Temporarily increases speed."
            tags = Array[StringName]([&"buff", &"movement"])
            duration = 2.0
            tick_interval = 0.0
            stack_mode = "refresh"
            max_stacks = 1
            default_data = {"speed_multiplier": 1.25}
            """
        ),
        encoding="utf-8",
    )
    (resources_dir / "poison.tres").write_text(
        textwrap.dedent(
            """\
            [gd_resource type="Resource" script_class="EffectDefinition" load_steps=2 format=3]

            [ext_resource type="Script" path="res://addons/effects/effect_definition.gd" id="1_poison"]

            [resource]
            script = ExtResource("1_poison")
            effect_id = &"poison"
            display_name = "Poison"
            description = "Ticks periodically."
            tags = Array[StringName]([&"debuff", &"dot"])
            duration = 5.0
            tick_interval = 1.0
            stack_mode = "stack"
            max_stacks = 3
            default_data = {"damage": 2}
            """
        ),
        encoding="utf-8",
    )
    (resources_dir / "shielded.tres").write_text(
        textwrap.dedent(
            """\
            [gd_resource type="Resource" script_class="EffectDefinition" load_steps=2 format=3]

            [ext_resource type="Script" path="res://addons/effects/effect_definition.gd" id="1_shielded"]

            [resource]
            script = ExtResource("1_shielded")
            effect_id = &"shielded"
            display_name = "Shielded"
            description = "Permanent shield marker."
            tags = Array[StringName]([&"buff", &"defense"])
            duration = 0.0
            tick_interval = 0.0
            stack_mode = "ignore"
            max_stacks = 1
            default_data = {"armor_bonus": 3}
            """
        ),
        encoding="utf-8",
    )
    (resources_dir / "short_tick.tres").write_text(
        textwrap.dedent(
            """\
            [gd_resource type="Resource" script_class="EffectDefinition" load_steps=2 format=3]

            [ext_resource type="Script" path="res://addons/effects/effect_definition.gd" id="1_short_tick"]

            [resource]
            script = ExtResource("1_short_tick")
            effect_id = &"short_tick"
            display_name = "Short Tick"
            description = "Expires before its first tick."
            tags = Array[StringName]([&"probe"])
            duration = 0.5
            tick_interval = 1.0
            stack_mode = "refresh"
            max_stacks = 1
            default_data = {}
            """
        ),
        encoding="utf-8",
    )
    (resources_dir / "effect_database.tres").write_text(
        textwrap.dedent(
            """\
            [gd_resource type="Resource" script_class="EffectDatabase" load_steps=6 format=3]

            [ext_resource type="Script" path="res://addons/effects/effect_database.gd" id="1_database"]
            [ext_resource type="Resource" path="res://resources/effects_probe/haste.tres" id="2_haste"]
            [ext_resource type="Resource" path="res://resources/effects_probe/poison.tres" id="3_poison"]
            [ext_resource type="Resource" path="res://resources/effects_probe/shielded.tres" id="4_shielded"]
            [ext_resource type="Resource" path="res://resources/effects_probe/short_tick.tres" id="5_short_tick"]

            [resource]
            script = ExtResource("1_database")
            effects = Array[Resource]([ExtResource("2_haste"), ExtResource("3_poison"), ExtResource("4_shielded"), ExtResource("5_short_tick")])
            """
        ),
        encoding="utf-8",
    )
    (scripts_dir / "effect_container_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            @onready var effects: Node = $EffectContainer


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                effects.clear_effects()
                var add_haste: Dictionary = effects.add_effect("haste", self, 1, {"source_id": "probe"})
                _assert_bool(bool(add_haste.get("ok", false)), "add haste should succeed", errors)
                var refresh_haste: Dictionary = effects.add_effect("haste", self, 1, {"speed_multiplier": 1.5})
                _assert_bool(bool(refresh_haste.get("ok", false)), "refresh haste should succeed", errors)
                _assert_int(1, effects.get_stack_count("haste"), "haste stack count", errors)
                _assert_float(1.5, float(effects.get_effect("haste").get("data", {}).get("speed_multiplier", 0.0)), "haste data overlay", errors)

                var add_poison: Dictionary = effects.add_effect("poison", self, 5, {"source_id": "snake"})
                _assert_bool(bool(add_poison.get("ok", false)), "add poison should succeed", errors)
                _assert_int(3, effects.get_stack_count("poison"), "poison stack count after clamp", errors)
                _assert_int(2, int(add_poison.get("remainder", -1)), "poison stack remainder", errors)

                var add_shielded: Dictionary = effects.add_effect("shielded", self, 1)
                var ignored_shielded: Dictionary = effects.add_effect("shielded", self, 1)
                _assert_bool(bool(add_shielded.get("ok", false)), "add shielded should succeed", errors)
                _assert_bool(bool(ignored_shielded.get("ok", false)), "ignored shielded should report success", errors)
                _assert_int(1, effects.get_stack_count("shielded"), "shielded stack count", errors)

                effects.clear_effects()
                var add_short_tick: Dictionary = effects.add_effect("short_tick", self, 1)
                _assert_bool(bool(add_short_tick.get("ok", false)), "add short_tick should succeed", errors)
                var short_tick_events: Array = effects.update_effects(2.0)
                _assert_int(0, _count_events_for_effect(short_tick_events, "tick", "short_tick"), "short_tick should not tick after expiry", errors)
                _assert_bool(_count_events_for_effect(short_tick_events, "expired", "short_tick") >= 1, "short_tick should expire", errors)
                _assert_bool(not effects.has_effect("short_tick"), "short_tick should not remain active", errors)

                effects.clear_effects()
                effects.add_effect("haste", self, 1, {"source_id": "probe"})
                effects.add_effect("haste", self, 1, {"speed_multiplier": 1.5})
                effects.add_effect("poison", self, 5, {"source_id": "snake"})
                effects.add_effect("shielded", self, 1)

                var tick_events: Array = effects.update_effects(2.5)
                var tick_count := _count_events(tick_events, "tick")
                _assert_int(2, tick_count, "poison tick count after 2.5s", errors)
                var expiry_events: Array = effects.update_effects(3.0)
                _assert_bool(_count_events(expiry_events, "expired") >= 1, "haste or poison should expire", errors)
                _assert_bool(not effects.has_effect("haste"), "haste should expire", errors)
                _assert_bool(effects.has_effect("shielded"), "permanent shielded should remain", errors)
                var has_haste_after_expire: bool = effects.has_effect("haste")
                var has_shielded_after_update: bool = effects.has_effect("shielded")

                effects.clear_effects()
                effects.add_effect("poison", self, 2)
                effects.update_effects(1.25)
                var saved_state: Dictionary = effects.get_state()
                effects.clear_effects()
                effects.add_effect("haste", self, 1)
                var apply_result: Dictionary = effects.apply_state(saved_state)
                _assert_bool(bool(apply_result.get("ok", false)), "apply state should succeed", errors)
                _assert_int(2, effects.get_stack_count("poison"), "poison stack count after state round-trip", errors)
                _assert_bool(not effects.has_effect("haste"), "state round-trip should replace active effects", errors)

                var float_schema_state: Dictionary = saved_state.duplicate(true)
                float_schema_state["schema_version"] = 1.0
                effects.clear_effects()
                var float_schema_result: Dictionary = effects.apply_state(float_schema_state)
                _assert_bool(bool(float_schema_result.get("ok", false)), "integral float schema_version should restore state", errors)
                _assert_int(2, effects.get_stack_count("poison"), "poison stack count after float schema_version state", errors)

                var remove_one: Dictionary = effects.remove_effect("poison", 1)
                _assert_bool(bool(remove_one.get("ok", false)), "partial remove should succeed", errors)
                _assert_int(1, effects.get_stack_count("poison"), "poison stack count after partial remove", errors)
                var remove_all: Dictionary = effects.remove_effect("poison")
                _assert_bool(bool(remove_all.get("ok", false)), "full remove should succeed", errors)
                _assert_bool(not effects.has_effect("poison"), "poison should be removed", errors)

                var unknown_result: Dictionary = effects.add_effect("missing", self, 1)
                _assert_bool(not bool(unknown_result.get("ok", true)), "unknown effect should fail", errors)
                var bad_stacks_result: Dictionary = effects.add_effect("haste", self, 0)
                _assert_bool(not bool(bad_stacks_result.get("ok", true)), "zero stacks should fail", errors)
                var malformed_state: Dictionary = effects.apply_state({"schema_version": 1, "effects": [{"effect_id": "missing", "stacks": 1}]})
                _assert_bool(not bool(malformed_state.get("ok", true)), "unknown saved effect should fail", errors)
                var negative_delta_events: Array = effects.update_effects(-1.0)
                _assert_bool(not bool(negative_delta_events[0].get("ok", true)), "negative delta should fail", errors)
                var infinite_delta_events: Array = effects.update_effects(INF)
                _assert_bool(not infinite_delta_events.is_empty(), "infinite delta should return an error event", errors)
                if not infinite_delta_events.is_empty():
                    _assert_bool(not bool(infinite_delta_events[0].get("ok", true)), "infinite delta should fail", errors)
                var invalid_overlay_result: Dictionary = effects.add_effect("haste", self, 1, {"node": self})
                _assert_bool(not bool(invalid_overlay_result.get("ok", true)), "non-json overlay data should fail", errors)
                var string_schema_state: Dictionary = effects.apply_state({"schema_version": "1", "effects": []})
                _assert_bool(not bool(string_schema_state.get("ok", true)), "string schema_version should fail", errors)
                var invalid_state_data: Dictionary = effects.apply_state({"schema_version": 1, "effects": [{"effect_id": "poison", "stacks": 1, "remaining_duration": 1.0, "elapsed_time": 0.0, "tick_elapsed": 0.0, "data": {"node": self}}]})
                _assert_bool(not bool(invalid_state_data.get("ok", true)), "non-json saved effect data should fail", errors)
                var excessive_tick_state: Dictionary = effects.apply_state({"schema_version": 1, "effects": [{"effect_id": "poison", "stacks": 1, "remaining_duration": 1.0, "elapsed_time": 0.0, "tick_elapsed": 100.0, "data": {}}]})
                _assert_bool(not bool(excessive_tick_state.get("ok", true)), "excessive saved tick_elapsed should fail", errors)
                var no_tick_elapsed_state: Dictionary = effects.apply_state({"schema_version": 1, "effects": [{"effect_id": "haste", "stacks": 1, "remaining_duration": 1.0, "elapsed_time": 0.0, "tick_elapsed": 1.0, "data": {}}]})
                _assert_bool(not bool(no_tick_elapsed_state.get("ok", true)), "no-tick effect saved tick_elapsed should fail", errors)
                var timed_permanent_state: Dictionary = effects.apply_state({"schema_version": 1, "effects": [{"effect_id": "poison", "stacks": 1, "remaining_duration": -1.0, "elapsed_time": 0.0, "tick_elapsed": 0.0, "data": {}}]})
                _assert_bool(not bool(timed_permanent_state.get("ok", true)), "timed effect saved as permanent should fail", errors)
                var permanent_timed_state: Dictionary = effects.apply_state({"schema_version": 1, "effects": [{"effect_id": "shielded", "stacks": 1, "remaining_duration": 1.0, "elapsed_time": 0.0, "tick_elapsed": 0.0, "data": {}}]})
                _assert_bool(not bool(permanent_timed_state.get("ok", true)), "permanent effect saved as timed should fail", errors)
                var too_long_timed_state: Dictionary = effects.apply_state({"schema_version": 1, "effects": [{"effect_id": "poison", "stacks": 1, "remaining_duration": 6.0, "elapsed_time": 0.0, "tick_elapsed": 0.0, "data": {}}]})
                _assert_bool(not bool(too_long_timed_state.get("ok", true)), "timed effect saved beyond definition duration should fail", errors)

                return {
                    "ok": errors.is_empty(),
                    "errors": errors,
                    "add_haste": add_haste,
                    "refresh_haste": refresh_haste,
                    "haste_stacks": 1,
                    "add_poison": add_poison,
                    "poison_stacks": 3,
                    "tick_count": tick_count,
                    "has_haste_after_expire": has_haste_after_expire,
                    "has_shielded_after_update": has_shielded_after_update,
                    "apply_result": apply_result,
                    "float_schema_result": float_schema_result,
                    "round_trip_poison_stacks": 2,
                    "remove_one": remove_one,
                    "remove_all": remove_all,
                    "unknown_result": unknown_result,
                    "bad_stacks_result": bad_stacks_result,
                    "malformed_state": malformed_state,
                    "negative_delta_event": negative_delta_events[0],
                    "add_short_tick": add_short_tick,
                    "short_tick_events": short_tick_events,
                    "invalid_overlay_result": invalid_overlay_result,
                    "string_schema_state": string_schema_state,
                    "invalid_state_data": invalid_state_data,
                    "infinite_delta_event": infinite_delta_events[0] if not infinite_delta_events.is_empty() else {},
                    "excessive_tick_state": excessive_tick_state,
                    "no_tick_elapsed_state": no_tick_elapsed_state,
                    "timed_permanent_state": timed_permanent_state,
                    "permanent_timed_state": permanent_timed_state,
                    "too_long_timed_state": too_long_timed_state,
                }


            func _count_events(events: Array, event_type: String) -> int:
                var count := 0
                for event in events:
                    if String(event.get("type", "")) == event_type:
                        count += 1
                return count


            func _count_events_for_effect(events: Array, event_type: String, effect_id: String) -> int:
                var count := 0
                for event in events:
                    if String(event.get("type", "")) == event_type and String(event.get("effect_id", "")) == effect_id:
                        count += 1
                return count


            func _assert_bool(value: bool, message: String, errors: Array[String]) -> void:
                if not value:
                    errors.append(message)


            func _assert_int(expected: int, actual: int, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %d, got %d" % [label, expected, actual])


            func _assert_float(expected: float, actual: float, label: String, errors: Array[String]) -> void:
                if absf(expected - actual) > 0.001:
                    errors.append("%s: expected %.3f, got %.3f" % [label, expected, actual])
            """
        ),
        encoding="utf-8",
    )
    (scenes_dir / "effect_container_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=4 format=3]

            [ext_resource type="Script" path="res://scripts/effect_container_probe.gd" id="1_probe"]
            [ext_resource type="Script" path="res://addons/effects/effect_container.gd" id="2_container"]
            [ext_resource type="Resource" path="res://resources/effects_probe/effect_database.tres" id="3_database"]

            [node name="EffectContainerProbe" type="Node"]
            script = ExtResource("1_probe")

            [node name="EffectContainer" type="Node" parent="."]
            script = ExtResource("2_container")
            database = ExtResource("3_database")
            save_id = &"probe_effects"
            auto_update = false
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


def _write_inventory_state_probe(project: Path) -> None:
    (project / "scripts" / "inventory_state_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            const InventoryData := preload("res://addons/inventory/inventory.gd")
            const InventoryItemDefinitionData := preload("res://addons/inventory/inventory_item_definition.gd")
            const InventoryItemDatabaseData := preload("res://addons/inventory/inventory_item_database.gd")


            func run_probe() -> Dictionary:
                var errors: Array[String] = []
                var inventory = InventoryData.new()
                inventory.database = _make_database()
                inventory.capacity = 2
                inventory.save_id = &"state_probe_inventory"
                add_child(inventory)

                _assert_bool(inventory.is_in_group(&"save_participants"), "inventory with save_id should join save_participants", errors)
                _assert_string("state_probe_inventory", inventory.get_save_id(), "save id", errors)

                inventory.add_item("potion", 3)
                inventory.add_item("key", 1)
                var saved_state: Dictionary = inventory.get_state()
                _assert_int(1, int(saved_state.get("schema_version", -1)), "state schema version", errors)
                _assert_int(2, int(saved_state.get("capacity", -1)), "state capacity", errors)

                inventory.clear()
                inventory.add_item("potion", 1)
                var apply_result: Dictionary = inventory.apply_state(saved_state)
                _assert_bool(bool(apply_result.get("ok", false)), "apply_state should succeed", errors)
                _assert_int(3, inventory.get_quantity("potion"), "potion quantity after apply_state", errors)
                _assert_int(1, inventory.get_quantity("key"), "key quantity after apply_state", errors)

                inventory.clear()
                inventory.load_state(saved_state)
                _assert_int(3, inventory.get_quantity("potion"), "potion quantity after load_state", errors)
                _assert_int(1, inventory.get_quantity("key"), "key quantity after load_state", errors)
                _assert_int(3, int(inventory.save_state()["stacks"][0]["quantity"]), "save_state wrapper quantity", errors)

                var before_bad_state: Dictionary = inventory.get_state()
                var bad_quantity_state := {
                    "schema_version": 1,
                    "capacity": 2,
                    "stacks": [{"item_id": "potion", "quantity": 99}],
                }
                var bad_quantity_result: Dictionary = inventory.apply_state(bad_quantity_state)
                _assert_bool(not bool(bad_quantity_result.get("ok", true)), "too-large stack should fail", errors)
                _assert_contains(bad_quantity_result.get("errors", []), "exceeds max_stack", "too-large stack error", errors)
                _assert_int(3, inventory.get_quantity("potion"), "bad state should not mutate potion", errors)
                _assert_int(1, inventory.get_quantity("key"), "bad state should not mutate key", errors)

                var too_many_stacks_state := {
                    "schema_version": 1,
                    "capacity": 2,
                    "stacks": [
                        {"item_id": "potion", "quantity": 1},
                        {"item_id": "key", "quantity": 1},
                        {"item_id": "coin", "quantity": 1},
                    ],
                }
                var too_many_result: Dictionary = inventory.apply_state(too_many_stacks_state)
                _assert_bool(not bool(too_many_result.get("ok", true)), "too many stacks should fail", errors)
                _assert_contains(too_many_result.get("errors", []), "does not fit current capacity", "too many stacks error", errors)
                _assert_int(3, inventory.get_quantity("potion"), "too many stacks should not mutate potion", errors)

                var capacity_warning_state: Dictionary = before_bad_state.duplicate(true)
                inventory.capacity = 3
                var capacity_warning_result: Dictionary = inventory.apply_state(capacity_warning_state)
                _assert_bool(bool(capacity_warning_result.get("ok", false)), "capacity mismatch that still fits should succeed", errors)
                _assert_bool(not (capacity_warning_result.get("warnings", []) as Array).is_empty(), "capacity mismatch should warn", errors)

                _assert_error(inventory.apply_state({"schema_version": 99, "capacity": 3, "stacks": []}), "schema_version", "schema mismatch", errors)
                _assert_error(inventory.apply_state({"schema_version": 1, "capacity": 3, "stacks": [{"item_id": "missing", "quantity": 1}]}), "Unknown item_id", "unknown saved item", errors)
                _assert_error(inventory.apply_state({"schema_version": 1, "capacity": 3, "stacks": [{"item_id": "potion", "quantity": 0}]}), "positive", "non-positive saved quantity", errors)

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

                var coin = InventoryItemDefinitionData.new()
                coin.item_id = &"coin"
                coin.display_name = "Coin"
                coin.max_stack = 99

                var database = InventoryItemDatabaseData.new()
                database.items.append(potion)
                database.items.append(key)
                database.items.append(coin)
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


            func _assert_string(expected: String, actual: String, label: String, errors: Array[String]) -> void:
                if expected != actual:
                    errors.append("%s: expected %s, got %s" % [label, expected, actual])


            func _assert_contains(messages: Array, needle: String, label: String, errors: Array[String]) -> void:
                for message in messages:
                    if String(message).contains(needle):
                        return
                errors.append("%s: missing %s in %s" % [label, needle, str(messages)])
            """
        ),
        encoding="utf-8",
    )
    (project / "scenes" / "inventory_state_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Script" path="res://scripts/inventory_state_probe.gd" id="1_probe_script"]

            [node name="InventoryStateProbe" type="Node"]
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


def _write_state_machine_runtime_probe(project: Path) -> None:
    scripts_dir = project / "scripts"
    scenes_dir = project / "scenes"
    scripts_dir.mkdir(exist_ok=True)
    scenes_dir.mkdir(exist_ok=True)
    (scripts_dir / "state_machine_probe.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            @onready var machine: Node = $StateMachine

            var transition_history: Array[String] = []
            var reentrant_result: Dictionary = {}
            var guard_reentrant_result: Dictionary = {}


            func _ready() -> void:
                machine.state_changed.connect(_on_state_changed)


            func run_state_machine_probe() -> Dictionary:
                var initial_state := String(machine.call("get_current_state_id"))
                var state_ids: Array = machine.call("get_state_ids")
                var move_result: Dictionary = machine.call("transition_to", "move", {"speed": 4})
                var attack_result: Dictionary = machine.call("get_current_state").call("request_attack")
                var forbidden_result: Dictionary = machine.call("transition_to", "forbidden")
                var snapshot: Dictionary = machine.call("get_state")
                var idle_result: Dictionary = machine.call("transition_to", "idle")
                var restore_result: Dictionary = machine.call("apply_state", snapshot)
                var restored_state := String(machine.call("get_current_state_id"))
                var transition_history_before_reentrant := transition_history.duplicate()
                var reentrant_transition: Dictionary = machine.call("transition_to", "reentrant")
                var duplicate_result: Dictionary = _run_duplicate_id_probe()
                var ok := initial_state == "idle"
                ok = ok and bool(move_result.get("ok", false))
                ok = ok and bool(attack_result.get("ok", false))
                ok = ok and not bool(forbidden_result.get("ok", true))
                ok = ok and bool(idle_result.get("ok", false))
                ok = ok and bool(restore_result.get("ok", false))
                ok = ok and bool(reentrant_transition.get("ok", false))
                ok = ok and not bool(reentrant_result.get("ok", true))
                ok = ok and not bool(duplicate_result.get("ok", true))
                return {
                    "ok": ok,
                    "initial_state": initial_state,
                    "state_ids": state_ids,
                    "move_result": move_result,
                    "attack_result": attack_result,
                    "forbidden_result": forbidden_result,
                    "guard_reentrant_result": guard_reentrant_result,
                    "snapshot": snapshot,
                    "idle_result": idle_result,
                    "restore_result": restore_result,
                    "restored_state": restored_state,
                    "reentrant_transition": reentrant_transition,
                    "reentrant_result": reentrant_result,
                    "duplicate_result": duplicate_result,
                    "transition_history": transition_history_before_reentrant,
                }


            func _run_duplicate_id_probe() -> Dictionary:
                var machine_script = load("res://addons/state_machine/state_machine.gd")
                var state_script = load("res://addons/state_machine/state.gd")
                var duplicate_machine: Node = machine_script.new()
                duplicate_machine.set("auto_start", false)
                var state_a: Node = state_script.new()
                state_a.name = "FirstDup"
                state_a.set("state_id", &"dup")
                var state_b: Node = state_script.new()
                state_b.name = "SecondDup"
                state_b.set("state_id", &"dup")
                duplicate_machine.add_child(state_a)
                duplicate_machine.add_child(state_b)
                add_child(duplicate_machine)
                return duplicate_machine.call("start")


            func _on_state_changed(previous_state_id: String, current_state_id: String, data: Dictionary) -> void:
                transition_history.append("%s>%s" % [previous_state_id, current_state_id])
            """
        ),
        encoding="utf-8",
    )
    (scripts_dir / "state_machine_probe_idle.gd").write_text(
        textwrap.dedent(
            """\
            extends "res://addons/state_machine/state.gd"

            var enter_count: int = 0


            func enter(previous_state: Node, data: Dictionary) -> void:
                enter_count += 1
            """
        ),
        encoding="utf-8",
    )
    (scripts_dir / "state_machine_probe_move.gd").write_text(
        textwrap.dedent(
            """\
            extends "res://addons/state_machine/state.gd"

            var last_speed: int = 0


            func enter(previous_state: Node, data: Dictionary) -> void:
                last_speed = int(data.get("speed", 0))


            func request_attack() -> Dictionary:
                return get_parent().call("request_transition", "attack", {"source": "move"})
            """
        ),
        encoding="utf-8",
    )
    (scripts_dir / "state_machine_probe_attack.gd").write_text(
        textwrap.dedent(
            """\
            extends "res://addons/state_machine/state.gd"

            var entered_from: String = ""


            func enter(previous_state: Node, data: Dictionary) -> void:
                if previous_state != null:
                    entered_from = String(previous_state.name)
            """
        ),
        encoding="utf-8",
    )
    (scripts_dir / "state_machine_probe_forbidden.gd").write_text(
        textwrap.dedent(
            """\
            extends "res://addons/state_machine/state.gd"


            func can_enter(previous_state: Node, data: Dictionary) -> bool:
                get_parent().get_parent().set("guard_reentrant_result", get_parent().call("request_transition", "idle"))
                return false
            """
        ),
        encoding="utf-8",
    )
    (scripts_dir / "state_machine_probe_reentrant.gd").write_text(
        textwrap.dedent(
            """\
            extends "res://addons/state_machine/state.gd"


            func enter(previous_state: Node, data: Dictionary) -> void:
                get_parent().get_parent().set("reentrant_result", get_parent().call("request_transition", "idle"))
            """
        ),
        encoding="utf-8",
    )
    (scenes_dir / "state_machine_probe.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene load_steps=8 format=3]

            [ext_resource type="Script" path="res://scripts/state_machine_probe.gd" id="1_root"]
            [ext_resource type="Script" path="res://addons/state_machine/state_machine.gd" id="2_machine"]
            [ext_resource type="Script" path="res://scripts/state_machine_probe_idle.gd" id="3_idle"]
            [ext_resource type="Script" path="res://scripts/state_machine_probe_move.gd" id="4_move"]
            [ext_resource type="Script" path="res://scripts/state_machine_probe_attack.gd" id="5_attack"]
            [ext_resource type="Script" path="res://scripts/state_machine_probe_forbidden.gd" id="6_forbidden"]
            [ext_resource type="Script" path="res://scripts/state_machine_probe_reentrant.gd" id="7_reentrant"]

            [node name="StateMachineProbe" type="Node"]
            script = ExtResource("1_root")

            [node name="StateMachine" type="Node" parent="."]
            script = ExtResource("2_machine")
            initial_state_id = &"idle"
            auto_start = true

            [node name="Idle" type="Node" parent="StateMachine"]
            script = ExtResource("3_idle")
            state_id = &"idle"

            [node name="Move" type="Node" parent="StateMachine"]
            script = ExtResource("4_move")
            state_id = &"move"

            [node name="Attack" type="Node" parent="StateMachine"]
            script = ExtResource("5_attack")
            state_id = &"attack"

            [node name="Forbidden" type="Node" parent="StateMachine"]
            script = ExtResource("6_forbidden")
            state_id = &"forbidden"

            [node name="Reentrant" type="Node" parent="StateMachine"]
            script = ExtResource("7_reentrant")
            state_id = &"reentrant"
            """
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()

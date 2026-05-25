from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from godot_playwright.install import bundled_addon_path, enable_autoload, enable_editor_plugin, install_addon
from godot_playwright.project import ProjectError, init_project


class InstallTests(unittest.TestCase):
    def test_enable_editor_plugin_adds_section(self) -> None:
        text = "config_version=5\n"
        result = enable_editor_plugin(text)
        self.assertIn("[editor_plugins]", result)
        self.assertIn('res://addons/godot_playwright/plugin.cfg', result)

    def test_enable_editor_plugin_is_idempotent(self) -> None:
        text = enable_editor_plugin("config_version=5\n")
        self.assertEqual(text, enable_editor_plugin(text))

    def test_enable_autoload_upserts(self) -> None:
        text = enable_autoload("config_version=5\n")
        text = enable_autoload(text)
        self.assertEqual(text.count("GodotPlaywright="), 1)
        self.assertIn("*res://addons/godot_playwright/runtime_autoload.gd", text)

    def test_install_addon_copies_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            target = install_addon(project, autoload=True)
            self.assertTrue((target / "plugin.cfg").exists())
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertIn("[editor_plugins]", project_text)
            self.assertIn("[autoload]", project_text)

    def test_bundled_addon_path_is_packaged(self) -> None:
        addon = bundled_addon_path()
        self.assertTrue((addon / "plugin.cfg").exists())
        self.assertTrue((addon / "plugin.gd").exists())
        self.assertTrue((addon / "runtime_autoload.gd").exists())
        self.assertTrue((addon / "godot_playwright_server.gd").exists())

    def test_init_project_creates_automation_ready_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = init_project(Path(tmp) / "game", name="Agent Game")
            self.assertTrue((project / "project.godot").exists())
            self.assertTrue((project / "scenes" / "main.tscn").exists())
            self.assertTrue((project / "scripts" / "main.gd").exists())
            self.assertTrue((project / "addons" / "godot_playwright" / "plugin.cfg").exists())
            project_text = (project / "project.godot").read_text(encoding="utf-8")
            self.assertIn('config/name="Agent Game"', project_text)
            self.assertIn("[autoload]", project_text)
            scene_text = (project / "scenes" / "main.tscn").read_text(encoding="utf-8")
            self.assertIn('metadata/test_id = "counter-button"', scene_text)

    def test_init_project_rejects_non_empty_directory_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "existing.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(ProjectError):
                init_project(project)


if __name__ == "__main__":
    unittest.main()

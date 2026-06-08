from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from godot_playwright.process import isolated_godot_env


class ProcessEnvTests(unittest.TestCase):
    def test_isolated_godot_env_assigns_port_and_xdg_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = isolated_godot_env(
                host="127.0.0.1",
                port=0,
                strict_port=False,
                base_dir=tmp,
                namespace="probe main",
            )

            self.assertEqual(env["GODOT_PLAYWRIGHT_HOST"], "127.0.0.1")
            self.assertEqual(env["GODOT_PLAYWRIGHT_PORT"], "0")
            self.assertEqual(env["GODOT_PLAYWRIGHT_STRICT_PORT"], "0")
            self.assertTrue(Path(env["GODOT_PLAYWRIGHT_RUNTIME_DIR"]).is_dir())
            self.assertTrue(Path(env["XDG_DATA_HOME"]).is_dir())
            self.assertTrue(Path(env["XDG_CONFIG_HOME"]).is_dir())
            self.assertTrue(Path(env["XDG_CACHE_HOME"]).is_dir())
            self.assertTrue(Path(env["XDG_STATE_HOME"]).is_dir())
            self.assertTrue(Path(env["XDG_RUNTIME_DIR"]).is_dir())
            self.assertIn("probe-main", Path(env["GODOT_PLAYWRIGHT_RUNTIME_DIR"]).name)

    def test_isolated_godot_env_links_existing_export_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "data-home" / "godot" / "export_templates"
            source.mkdir(parents=True)

            with mock.patch.dict("os.environ", {"XDG_DATA_HOME": str(root / "data-home")}):
                env = isolated_godot_env(base_dir=root / "runtime", namespace="export")

            linked = Path(env["XDG_DATA_HOME"]) / "godot" / "export_templates"
            self.assertTrue(linked.exists())
            self.assertEqual(linked.resolve(), source.resolve())


if __name__ == "__main__":
    unittest.main()

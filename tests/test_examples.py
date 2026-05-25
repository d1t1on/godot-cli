from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from godot_playwright.validate import validate_project


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class ExampleProjectValidationTests(unittest.TestCase):
    def test_agent_workspace_validates_as_second_project_shape(self) -> None:
        source = ROOT / "examples" / "agent_workspace"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "agent_workspace"
            shutil.copytree(source, project)
            report = validate_project(
                project,
                exclude=["addons/**"],
                frames=1,
                artifacts_dir=Path(tmp) / "report",
                timeout=30,
            )

        self.assertTrue(report["ok"], report["diagnostics"])
        self.assertEqual(report["passed"], 5)
        self.assertEqual(report["failed"], 0)
        inventory = report["checks"]["inventory"]
        self.assertEqual(inventory["autoload_count"], 2)
        self.assertEqual(inventory["files"]["script_count"], 4)
        self.assertEqual(inventory["files"]["scene_count"], 3)
        self.assertEqual(inventory["files"]["resource_count"], 1)
        self.assertGreaterEqual(inventory["files"]["scale"]["directory_count"], 7)
        self.assertEqual(report["checks"]["scripts"]["passed"], 4)
        self.assertEqual(report["checks"]["resources"]["passed"], 4)
        self.assertEqual(report["checks"]["scene_inspect"]["passed"], 3)
        self.assertEqual(report["checks"]["runtime"]["passed"], 3)


if __name__ == "__main__":
    unittest.main()

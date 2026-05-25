from __future__ import annotations

import base64
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from godot_playwright import Godot
from godot_playwright.export import export_project
from godot_playwright.project import init_project
from godot_playwright.validate import validate_project


PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class ExternalProjectEvidenceTests(unittest.TestCase):
    def test_generated_external_project_validates_doctors_and_export_preflights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "external_project", name="External Scale Probe")
            _write_external_project_fixture(project)

            report = validate_project(
                project,
                exclude=["addons/**"],
                frames=2,
                artifacts_dir=root / "validate-report",
                timeout=45,
            )

            self.assertTrue(report["ok"], report["diagnostics"])
            self.assertEqual(report["passed"], 5)
            inventory = report["checks"]["inventory"]
            files = inventory["files"]
            self.assertGreaterEqual(files["count"], 35)
            self.assertGreaterEqual(files["asset_count"], 12)
            self.assertGreaterEqual(files["resource_count"], 12)
            self.assertGreaterEqual(files["scene_count"], 6)
            self.assertGreaterEqual(files["scale"]["directory_count"], 7)
            self.assertEqual(inventory["export_presets"]["count"], 1)
            self.assertEqual(report["checks"]["scripts"]["passed"], 3)
            self.assertGreaterEqual(report["checks"]["resources"]["passed"], 18)
            self.assertGreaterEqual(report["checks"]["scene_inspect"]["passed"], 6)
            self.assertGreaterEqual(report["checks"]["runtime"]["passed"], 6)

            with Godot(project, mode="runtime", timeout=30, stdout=None) as godot:
                doctor = godot.project_doctor(max_results=80, include_protocol_methods=True)

            self.assertTrue(doctor["ok"], doctor["diagnostics"])
            self.assertEqual(doctor["status"], "ready")
            self.assertGreaterEqual(doctor["project_summary"]["counts"]["imports"], 12)
            self.assertIn("project.doctor", {entry["method"] for entry in doctor["protocol"]["methods"]})

            export = export_project(
                project,
                "Agent Linux Pack",
                "build/external_scale.pck",
                mode="pack",
                timeout=45,
            )
            self.assertTrue(export["preset_found"])
            self.assertEqual(export["preset_export_path"], "build/external_scale.pck")
            self.assertTrue(export["output_matches_preset"])
            self.assertEqual(export["output_relative_path"], "build/external_scale.pck")
            self.assertIn("--export-pack", export["command"])
            self.assertTrue(Path(export["log_path"]).exists())
            if export["ok"]:
                self.assertTrue(export["output_exists"])
                self.assertTrue(export["output_changed"])
            else:
                self.assertTrue(export["stdout_tail"] or export["diagnostics"])


def _write_external_project_fixture(project: Path) -> None:
    (project / "assets" / "icons").mkdir(parents=True, exist_ok=True)
    (project / "resources" / "items").mkdir(parents=True, exist_ok=True)
    (project / "scenes" / "generated").mkdir(parents=True, exist_ok=True)
    (project / "scripts" / "systems").mkdir(parents=True, exist_ok=True)

    (project / "scripts" / "systems" / "scale_state.gd").write_text(
        textwrap.dedent(
            """\
            extends Node

            var loaded_items := 0


            func register_item() -> void:
            \tloaded_items += 1
            """
        ),
        encoding="utf-8",
    )
    project_file = project / "project.godot"
    project_text = project_file.read_text(encoding="utf-8")
    project_text = project_text.replace(
        "[autoload]\n\n",
        '[autoload]\n\nScaleState="*res://scripts/systems/scale_state.gd"\n',
    )
    project_file.write_text(project_text, encoding="utf-8")

    for index in range(12):
        (project / "assets" / "icons" / f"pixel_{index}.png").write_bytes(PIXEL_PNG)
        (project / "resources" / "items" / f"item_{index}.tres").write_text(
            textwrap.dedent(
                f"""\
                [gd_resource type="Resource" format=3]

                [resource]
                resource_name = "Item{index}"
                metadata/icon_path = "res://assets/icons/pixel_{index}.png"
                metadata/test_id = "item-{index}"
                """
            ),
            encoding="utf-8",
        )

    for index in range(4):
        (project / "scenes" / "generated" / f"arena_{index}.tscn").write_text(
            textwrap.dedent(
                f"""\
                [gd_scene format=3]

                [node name="Arena{index}" type="Node2D"]
                metadata/test_id = "arena-{index}"

                [node name="Marker{index}" type="Label" parent="."]
                text = "Arena {index}"
                metadata/test_id = "arena-marker-{index}"
                """
            ),
            encoding="utf-8",
        )

    (project / "export_presets.cfg").write_text(
        textwrap.dedent(
            """\
            [preset.0]
            name="Agent Linux Pack"
            platform="Linux"
            runnable=false
            export_filter="all_resources"
            export_path="build/external_scale.pck"

            [preset.0.options]
            binary_format/embed_pck=false
            """
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()

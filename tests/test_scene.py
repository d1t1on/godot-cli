from __future__ import annotations

import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from godot_playwright.cli import main as cli_main
from godot_playwright.scene import SceneInspectError, expect_scene_file, inspect_project_scenes, inspect_scene


class SceneInspectTests(unittest.TestCase):
    def test_inspect_scene_parses_nodes_properties_and_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "scenes").mkdir(parents=True)
            (project / "scripts").mkdir()
            (project / "scripts" / "main.gd").write_text("extends Control\n", encoding="utf-8")
            (project / "scenes" / "badge.tscn").write_text(
                '[gd_scene format=3]\n\n[node name="Badge" type="Label"]\n',
                encoding="utf-8",
            )
            (project / "scenes" / "main.tscn").write_text(
                textwrap.dedent(
                    """\
                    [gd_scene load_steps=4 format=3 uid="uid://main"]

                    [ext_resource type="Script" uid="uid://script" path="res://scripts/main.gd" id="1_main"]
                    [ext_resource type="PackedScene" path="res://scenes/badge.tscn" id="2_badge"]

                    [sub_resource type="LabelSettings" id="LabelSettings_title"]
                    font_size = 24

                    [node name="Main" type="Control"]
                    script = ExtResource("1_main")
                    metadata/test_id = "main"

                    [node name="Panel" type="VBoxContainer" parent="." groups=["agent_generated"]]
                    visible = true

                    [node name="Title" type="Label" parent="./Panel"]
                    text = "Godot Playwright"
                    label_settings = SubResource("LabelSettings_title")
                    offset_left = 24.0
                    modulate = Color(0.2, 0.4, 0.8, 1)

                    [node name="BadgeInstance" parent="Panel" instance=ExtResource("2_badge")]

                    [connection signal="pressed" from="Panel/BadgeInstance" to="." method="_on_badge_pressed"]
                    """
                ),
                encoding="utf-8",
            )

            report = inspect_scene(project, "res://scenes/main.tscn")

            self.assertTrue(report["ok"])
            self.assertEqual(report["header"]["format"], 3)
            self.assertEqual(report["header"]["uid"], "uid://main")
            self.assertEqual(report["node_count"], 4)
            self.assertEqual(report["root"]["name"], "Main")
            self.assertEqual(report["root"]["properties"]["metadata/test_id"], "main")
            self.assertEqual(report["root"]["properties"]["script"]["path"], "res://scripts/main.gd")
            title = next(node for node in report["nodes"] if node["name"] == "Title")
            self.assertEqual(title["path"], "/Main/Panel/Title")
            self.assertEqual(title["properties"]["text"], "Godot Playwright")
            self.assertEqual(title["properties"]["label_settings"]["resource_type"], "LabelSettings")
            self.assertEqual(title["properties"]["modulate"]["$type"], "Color")
            badge = next(node for node in report["nodes"] if node["name"] == "BadgeInstance")
            self.assertEqual(badge["instance"]["path"], "res://scenes/badge.tscn")
            panel = next(node for node in report["nodes"] if node["name"] == "Panel")
            self.assertEqual(panel["groups"], ["agent_generated"])
            self.assertEqual(report["ext_resources"][0]["exists"], True)
            self.assertEqual(report["sub_resources"][0]["properties"]["font_size"], 24)
            self.assertEqual(report["connections"][0]["method"], "_on_badge_pressed")

            scene = expect_scene_file(project, "res://scenes/main.tscn")
            scene.to_exist(timeout=0.1)
            scene.to_be_valid(timeout=0.1)
            scene.to_have_root(name="Main", class_name="Control", properties={"metadata/test_id": "main"}, timeout=0.1)
            scene.to_have_node(path="/Main/Panel", class_name="VBoxContainer", groups=["agent_generated"], timeout=0.1)
            scene.to_have_node(
                name="Main",
                script="res://scripts/main.gd",
                properties={"metadata/test_id": "main"},
                timeout=0.1,
            )
            scene.to_have_node(
                name="BadgeInstance",
                instance_path="res://scenes/badge.tscn",
                timeout=0.1,
            )
            scene.to_have_node_count(1, class_name="Label", properties={"text": "Godot Playwright"}, timeout=0.1)
            scene.to_have_ext_resource(path="res://scripts/main.gd", resource_type="Script", timeout=0.1)
            scene.to_have_connection(
                "pressed",
                from_node="Panel/BadgeInstance",
                to=".",
                method="_on_badge_pressed",
                timeout=0.1,
            )
            scene.not_to_have_node(name="Missing", timeout=0.1)
            with self.assertRaisesRegex(AssertionError, "Missing"):
                scene.to_have_node(name="Missing", timeout=0.01, interval=0.001)

    def test_inspect_scene_reports_missing_and_orphan_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "scenes").mkdir(parents=True)
            (project / "scenes" / "broken.tscn").write_text(
                textwrap.dedent(
                    """\
                    [gd_scene format=3]

                    [node name="Main" type="Node"]
                    [node name="Orphan" type="Node" parent="Missing"]
                    """
                ),
                encoding="utf-8",
            )

            report = inspect_scene(project, "res://scenes/broken.tscn")

            self.assertFalse(report["ok"])
            self.assertEqual(report["diagnostics"][0]["kind"], "ORPHAN_SCENE_NODE")
            with self.assertRaises(SceneInspectError):
                inspect_scene(project, "res://scenes/broken.tscn", check=True)
            with self.assertRaises(SceneInspectError):
                inspect_scene(project, "res://scenes/missing.tscn", check=True)

    def test_inspect_project_scenes_discovers_and_aggregates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "scenes").mkdir(parents=True)
            (project / "addons").mkdir()
            (project / "scenes" / "ok.tscn").write_text(
                '[gd_scene format=3]\n\n[node name="Ok" type="Node"]\n',
                encoding="utf-8",
            )
            (project / "scenes" / "bad.tscn").write_text(
                '[gd_scene format=3]\n\n[node name="Bad" type="Node"]\n[node name="Orphan" type="Node" parent="Missing"]\n',
                encoding="utf-8",
            )
            (project / "addons" / "ignored.tscn").write_text(
                '[gd_scene format=3]\n\n[node name="Ignored" type="Node"]\n[node name="Orphan" type="Node" parent="Missing"]\n',
                encoding="utf-8",
            )

            report = inspect_project_scenes(project, ["res://scenes", "res://addons"], exclude=["addons/**"])

            self.assertFalse(report["ok"])
            self.assertEqual(report["scene_count"], 2)
            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["diagnostics"][0]["scene"], "res://scenes/bad.tscn")
            with self.assertRaises(SceneInspectError):
                inspect_project_scenes(project, ["res://scenes"], check=True)

    def test_cli_inspect_scene_invokes_parser(self) -> None:
        report = {
            "ok": True,
            "scene": "res://scenes/main.tscn",
            "root": {"name": "Main", "class": "Control"},
            "node_count": 1,
            "ext_resource_count": 0,
            "sub_resource_count": 0,
            "connection_count": 0,
            "duration_ms": 1.0,
            "nodes": [{"path": "/Main", "class": "Control", "property_count": 0}],
            "diagnostics": [],
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.inspect_scene", return_value=report) as inspect:
            with redirect_stdout(stdout):
                code = cli_main(["inspect-scene", "/tmp/project", "res://scenes/main.tscn", "--no-properties"])

        self.assertEqual(code, 0)
        self.assertIn("PASS scene res://scenes/main.tscn", stdout.getvalue())
        inspect.assert_called_once()
        self.assertEqual(inspect.call_args.args[:2], ("/tmp/project", "res://scenes/main.tscn"))
        self.assertFalse(inspect.call_args.kwargs["include_properties"])


if __name__ == "__main__":
    unittest.main()

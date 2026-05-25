from __future__ import annotations

import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from godot_playwright.cli import main as cli_main
from godot_playwright.locator_index import find_project_nodes


class ProjectNodeQueryTests(unittest.TestCase):
    def test_find_project_nodes_matches_static_locator_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _write_project(Path(tmp))

            button_report = find_project_nodes(
                project,
                ["res://scenes/main.tscn"],
                role="button",
                role_name="Play",
            )

            self.assertTrue(button_report["ok"])
            self.assertEqual(button_report["match_count"], 1)
            button = button_report["matches"][0]
            self.assertEqual(button["name"], "PlayButton")
            self.assertEqual(button["role"], "button")
            self.assertEqual(button["test_id"], "counter-button")
            self.assertNotIn("properties", button)

            test_id_report = find_project_nodes(project, test_id="counter-button")
            self.assertEqual(test_id_report["match_count"], 1)
            self.assertEqual(test_id_report["matches"][0]["path"], "/Main/PlayButton")

            text_report = find_project_nodes(project, selector="text*=Pla")
            self.assertEqual(
                [node["name"] for node in text_report["matches"]],
                ["PlayButton", "Title"],
            )

            metadata_report = find_project_nodes(project, selector={"metadata": {"test_id": "counter-button"}})
            self.assertEqual(metadata_report["match_count"], 1)
            self.assertEqual(metadata_report["matches"][0]["name"], "PlayButton")

            property_report = find_project_nodes(project, property_name="placeholder_text", property_value="Name")
            self.assertEqual(property_report["match_count"], 1)
            self.assertEqual(property_report["matches"][0]["name"], "NameInput")

    def test_find_project_nodes_can_include_properties(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _write_project(Path(tmp))

            report = find_project_nodes(project, test_id="counter-button", include_properties=True)

            self.assertEqual(report["match_count"], 1)
            self.assertEqual(report["matches"][0]["properties"]["text"], "Play")
            self.assertEqual(report["matches"][0]["properties"]["metadata/test_id"], "counter-button")

    def test_cli_find_nodes_invokes_query(self) -> None:
        report = {
            "ok": True,
            "project": "/tmp/project",
            "query": {"role": "button", "test_id": "counter-button"},
            "scene_count": 1,
            "node_count": 4,
            "match_count": 1,
            "matches": [
                {
                    "scene": "res://scenes/main.tscn",
                    "path": "/Main/PlayButton",
                    "name": "PlayButton",
                    "class": "Button",
                    "role": "button",
                    "test_id": "counter-button",
                    "accessible_names": ["Play", "PlayButton"],
                }
            ],
            "diagnostics": [],
            "diagnostic_count": 0,
            "duration_ms": 1.0,
        }
        stdout = StringIO()
        with mock.patch("godot_playwright.cli.find_project_nodes", return_value=report) as find:
            with redirect_stdout(stdout):
                code = cli_main(
                    [
                        "find-nodes",
                        "/tmp/project",
                        "res://scenes",
                        "--role",
                        "button",
                        "--test-id",
                        "counter-button",
                        "--limit",
                        "1",
                    ]
                )

        self.assertEqual(code, 0)
        self.assertIn("PASS node query 1/4 nodes matched", stdout.getvalue())
        find.assert_called_once()
        self.assertEqual(find.call_args.args[:2], ("/tmp/project", ["res://scenes"]))
        self.assertEqual(find.call_args.kwargs["role"], "button")
        self.assertEqual(find.call_args.kwargs["test_id"], "counter-button")
        self.assertEqual(find.call_args.kwargs["limit"], 1)


def _write_project(root: Path) -> Path:
    project = root / "project"
    (project / "scenes").mkdir(parents=True)
    (project / "scenes" / "main.tscn").write_text(
        textwrap.dedent(
            """\
            [gd_scene format=3]

            [node name="Main" type="Control"]
            metadata/test_id = "main"

            [node name="PlayButton" type="Button" parent="."]
            text = "Play"
            tooltip_text = "Start game"
            metadata/test_id = "counter-button"

            [node name="NameInput" type="LineEdit" parent="."]
            placeholder_text = "Name"
            metadata/test_id = "name-input"

            [node name="Title" type="Label" parent="."]
            text = "Play"

            [node name="ThemeSelect" type="OptionButton" parent="."]
            metadata/test_id = "theme-select"

            [node name="Volume" type="HSlider" parent="."]
            value = 50.0
            """
        ),
        encoding="utf-8",
    )
    return project


if __name__ == "__main__":
    unittest.main()

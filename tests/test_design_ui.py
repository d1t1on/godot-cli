from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from godot_playwright.design_ui import (
    DesignUISpecError,
    compile_design_spec,
    generate_design_ui,
    review_compiled_design,
)
from godot_playwright.project import init_project


def _find_node(tree: list[dict[str, object]], design_id: str) -> dict[str, object]:
    for node in tree:
        metadata = node.get("metadata", {})
        if isinstance(metadata, dict) and metadata.get("design_id") == design_id:
            return node
        children = node.get("children", [])
        if isinstance(children, list):
            try:
                return _find_node(children, design_id)
            except AssertionError:
                pass
    raise AssertionError(f"node {design_id!r} not found")


class FakeDesignLocator:
    def __init__(self, design_id: str, bounds: dict[str, object], minimum_size: tuple[float, float] | None = None) -> None:
        self.design_id = design_id
        self._bounds = bounds
        self._minimum_size = minimum_size

    def bounds(self) -> dict[str, object]:
        return self._bounds

    def evaluate(self, expression: str):  # type: ignore[no-untyped-def]
        if expression == "node.get_minimum_size()" and self._minimum_size is not None:
            return {"$type": "Vector2", "x": self._minimum_size[0], "y": self._minimum_size[1]}
        return {"$type": "Vector2", "x": 0, "y": 0}


class FakeDesignClient:
    def __init__(self) -> None:
        self.bounds = {
            "play": {"rect": {"x": 0, "y": 0, "width": 40, "height": 40}},
            "quit": {"rect": {"x": 20, "y": 0, "width": 40, "height": 40}},
        }

    def set_viewport_size(self, width: int, height: int) -> dict[str, object]:
        return {"window_size": {"width": width, "height": height}}

    def wait_for_viewport_size(self, width: int, height: int, **kwargs):  # type: ignore[no-untyped-def]
        return {"window_size": {"width": width, "height": height}, "visible_rect": {"x": 0, "y": 0, "width": width, "height": height}}

    def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
        return {"name": "GeneratedUi", "children": []}

    def screenshot(self, path: Path) -> dict[str, object]:
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        return {"path": str(path), "width": 50, "height": 40}

    def locator(self, selector, root=None):  # type: ignore[no-untyped-def]
        design_id = selector["metadata"]["design_id"]
        minimum_size = (80, 20) if design_id == "play" else None
        return FakeDesignLocator(design_id, self.bounds[design_id], minimum_size)


class DesignUiTests(unittest.TestCase):
    def test_compile_expands_tokens_components_and_node_tree(self) -> None:
        spec = {
            "schema_version": 1,
            "name": "MainMenuHud",
            "target": {"scene": "res://scenes/ui/main_menu_hud.tscn"},
            "tokens": {
                "colors": {"surface": "#141418", "text": "#f7f7fb", "primary": "#ffcc00"},
                "spacing": {"md": 12, "lg": 24},
                "font_sizes": {"title": 32, "body": 16},
                "radii": {"panel": 8},
            },
            "components": {
                "menu_button": {
                    "base": {
                        "type": "button",
                        "size": [220, 52],
                        "style": {"font_color": "$colors.text", "font_size": "$font_sizes.body"},
                    },
                    "variants": {
                        "primary": {"style": {"font_color": "$colors.primary"}},
                    },
                }
            },
            "root": {
                "type": "screen",
                "id": "main_screen",
                "style": {"background": "$colors.surface"},
                "children": [
                    {
                        "type": "panel",
                        "id": "menu_panel",
                        "style": {"background": "$colors.surface", "radius": "$radii.panel", "padding": "$spacing.lg"},
                        "children": [
                            {
                                "type": "stack",
                                "id": "menu_stack",
                                "layout": {"direction": "vertical", "gap": "$spacing.md"},
                                "children": [
                                    {"type": "text", "id": "title", "text": "Start", "font_size": "$font_sizes.title"},
                                    {"type": "instance", "component": "menu_button", "variant": "primary", "id": "play", "text": "Play"},
                                ],
                            }
                        ],
                    },
                    {"type": "meter", "id": "health", "value": 75, "max": 100, "size": [180, 18]},
                ],
            },
            "review": {"viewports": ["900x600"]},
        }

        compiled = compile_design_spec(spec)

        self.assertEqual(compiled.scene_path, "res://scenes/ui/main_menu_hud.tscn")
        self.assertEqual(compiled.root_class, "Panel")
        self.assertEqual(compiled.root_metadata["design_id"], "main_screen")
        self.assertEqual(compiled.viewports, [(900, 600)])
        self.assertEqual(compiled.node_count, 5)
        play = _find_node(compiled.node_tree, "play")
        self.assertEqual(play["class"], "Button")
        self.assertEqual(play["properties"]["text"], "Play")
        self.assertEqual(play["properties"]["size"], {"$type": "Vector2", "x": 220.0, "y": 52.0})
        self.assertEqual(play["properties"]["custom_minimum_size"], {"$type": "Vector2", "x": 220.0, "y": 52.0})
        self.assertEqual(play["metadata"]["test_id"], "play")
        self.assertIn("theme_override_colors/font_color", play["properties"])
        panel = _find_node(compiled.node_tree, "menu_panel")
        self.assertIn("theme_override_styles/panel", panel["properties"])
        health = _find_node(compiled.node_tree, "health")
        self.assertEqual(health["class"], "ProgressBar")
        self.assertEqual(health["properties"]["size"], {"$type": "Vector2", "x": 180.0, "y": 18.0})

    def test_compile_distinguishes_explicit_size_from_min_size(self) -> None:
        spec = {
            "name": "Sizing",
            "root": {
                "type": "screen",
                "children": [
                    {"type": "button", "id": "fixed", "text": "Fixed", "size": [120, 48], "min_size": [90, 44]},
                    {"type": "button", "id": "minimum", "text": "Minimum", "min_size": [90, 44]},
                ],
            },
        }

        compiled = compile_design_spec(spec)
        fixed = _find_node(compiled.node_tree, "fixed")
        minimum = _find_node(compiled.node_tree, "minimum")

        self.assertEqual(fixed["properties"]["size"], {"$type": "Vector2", "x": 120.0, "y": 48.0})
        self.assertEqual(fixed["properties"]["custom_minimum_size"], {"$type": "Vector2", "x": 90.0, "y": 44.0})
        self.assertNotIn("size", minimum["properties"])
        self.assertEqual(minimum["properties"]["custom_minimum_size"], {"$type": "Vector2", "x": 90.0, "y": 44.0})

    def test_compile_reports_missing_assets_and_rejects_bad_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            spec = {
                "name": "Inventory",
                "target": {"scene": "res://scenes/ui/inventory.tscn"},
                "root": {"type": "screen", "children": [{"type": "image", "id": "portrait", "asset": "res://assets/portrait.png"}]},
            }

            compiled = compile_design_spec(spec, project=project)

        self.assertEqual(compiled.issues[0]["code"], "missing_asset")

        bad_token = {
            "name": "BadToken",
            "tokens": {"colors": {"text": "#fff"}},
            "root": {"type": "screen", "children": [{"type": "text", "id": "title", "text": "Title", "style": {"font_color": "$colors.missing"}}]},
        }
        with self.assertRaisesRegex(DesignUISpecError, "Unknown design token"):
            compile_design_spec(bad_token)

    def test_compile_rejects_component_cycles(self) -> None:
        spec = {
            "name": "Cycle",
            "components": {
                "a": {"type": "instance", "component": "b"},
                "b": {"type": "instance", "component": "a"},
            },
            "root": {"type": "screen", "children": [{"type": "instance", "component": "a"}]},
        }

        with self.assertRaisesRegex(DesignUISpecError, "Component cycle"):
            compile_design_spec(spec)

    def test_review_reports_layout_issues_without_real_godot(self) -> None:
        spec = {
            "name": "Review",
            "root": {
                "type": "screen",
                "children": [
                    {"type": "button", "id": "play", "text": "Play"},
                    {"type": "button", "id": "quit", "text": "Quit"},
                ],
            },
        }
        compiled = compile_design_spec(spec, viewports=[(50, 40)])

        with tempfile.TemporaryDirectory() as tmp:
            report = review_compiled_design(FakeDesignClient(), compiled, artifacts_dir=tmp)

        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("small_touch_target", codes)
        self.assertIn("text_overflow", codes)
        self.assertIn("out_of_viewport", codes)
        self.assertIn("sibling_overlap", codes)
        self.assertFalse(report["ok"])


@unittest.skipUnless(shutil.which("godot"), "godot executable is not available")
class DesignUiGodotIntegrationTests(unittest.TestCase):
    def test_generate_design_ui_applies_explicit_control_size_to_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project(root / "project", name="Design UI Size")
            spec_path = root / "sized_button.json"
            spec_path.write_text(
                json.dumps(
                    {
                        "name": "SizedButton",
                        "target": {"scene": "res://scenes/ui/sized_button.tscn"},
                        "root": {
                            "type": "screen",
                            "children": [
                                {
                                    "type": "button",
                                    "id": "play",
                                    "text": "Play",
                                    "position": [20, 20],
                                    "size": [220, 52],
                                }
                            ],
                        },
                        "review": {"viewports": ["400x240"]},
                    }
                ),
                encoding="utf-8",
            )

            report = generate_design_ui(
                project,
                spec_path,
                artifacts_dir=root / "artifacts",
                timeout=30.0,
                no_screenshots=True,
                check=True,
            )

        self.assertTrue(report["ok"])
        nodes = report["review"]["viewports"][0]["nodes"]
        play = next(node for node in nodes if node["id"] == "play")
        self.assertGreaterEqual(play["rect"]["width"], 220.0)
        self.assertGreaterEqual(play["rect"]["height"], 52.0)


if __name__ == "__main__":
    unittest.main()

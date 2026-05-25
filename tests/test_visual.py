from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from godot_playwright.visual import SnapshotAssertionError, _encode_rgba_png, compare_screenshots, expect_scene, inspect_screenshot


class FakeSnapshotClient:
    def __init__(self) -> None:
        self.snapshots: list[dict[str, object]] = [
            {
                "name": "Main",
                "class": "Control",
                "children": [
                    {
                        "name": "Title",
                        "class": "Label",
                        "path": "/root/Main/Title",
                        "properties": {"text": "Godot Playwright"},
                        "children": [],
                    },
                    {
                        "name": "CounterButton",
                        "class": "Button",
                        "path": "/root/Main/CounterButton",
                        "properties": {"text": "Clicked 0"},
                        "children": [],
                    },
                ],
            }
        ]

    def snapshot(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.snapshots[0]

    def screenshot(self, path: Path):  # type: ignore[no-untyped-def]
        path.write_bytes(_encode_rgba_png(1, 1, bytes([0, 0, 0, 255])))
        return {"path": str(path)}


class FakeScreenshotClient(FakeSnapshotClient):
    def __init__(self, pixels: bytes, *, width: int = 2, height: int = 1) -> None:
        super().__init__()
        self.pixels = pixels
        self.width = width
        self.height = height

    def screenshot(self, path: Path):  # type: ignore[no-untyped-def]
        path.write_bytes(_encode_rgba_png(self.width, self.height, self.pixels))
        return {"path": str(path)}


class VisualTests(unittest.TestCase):
    def test_scene_expect_finds_nodes_and_text(self) -> None:
        client = FakeSnapshotClient()
        scene = expect_scene(client, snapshots_dir=Path("."), artifacts_dir=Path("."))

        node = scene.to_have_node(name="CounterButton", class_name="Button", path="/root/Main/CounterButton")
        self.assertEqual(node["properties"]["text"], "Clicked 0")
        self.assertEqual(scene.to_contain_text("Godot Playwright")["name"], "Title")
        self.assertEqual(scene.to_have_node_count(1, class_name="Button")[0]["name"], "CounterButton")
        scene.to_satisfy(lambda snapshot: snapshot["children"][0]["name"] == "Title")
        scene.not_to_have_node(name="MissingNode", timeout=0.01)

    def test_scene_expect_writes_diff_on_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "snapshots"
            artifacts = root / "artifacts"
            snapshots.mkdir()
            artifacts.mkdir()
            (snapshots / "main.scene.json").write_text("{\n  \"name\": \"Main\"\n}\n", encoding="utf-8")

            client = FakeSnapshotClient()
            scene = expect_scene(client, snapshots_dir=snapshots, artifacts_dir=artifacts)
            with self.assertRaises(SnapshotAssertionError):
                scene.to_match_snapshot("main.scene.json")

            diff_path = artifacts / "main.scene.json.actual.json.diff"
            self.assertTrue(diff_path.exists())
            self.assertIn("---", diff_path.read_text(encoding="utf-8"))

    def test_screenshot_mismatch_writes_pixel_diff_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "snapshots"
            artifacts = root / "artifacts"
            snapshots.mkdir()
            artifacts.mkdir()
            expected_pixels = bytes([0, 0, 0, 255, 10, 10, 10, 255])
            actual_pixels = bytes([0, 0, 0, 255, 255, 0, 0, 255])
            (snapshots / "main.png").write_bytes(_encode_rgba_png(2, 1, expected_pixels))

            scene = expect_scene(
                FakeScreenshotClient(actual_pixels),
                snapshots_dir=snapshots,
                artifacts_dir=artifacts,
            )
            with self.assertRaises(SnapshotAssertionError) as raised:
                scene.to_match_screenshot("main.png")

            self.assertEqual(raised.exception.report["different_pixels"], 1)
            self.assertEqual(raised.exception.report["total_pixels"], 2)
            self.assertEqual(raised.exception.report["diff_ratio"], 0.5)
            self.assertTrue((artifacts / "main.png.actual.png").exists())
            self.assertTrue((artifacts / "main.png.diff.png").exists())
            report_path = artifacts / "main.png.diff.json"
            self.assertTrue(report_path.exists())
            self.assertIn('"different_pixels": 1', report_path.read_text(encoding="utf-8"))

    def test_screenshot_tolerance_allows_small_pixel_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = root / "expected.png"
            actual = root / "actual.png"
            expected.write_bytes(_encode_rgba_png(1, 1, bytes([10, 10, 10, 255])))
            actual.write_bytes(_encode_rgba_png(1, 1, bytes([12, 10, 10, 255])))

            exact = compare_screenshots(expected, actual)
            tolerated = compare_screenshots(expected, actual, threshold=2)

            self.assertFalse(exact["ok"])
            self.assertEqual(exact["different_pixels"], 1)
            self.assertTrue(tolerated["ok"])
            self.assertEqual(tolerated["different_pixels"], 0)

    def test_scene_expect_checks_screenshot_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pixels = bytes(
                [
                    0,
                    0,
                    0,
                    255,
                    255,
                    0,
                    0,
                    255,
                    0,
                    255,
                    0,
                    255,
                    0,
                    0,
                    255,
                    255,
                ]
            )
            scene = expect_scene(
                FakeScreenshotClient(pixels, width=2, height=2),
                snapshots_dir=root / "snapshots",
                artifacts_dir=root / "artifacts",
            )

            exact = scene.to_have_pixel(1, 0, "#ff0000", name="pixel.png", timeout=0.01)
            self.assertEqual(exact["actual_color"], (255, 0, 0, 255))
            tolerated = scene.to_have_pixel(0, 1, (0, 254, 0), threshold=1, name="pixel.png", timeout=0.01)
            self.assertTrue(tolerated["ok"])
            negative = scene.not_to_have_pixel(0, 0, {"r": 255, "g": 255, "b": 255}, name="pixel.png", timeout=0.01)
            self.assertEqual(negative["actual_color"], (0, 0, 0, 255))
            self.assertTrue((root / "artifacts" / "pixel.png.actual.png").exists())

            with self.assertRaises(SnapshotAssertionError) as raised:
                scene.to_have_pixel(1, 1, "#ff0000", name="pixel.png", timeout=0.01, interval=0.001)
            self.assertEqual(raised.exception.report["actual_color"], (0, 0, 255, 255))

            with self.assertRaises(SnapshotAssertionError):
                scene.not_to_have_pixel(1, 0, "#ff0000", name="pixel.png", timeout=0.01, interval=0.001)

    def test_scene_expect_checks_screenshot_region_color(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            red = [255, 0, 0, 255]
            blue = [0, 0, 255, 255]
            pixels = bytes(red + red + red + blue)
            scene = expect_scene(
                FakeScreenshotClient(pixels, width=2, height=2),
                snapshots_dir=root / "snapshots",
                artifacts_dir=root / "artifacts",
            )

            report = scene.to_have_region_color(0, 0, 2, 2, "#ff0000", min_ratio=0.75, name="region.png", timeout=0.01)
            self.assertEqual(report["matched_pixels"], 3)
            self.assertEqual(report["matched_ratio"], 0.75)
            with self.assertRaises(SnapshotAssertionError) as raised:
                scene.to_have_region_color(
                    0,
                    0,
                    2,
                    2,
                    "#ff0000",
                    min_ratio=1.0,
                    name="region.png",
                    timeout=0.01,
                    interval=0.001,
                )
            self.assertEqual(raised.exception.report["matched_pixels"], 3)

    def test_scene_expect_inspects_screenshot_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            red = [255, 0, 0, 255]
            blue = [0, 0, 255, 255]
            pixels = bytes(red + red + red + blue)
            scene = expect_scene(
                FakeScreenshotClient(pixels, width=2, height=2),
                snapshots_dir=root / "snapshots",
                artifacts_dir=root / "artifacts",
            )

            report = scene.inspect_screenshot(
                "inspection.png",
                sample_points=[
                    {"label": "origin", "x": 0, "y": 0},
                    {"label": "bottom-right", "x": 1, "y": 1, "expected_color": "#0000ff"},
                ],
                regions=[
                    {
                        "label": "full",
                        "x": 0,
                        "y": 0,
                        "width": 2,
                        "height": 2,
                        "expected_color": "#ff0000",
                        "min_ratio": 0.75,
                    }
                ],
            )

            self.assertTrue(report["ok"])
            self.assertEqual(report["image_size"], {"width": 2, "height": 2})
            self.assertEqual(report["sample_points"][0]["actual_color"], (255, 0, 0, 255))
            self.assertEqual(report["sample_points"][1]["max_channel_delta"], 0)
            self.assertEqual(report["regions"][0]["matched_pixels"], 3)
            self.assertEqual(report["regions"][0]["dominant_color"], (255, 0, 0, 255))
            self.assertEqual(report["regions"][0]["average_color"], (191, 0, 64, 255))
            self.assertTrue((root / "artifacts" / "inspection.png.actual.png").exists())
            report_path = root / "artifacts" / "inspection.png.visual.json"
            self.assertEqual(report["report_path"], str(report_path))
            self.assertTrue(report_path.exists())
            written = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(written["sample_points"][1]["actual_color"], [0, 0, 255, 255])
            self.assertEqual(written["regions"][0]["matched_ratio"], 0.75)

    def test_inspect_screenshot_reads_existing_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "existing.png"
            screenshot.write_bytes(_encode_rgba_png(1, 1, bytes([12, 34, 56, 255])))

            report = inspect_screenshot(
                screenshot,
                sample_points=[{"x": 0, "y": 0, "expected_color": [12, 34, 56, 255]}],
            )

            self.assertTrue(report["ok"])
            self.assertEqual(report["sha256"], report["sha256"].lower())
            self.assertEqual(report["sample_points"][0]["actual_color"], (12, 34, 56, 255))
            self.assertTrue((root / "existing.visual.json").exists())


if __name__ == "__main__":
    unittest.main()

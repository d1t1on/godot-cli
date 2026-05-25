from __future__ import annotations

import hashlib
import json
import shutil
import struct
import time
import zlib
from difflib import unified_diff
from pathlib import Path
from typing import Any, Callable

from .client import GodotClient


class SnapshotAssertionError(AssertionError):
    def __init__(self, message: str, report: dict[str, Any] | None = None):
        self.report = report or {}
        super().__init__(message)


class PngDecodeError(ValueError):
    pass


class SceneExpect:
    def __init__(
        self,
        client: GodotClient,
        *,
        snapshots_dir: str | Path = "__snapshots__",
        artifacts_dir: str | Path | None = None,
        update: bool = False,
    ):
        self.client = client
        self.snapshots_dir = Path(snapshots_dir)
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else self.snapshots_dir
        self.update = update

    def to_match_snapshot(
        self,
        name: str,
        *,
        root: str | dict[str, Any] | None = None,
        max_depth: int = 8,
        include_properties: bool = True,
    ) -> None:
        expected_path = _snapshot_path(self.snapshots_dir, name, ".json")
        actual_path = _snapshot_path(self.artifacts_dir, name, ".actual.json")
        diff_path = actual_path.with_suffix(actual_path.suffix + ".diff")
        snapshot = self.client.snapshot(
            root=root,
            max_depth=max_depth,
            include_properties=include_properties,
        )
        actual = _canonical_json(normalize_scene_snapshot(snapshot))

        if self.update or not expected_path.exists():
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            expected_path.write_text(actual, encoding="utf-8")
            return

        expected = expected_path.read_text(encoding="utf-8")
        if expected != actual:
            actual_path.parent.mkdir(parents=True, exist_ok=True)
            actual_path.write_text(actual, encoding="utf-8")
            diff_path.write_text(_text_diff(expected, actual, expected_path, actual_path), encoding="utf-8")
            raise SnapshotAssertionError(
                f"Scene snapshot mismatch for {name}. "
                f"Expected {expected_path}; actual {actual_path}; diff {diff_path}"
            )

    def to_have_node(
        self,
        *,
        name: str | None = None,
        class_name: str | None = None,
        path: str | None = None,
        properties: dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        max_depth: int = 8,
        include_properties: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_nodes: list[dict[str, Any]] = []
        while True:
            snapshot = self.client.snapshot(
                root=root,
                max_depth=max_depth,
                include_properties=include_properties,
            )
            last_nodes = _find_nodes(
                snapshot,
                name=name,
                class_name=class_name,
                path=path,
                properties=properties,
            )
            if last_nodes:
                return last_nodes[0]
            if time.monotonic() >= deadline:
                raise AssertionError(
                    "Expected scene snapshot to contain node "
                    f"name={name!r} class_name={class_name!r} path={path!r} properties={properties!r}; "
                    f"last snapshot={normalize_scene_snapshot(snapshot)!r}"
                )
            time.sleep(interval)

    def not_to_have_node(
        self,
        *,
        name: str | None = None,
        class_name: str | None = None,
        path: str | None = None,
        properties: dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        max_depth: int = 8,
        include_properties: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> None:
        deadline = time.monotonic() + timeout
        while True:
            snapshot = self.client.snapshot(
                root=root,
                max_depth=max_depth,
                include_properties=include_properties,
            )
            nodes = _find_nodes(
                snapshot,
                name=name,
                class_name=class_name,
                path=path,
                properties=properties,
            )
            if nodes:
                raise AssertionError(f"Expected scene snapshot not to contain matching node; got {nodes[0]!r}")
            if time.monotonic() >= deadline:
                return
            time.sleep(interval)

    def to_have_node_count(
        self,
        expected: int,
        *,
        name: str | None = None,
        class_name: str | None = None,
        path: str | None = None,
        properties: dict[str, Any] | None = None,
        root: str | dict[str, Any] | None = None,
        max_depth: int = 8,
        include_properties: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout
        last_nodes: list[dict[str, Any]] = []
        while True:
            snapshot = self.client.snapshot(
                root=root,
                max_depth=max_depth,
                include_properties=include_properties,
            )
            last_nodes = _find_nodes(
                snapshot,
                name=name,
                class_name=class_name,
                path=path,
                properties=properties,
            )
            if len(last_nodes) == expected:
                return last_nodes
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected {expected} matching scene nodes, got {len(last_nodes)}: {last_nodes!r}")
            time.sleep(interval)

    def to_contain_text(
        self,
        text: str,
        *,
        root: str | dict[str, Any] | None = None,
        max_depth: int = 8,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self.to_have_node(
            properties={"text": text},
            root=root,
            max_depth=max_depth,
            include_properties=True,
            timeout=timeout,
            interval=interval,
        )

    def to_satisfy(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        *,
        root: str | dict[str, Any] | None = None,
        max_depth: int = 8,
        include_properties: bool = True,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_snapshot: dict[str, Any] = {}
        while True:
            last_snapshot = self.client.snapshot(
                root=root,
                max_depth=max_depth,
                include_properties=include_properties,
            )
            if predicate(last_snapshot):
                return last_snapshot
            if time.monotonic() >= deadline:
                raise AssertionError(f"Expected scene snapshot predicate to pass; last={normalize_scene_snapshot(last_snapshot)!r}")
            time.sleep(interval)

    def to_match_screenshot(
        self,
        name: str,
        *,
        threshold: int = 0,
        max_different_pixels: int = 0,
        max_diff_ratio: float = 0.0,
    ) -> None:
        expected_path = _snapshot_path(self.snapshots_dir, name, ".png")
        actual_path = _snapshot_path(self.artifacts_dir, name, ".actual.png")
        diff_path, report_path = _screenshot_diff_paths(actual_path)
        actual_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.screenshot(actual_path)

        if self.update or not expected_path.exists():
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(actual_path, expected_path)
            return

        report = compare_screenshots(
            expected_path,
            actual_path,
            diff_path=diff_path,
            threshold=threshold,
            max_different_pixels=max_different_pixels,
            max_diff_ratio=max_diff_ratio,
        )
        if not report["ok"]:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(_canonical_json(report), encoding="utf-8")
            raise SnapshotAssertionError(
                _screenshot_mismatch_message(name, report, report_path),
                report=report,
            )

    def inspect_screenshot(
        self,
        name: str = "visual.png",
        *,
        sample_points: list[dict[str, Any]] | None = None,
        regions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        image, actual_path = self._capture_screenshot_rgba(name)
        report_path = _screenshot_inspection_path(actual_path)
        return _write_screenshot_inspection_report(
            image,
            actual_path=actual_path,
            report_path=report_path,
            sample_points=sample_points,
            regions=regions,
        )

    def to_have_pixel(
        self,
        x: int,
        y: int,
        color: str | tuple[int, ...] | list[int] | dict[str, int],
        *,
        threshold: int = 0,
        name: str = "pixel.png",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected = _normalize_rgba_color(color)
        deadline = time.monotonic() + timeout
        report: dict[str, Any] = {}
        while True:
            image, actual_path = self._capture_screenshot_rgba(name)
            report = _pixel_report(image, x, y, expected, threshold=threshold, actual_path=actual_path)
            if report["ok"]:
                return report
            if time.monotonic() >= deadline:
                raise SnapshotAssertionError(
                    f"Expected screenshot pixel ({x}, {y}) to be {expected}; "
                    f"actual={report.get('actual_color')} delta={report.get('max_channel_delta')} "
                    f"threshold={threshold}; actual {actual_path}",
                    report=report,
                )
            time.sleep(interval)

    def not_to_have_pixel(
        self,
        x: int,
        y: int,
        color: str | tuple[int, ...] | list[int] | dict[str, int],
        *,
        threshold: int = 0,
        name: str = "pixel.png",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        expected = _normalize_rgba_color(color)
        deadline = time.monotonic() + timeout
        report: dict[str, Any] = {}
        while True:
            image, actual_path = self._capture_screenshot_rgba(name)
            report = _pixel_report(image, x, y, expected, threshold=threshold, actual_path=actual_path)
            if not report["ok"]:
                return report
            if time.monotonic() >= deadline:
                raise SnapshotAssertionError(
                    f"Expected screenshot pixel ({x}, {y}) not to be {expected}; "
                    f"actual={report.get('actual_color')} threshold={threshold}; actual {actual_path}",
                    report=report,
                )
            time.sleep(interval)

    def to_have_region_color(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: str | tuple[int, ...] | list[int] | dict[str, int],
        *,
        threshold: int = 0,
        min_ratio: float = 1.0,
        name: str = "region.png",
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        if min_ratio < 0 or min_ratio > 1:
            raise ValueError("min_ratio must be between 0 and 1")
        expected = _normalize_rgba_color(color)
        deadline = time.monotonic() + timeout
        report: dict[str, Any] = {}
        while True:
            image, actual_path = self._capture_screenshot_rgba(name)
            report = _region_color_report(
                image,
                x,
                y,
                width,
                height,
                expected,
                threshold=threshold,
                min_ratio=min_ratio,
                actual_path=actual_path,
            )
            if report["ok"]:
                return report
            if time.monotonic() >= deadline:
                raise SnapshotAssertionError(
                    f"Expected screenshot region ({x}, {y}, {width}, {height}) to match {expected}; "
                    f"matched_ratio={report.get('matched_ratio')} min_ratio={min_ratio} "
                    f"threshold={threshold}; actual {actual_path}",
                    report=report,
                )
            time.sleep(interval)

    def _capture_screenshot_rgba(self, name: str) -> tuple[dict[str, Any], Path]:
        actual_path = _snapshot_path(self.artifacts_dir, name, ".actual.png")
        actual_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.screenshot(actual_path)
        try:
            return _decode_png_rgba(actual_path), actual_path
        except PngDecodeError as exc:
            raise SnapshotAssertionError(
                f"Could not decode screenshot {actual_path}: {exc}",
                report={"ok": False, "error": "PNG_DECODE_FAILED", "message": str(exc), "actual_path": str(actual_path)},
            ) from exc


def expect_scene(
    client: GodotClient,
    *,
    snapshots_dir: str | Path = "__snapshots__",
    artifacts_dir: str | Path | None = None,
    update: bool = False,
) -> SceneExpect:
    return SceneExpect(
        client,
        snapshots_dir=snapshots_dir,
        artifacts_dir=artifacts_dir,
        update=update,
    )


def inspect_screenshot(
    path: str | Path,
    *,
    sample_points: list[dict[str, Any]] | None = None,
    regions: list[dict[str, Any]] | None = None,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    actual_path = Path(path)
    image = _decode_png_rgba(actual_path)
    target_report_path = Path(report_path) if report_path is not None else _screenshot_inspection_path(actual_path)
    return _write_screenshot_inspection_report(
        image,
        actual_path=actual_path,
        report_path=target_report_path,
        sample_points=sample_points,
        regions=regions,
    )


def compare_screenshots(
    expected_path: str | Path,
    actual_path: str | Path,
    *,
    diff_path: str | Path | None = None,
    threshold: int = 0,
    max_different_pixels: int = 0,
    max_diff_ratio: float = 0.0,
) -> dict[str, Any]:
    if threshold < 0 or threshold > 255:
        raise ValueError("threshold must be between 0 and 255")
    if max_different_pixels < 0:
        raise ValueError("max_different_pixels must be non-negative")
    if max_diff_ratio < 0 or max_diff_ratio > 1:
        raise ValueError("max_diff_ratio must be between 0 and 1")

    expected = Path(expected_path)
    actual = Path(actual_path)
    expected_hash = _file_sha256(expected)
    actual_hash = _file_sha256(actual)
    report: dict[str, Any] = {
        "ok": expected_hash == actual_hash,
        "expected_path": str(expected),
        "actual_path": str(actual),
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
        "exact_hash_match": expected_hash == actual_hash,
        "threshold": threshold,
        "max_different_pixels": max_different_pixels,
        "max_diff_ratio": max_diff_ratio,
    }
    if expected_hash == actual_hash:
        return report

    try:
        expected_image = _decode_png_rgba(expected)
        actual_image = _decode_png_rgba(actual)
    except PngDecodeError as exc:
        report.update(
            {
                "ok": False,
                "error": "PNG_DECODE_FAILED",
                "message": str(exc),
            }
        )
        return report

    report["expected_size"] = {"width": expected_image["width"], "height": expected_image["height"]}
    report["actual_size"] = {"width": actual_image["width"], "height": actual_image["height"]}
    if expected_image["width"] != actual_image["width"] or expected_image["height"] != actual_image["height"]:
        report.update(
            {
                "ok": False,
                "error": "IMAGE_SIZE_MISMATCH",
                "message": "Screenshot dimensions differ",
            }
        )
        return report

    metrics = _compare_rgba_pixels(
        expected_image["pixels"],
        actual_image["pixels"],
        width=expected_image["width"],
        height=expected_image["height"],
        threshold=threshold,
    )
    allowed = max(max_different_pixels, int(max_diff_ratio * metrics["total_pixels"]))
    metrics["allowed_different_pixels"] = allowed
    metrics["ok"] = metrics["different_pixels"] <= allowed
    report.update(metrics)
    report["ok"] = bool(metrics["ok"])

    if diff_path is not None and not report["ok"]:
        diff = Path(diff_path)
        diff.parent.mkdir(parents=True, exist_ok=True)
        diff.write_bytes(_encode_rgba_png(expected_image["width"], expected_image["height"], metrics["diff_pixels"]))
        report["diff_path"] = str(diff)
    report.pop("diff_pixels", None)
    return report


def normalize_scene_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "name": snapshot.get("name"),
        "class": snapshot.get("class"),
    }
    if "properties" in snapshot:
        normalized["properties"] = _normalize_value(snapshot["properties"])
    normalized["children"] = [
        normalize_scene_snapshot(child)
        for child in snapshot.get("children", [])
        if isinstance(child, dict)
    ]
    return normalized


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _find_nodes(
    node: dict[str, Any],
    *,
    name: str | None = None,
    class_name: str | None = None,
    path: str | None = None,
    properties: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    if _node_matches(node, name=name, class_name=class_name, path=path, properties=properties):
        matches.append(node)
    for child in node.get("children", []):
        if isinstance(child, dict):
            matches.extend(
                _find_nodes(
                    child,
                    name=name,
                    class_name=class_name,
                    path=path,
                    properties=properties,
                )
            )
    return matches


def _node_matches(
    node: dict[str, Any],
    *,
    name: str | None = None,
    class_name: str | None = None,
    path: str | None = None,
    properties: dict[str, Any] | None = None,
) -> bool:
    if name is not None and node.get("name") != name:
        return False
    if class_name is not None and node.get("class") != class_name:
        return False
    if path is not None and node.get("path") != path:
        return False
    if properties is not None:
        node_properties = node.get("properties", {})
        if not isinstance(node_properties, dict) or not _contains_value(node_properties, properties):
            return False
    return True


def _contains_value(actual: Any, expected: Any) -> bool:
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key, expected_value in expected.items():
            if key not in actual or not _contains_value(actual[key], expected_value):
                return False
        return True
    if isinstance(actual, list) and isinstance(expected, list):
        if len(actual) < len(expected):
            return False
        return all(_contains_value(actual[index], expected[index]) for index in range(len(expected)))
    return actual == expected


def _text_diff(expected: str, actual: str, expected_path: Path, actual_path: Path) -> str:
    return "".join(
        unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=str(expected_path),
            tofile=str(actual_path),
        )
    )


def _screenshot_mismatch_message(name: str, report: dict[str, Any], report_path: Path) -> str:
    if report.get("error") == "IMAGE_SIZE_MISMATCH":
        return (
            f"Screenshot mismatch for {name}. "
            f"Expected size {report.get('expected_size')}; actual size {report.get('actual_size')}; "
            f"actual {report.get('actual_path')}; report {report_path}"
        )
    if report.get("error"):
        return (
            f"Screenshot mismatch for {name}. {report.get('message')}; "
            f"expected {report.get('expected_path')} ({report.get('expected_sha256')}); "
            f"actual {report.get('actual_path')} ({report.get('actual_sha256')}); report {report_path}"
        )
    return (
        f"Screenshot mismatch for {name}. "
        f"different_pixels={report.get('different_pixels')}/{report.get('total_pixels')} "
        f"diff_ratio={report.get('diff_ratio')} max_channel_delta={report.get('max_channel_delta')} "
        f"allowed={report.get('allowed_different_pixels')}; actual {report.get('actual_path')}; "
        f"diff {report.get('diff_path', '<none>')}; report {report_path}"
    )


def _screenshot_diff_paths(actual_path: Path) -> tuple[Path, Path]:
    name = actual_path.name
    if name.endswith(".actual.png"):
        prefix = name.removesuffix(".actual.png")
    else:
        prefix = actual_path.stem
    return actual_path.with_name(f"{prefix}.diff.png"), actual_path.with_name(f"{prefix}.diff.json")


def _screenshot_inspection_path(actual_path: Path) -> Path:
    name = actual_path.name
    if name.endswith(".actual.png"):
        prefix = name.removesuffix(".actual.png")
    elif name.endswith(".png"):
        prefix = name.removesuffix(".png")
    else:
        prefix = actual_path.stem
    return actual_path.with_name(f"{prefix}.visual.json")


def _write_screenshot_inspection_report(
    image: dict[str, Any],
    *,
    actual_path: Path,
    report_path: Path,
    sample_points: list[dict[str, Any]] | None,
    regions: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    report = _screenshot_inspection_report(
        image,
        actual_path=actual_path,
        sample_points=sample_points,
        regions=regions,
    )
    report["report_path"] = str(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_canonical_json(report), encoding="utf-8")
    return report


def _screenshot_inspection_report(
    image: dict[str, Any],
    *,
    actual_path: Path,
    sample_points: list[dict[str, Any]] | None,
    regions: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    width = int(image["width"])
    height = int(image["height"])
    point_reports = [_sample_point_inspection_report(image, spec) for spec in _inspection_entries(sample_points, "sample_points")]
    region_reports = [_region_inspection_report(image, spec, actual_path=actual_path) for spec in _inspection_entries(regions, "regions")]
    ok = all(report.get("ok", True) for report in [*point_reports, *region_reports])
    return {
        "ok": ok,
        "actual_path": str(actual_path),
        "sha256": _file_sha256(actual_path),
        "image_size": {"width": width, "height": height},
        "sample_points": point_reports,
        "regions": region_reports,
    }


def _inspection_entries(entries: list[dict[str, Any]] | None, name: str) -> list[dict[str, Any]]:
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise ValueError(f"{name} must be a list of dictionaries")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{name}[{index}] must be a dictionary")
    return entries


def _sample_point_inspection_report(image: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    width = int(image["width"])
    height = int(image["height"])
    x = _required_int(spec, "x", "sample point")
    y = _required_int(spec, "y", "sample point")
    _validate_pixel_bounds(x, y, width=width, height=height)
    actual = _pixel_at(image["pixels"], x, y, width=width)
    report: dict[str, Any] = {
        "ok": True,
        "x": x,
        "y": y,
        "actual_color": actual,
    }
    if "label" in spec:
        report["label"] = str(spec["label"])
    expected_value = _expected_color_value(spec)
    if expected_value is not None:
        expected = _normalize_rgba_color(expected_value)
        threshold = _optional_threshold(spec)
        max_delta = _max_rgba_delta(actual, expected)
        report.update(
            {
                "ok": max_delta <= threshold,
                "expected_color": expected,
                "threshold": threshold,
                "max_channel_delta": max_delta,
            }
        )
    return report


def _region_inspection_report(image: dict[str, Any], spec: dict[str, Any], *, actual_path: Path) -> dict[str, Any]:
    width = _required_int(spec, "width", "region")
    height = _required_int(spec, "height", "region")
    x = _required_int(spec, "x", "region")
    y = _required_int(spec, "y", "region")
    image_width = int(image["width"])
    image_height = int(image["height"])
    summary = _region_summary(image, x, y, width, height)
    report: dict[str, Any] = {
        "ok": True,
        "image_size": {"width": image_width, "height": image_height},
        "region": {"x": x, "y": y, "width": width, "height": height},
        **summary,
    }
    if "label" in spec:
        report["label"] = str(spec["label"])
    expected_value = _expected_color_value(spec)
    if expected_value is not None:
        threshold = _optional_threshold(spec)
        min_ratio = _optional_min_ratio(spec)
        match_report = _region_color_report(
            image,
            x,
            y,
            width,
            height,
            _normalize_rgba_color(expected_value),
            threshold=threshold,
            min_ratio=min_ratio,
            actual_path=actual_path,
        )
        report.update(
            {
                "ok": match_report["ok"],
                "expected_color": match_report["expected_color"],
                "threshold": match_report["threshold"],
                "min_ratio": match_report["min_ratio"],
                "matched_pixels": match_report["matched_pixels"],
                "matched_ratio": match_report["matched_ratio"],
                "max_channel_delta": match_report["max_channel_delta"],
            }
        )
    return report


def _region_summary(
    image: dict[str, Any],
    x: int,
    y: int,
    width: int,
    height: int,
) -> dict[str, Any]:
    if width <= 0 or height <= 0:
        raise ValueError("Region width and height must be positive")
    image_width = int(image["width"])
    image_height = int(image["height"])
    _validate_pixel_bounds(x, y, width=image_width, height=image_height)
    _validate_pixel_bounds(x + width - 1, y + height - 1, width=image_width, height=image_height)
    pixels = image["pixels"]
    totals = [0, 0, 0, 0]
    counts: dict[tuple[int, int, int, int], int] = {}
    for row in range(y, y + height):
        for column in range(x, x + width):
            color = _pixel_at(pixels, column, row, width=image_width)
            for channel in range(4):
                totals[channel] += color[channel]
            counts[color] = counts.get(color, 0) + 1
    total_pixels = width * height
    dominant_color, dominant_pixels = max(counts.items(), key=lambda item: (item[1], item[0]))
    average_color = tuple(int((total + (total_pixels / 2)) // total_pixels) for total in totals)
    return {
        "total_pixels": total_pixels,
        "average_color": average_color,
        "dominant_color": dominant_color,
        "dominant_pixels": dominant_pixels,
        "dominant_ratio": round(dominant_pixels / total_pixels, 8),
    }


def _required_int(spec: dict[str, Any], key: str, entry_name: str) -> int:
    if key not in spec:
        raise ValueError(f"{entry_name} requires {key!r}")
    try:
        return int(spec[key])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{entry_name} {key!r} must be an integer") from exc


def _optional_threshold(spec: dict[str, Any]) -> int:
    try:
        threshold = int(spec.get("threshold", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("threshold must be an integer") from exc
    _validate_threshold(threshold)
    return threshold


def _optional_min_ratio(spec: dict[str, Any]) -> float:
    try:
        min_ratio = float(spec.get("min_ratio", 1.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("min_ratio must be a number") from exc
    if min_ratio < 0 or min_ratio > 1:
        raise ValueError("min_ratio must be between 0 and 1")
    return min_ratio


def _expected_color_value(spec: dict[str, Any]) -> Any | None:
    if "expected_color" in spec:
        return spec["expected_color"]
    if "color" in spec:
        return spec["color"]
    return None


def _normalize_rgba_color(color: str | tuple[int, ...] | list[int] | dict[str, int]) -> tuple[int, int, int, int]:
    if isinstance(color, str):
        text = color.strip()
        if text.startswith("#"):
            text = text[1:]
        if len(text) not in {6, 8}:
            raise ValueError("Hex colors must be #RRGGBB or #RRGGBBAA")
        try:
            values = [int(text[index : index + 2], 16) for index in range(0, len(text), 2)]
        except ValueError as exc:
            raise ValueError(f"Invalid hex color {color!r}") from exc
        if len(values) == 3:
            values.append(255)
        return tuple(values)  # type: ignore[return-value]
    if isinstance(color, dict):
        values = [color.get("r"), color.get("g"), color.get("b"), color.get("a", 255)]
    else:
        values = list(color)
        if len(values) == 3:
            values.append(255)
    if len(values) != 4:
        raise ValueError("Colors must have r/g/b and optional alpha components")
    normalized = tuple(int(value) for value in values)
    if any(channel < 0 or channel > 255 for channel in normalized):
        raise ValueError("Color channel values must be between 0 and 255")
    return normalized


def _pixel_report(
    image: dict[str, Any],
    x: int,
    y: int,
    expected: tuple[int, int, int, int],
    *,
    threshold: int,
    actual_path: Path,
) -> dict[str, Any]:
    _validate_threshold(threshold)
    width = int(image["width"])
    height = int(image["height"])
    _validate_pixel_bounds(x, y, width=width, height=height)
    actual = _pixel_at(image["pixels"], x, y, width=width)
    max_delta = _max_rgba_delta(actual, expected)
    return {
        "ok": max_delta <= threshold,
        "actual_path": str(actual_path),
        "width": width,
        "height": height,
        "x": x,
        "y": y,
        "expected_color": expected,
        "actual_color": actual,
        "threshold": threshold,
        "max_channel_delta": max_delta,
    }


def _region_color_report(
    image: dict[str, Any],
    x: int,
    y: int,
    width: int,
    height: int,
    expected: tuple[int, int, int, int],
    *,
    threshold: int,
    min_ratio: float,
    actual_path: Path,
) -> dict[str, Any]:
    _validate_threshold(threshold)
    if width <= 0 or height <= 0:
        raise ValueError("Region width and height must be positive")
    image_width = int(image["width"])
    image_height = int(image["height"])
    _validate_pixel_bounds(x, y, width=image_width, height=image_height)
    _validate_pixel_bounds(x + width - 1, y + height - 1, width=image_width, height=image_height)
    matched = 0
    total = width * height
    max_delta = 0
    pixels = image["pixels"]
    for row in range(y, y + height):
        for column in range(x, x + width):
            actual = _pixel_at(pixels, column, row, width=image_width)
            delta = _max_rgba_delta(actual, expected)
            max_delta = max(max_delta, delta)
            if delta <= threshold:
                matched += 1
    ratio = matched / total if total else 0.0
    return {
        "ok": ratio >= min_ratio,
        "actual_path": str(actual_path),
        "image_size": {"width": image_width, "height": image_height},
        "region": {"x": x, "y": y, "width": width, "height": height},
        "expected_color": expected,
        "threshold": threshold,
        "min_ratio": min_ratio,
        "matched_pixels": matched,
        "total_pixels": total,
        "matched_ratio": round(ratio, 8),
        "max_channel_delta": max_delta,
    }


def _validate_threshold(threshold: int) -> None:
    if threshold < 0 or threshold > 255:
        raise ValueError("threshold must be between 0 and 255")


def _validate_pixel_bounds(x: int, y: int, *, width: int, height: int) -> None:
    if x < 0 or y < 0 or x >= width or y >= height:
        raise ValueError(f"Pixel ({x}, {y}) is outside image bounds {width}x{height}")


def _pixel_at(pixels: bytes, x: int, y: int, *, width: int) -> tuple[int, int, int, int]:
    offset = (y * width + x) * 4
    return tuple(pixels[offset : offset + 4])  # type: ignore[return-value]


def _max_rgba_delta(actual: tuple[int, int, int, int], expected: tuple[int, int, int, int]) -> int:
    return max(abs(actual[index] - expected[index]) for index in range(4))


def _compare_rgba_pixels(
    expected_pixels: bytes,
    actual_pixels: bytes,
    *,
    width: int,
    height: int,
    threshold: int,
) -> dict[str, Any]:
    total_pixels = width * height
    different_pixels = 0
    max_channel_delta = 0
    delta_sum = 0
    diff_pixels = bytearray()
    for offset in range(0, len(expected_pixels), 4):
        expected = expected_pixels[offset : offset + 4]
        actual = actual_pixels[offset : offset + 4]
        deltas = [abs(expected[index] - actual[index]) for index in range(4)]
        pixel_delta = max(deltas)
        max_channel_delta = max(max_channel_delta, pixel_delta)
        delta_sum += sum(deltas)
        if pixel_delta > threshold:
            different_pixels += 1
            diff_pixels.extend((255, 0, 255, 255))
        else:
            # Keep unchanged pixels visible but subdued in the generated diff.
            gray = int((int(actual[0]) + int(actual[1]) + int(actual[2])) / 3)
            diff_pixels.extend((gray, gray, gray, 96))
    channel_count = max(total_pixels * 4, 1)
    return {
        "total_pixels": total_pixels,
        "different_pixels": different_pixels,
        "diff_ratio": round(different_pixels / total_pixels, 8) if total_pixels else 0.0,
        "max_channel_delta": max_channel_delta,
        "mean_channel_delta": round(delta_sum / channel_count, 6),
        "diff_pixels": bytes(diff_pixels),
    }


def _decode_png_rgba(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PngDecodeError(f"{path} is not a PNG file")

    width = 0
    height = 0
    bit_depth = 0
    color_type = 0
    interlace = 0
    palette = b""
    transparency = b""
    idat_chunks: list[bytes] = []
    offset = 8
    while offset < len(data):
        if offset + 8 > len(data):
            raise PngDecodeError(f"{path} has a truncated PNG chunk header")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_start = offset + 8
        chunk_end = chunk_start + length
        if chunk_end + 4 > len(data):
            raise PngDecodeError(f"{path} has a truncated {chunk_type.decode('ascii', 'replace')} chunk")
        chunk = data[chunk_start:chunk_end]
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(">IIBBBBB", chunk)
        elif chunk_type == b"PLTE":
            palette = chunk
        elif chunk_type == b"tRNS":
            transparency = chunk
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk)
        elif chunk_type == b"IEND":
            break
        offset = chunk_end + 4

    if width <= 0 or height <= 0:
        raise PngDecodeError(f"{path} has no valid IHDR dimensions")
    if bit_depth != 8:
        raise PngDecodeError(f"{path} uses unsupported PNG bit depth {bit_depth}")
    if color_type not in {0, 2, 3, 4, 6}:
        raise PngDecodeError(f"{path} uses unsupported PNG color type {color_type}")
    if interlace != 0:
        raise PngDecodeError(f"{path} uses unsupported interlacing")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    stride = width * channels
    try:
        raw = zlib.decompress(b"".join(idat_chunks))
    except zlib.error as exc:
        raise PngDecodeError(f"{path} has invalid PNG image data: {exc}") from exc

    rows: list[bytes] = []
    previous = bytes(stride)
    position = 0
    for _row in range(height):
        if position >= len(raw):
            raise PngDecodeError(f"{path} has truncated PNG scanline data")
        filter_type = raw[position]
        position += 1
        scanline = bytearray(raw[position : position + stride])
        if len(scanline) != stride:
            raise PngDecodeError(f"{path} has truncated PNG scanline data")
        position += stride
        reconstructed = _unfilter_png_scanline(filter_type, scanline, previous, channels)
        rows.append(bytes(reconstructed))
        previous = bytes(reconstructed)

    pixels = bytearray()
    for row in rows:
        pixels.extend(_png_row_to_rgba(row, color_type, palette, transparency))
    return {"width": width, "height": height, "pixels": bytes(pixels)}


def _unfilter_png_scanline(filter_type: int, scanline: bytearray, previous: bytes, bytes_per_pixel: int) -> bytearray:
    if filter_type == 0:
        return scanline
    reconstructed = bytearray(scanline)
    for index, value in enumerate(scanline):
        left = reconstructed[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index] if index < len(previous) else 0
        up_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel and index - bytes_per_pixel < len(previous) else 0
        if filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = up
        elif filter_type == 3:
            predictor = (left + up) // 2
        elif filter_type == 4:
            predictor = _paeth_predictor(left, up, up_left)
        else:
            raise PngDecodeError(f"Unsupported PNG filter type {filter_type}")
        reconstructed[index] = (value + predictor) & 0xFF
    return reconstructed


def _paeth_predictor(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    up_left_distance = abs(estimate - up_left)
    if left_distance <= up_distance and left_distance <= up_left_distance:
        return left
    if up_distance <= up_left_distance:
        return up
    return up_left


def _png_row_to_rgba(row: bytes, color_type: int, palette: bytes, transparency: bytes) -> bytes:
    pixels = bytearray()
    if color_type == 0:
        for gray in row:
            pixels.extend((gray, gray, gray, 255))
    elif color_type == 2:
        for offset in range(0, len(row), 3):
            pixels.extend((row[offset], row[offset + 1], row[offset + 2], 255))
    elif color_type == 3:
        for index in row:
            palette_offset = index * 3
            if palette_offset + 2 >= len(palette):
                raise PngDecodeError(f"Palette index {index} is outside PLTE")
            alpha = transparency[index] if index < len(transparency) else 255
            pixels.extend((palette[palette_offset], palette[palette_offset + 1], palette[palette_offset + 2], alpha))
    elif color_type == 4:
        for offset in range(0, len(row), 2):
            gray = row[offset]
            pixels.extend((gray, gray, gray, row[offset + 1]))
    elif color_type == 6:
        pixels.extend(row)
    return bytes(pixels)


def _encode_rgba_png(width: int, height: int, pixels: bytes) -> bytes:
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive")
    expected_length = width * height * 4
    if len(pixels) != expected_length:
        raise ValueError(f"Expected {expected_length} RGBA bytes, got {len(pixels)}")
    raw = bytearray()
    stride = width * 4
    for row in range(height):
        raw.append(0)
        start = row * stride
        raw.extend(pixels[start : start + stride])
    chunks = [
        _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
        _png_chunk(b"IDAT", zlib.compress(bytes(raw))),
        _png_chunk(b"IEND", b""),
    ]
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(payload, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", checksum)


def _snapshot_path(root: Path, name: str, default_suffix: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Snapshot name must be a relative path inside the snapshot directory: {name}")
    if path.suffix == "":
        path = path.with_suffix(default_suffix)
    elif path.suffix != default_suffix and default_suffix == ".actual.json":
        path = path.with_suffix(path.suffix + ".actual.json")
    elif path.suffix != default_suffix and default_suffix == ".actual.png":
        path = path.with_suffix(path.suffix + ".actual.png")
    return root / path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

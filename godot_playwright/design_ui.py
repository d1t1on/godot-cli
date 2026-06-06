from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from html import escape
from pathlib import Path, PurePosixPath
from typing import Any

from .client import Godot, GodotClient


DEFAULT_VIEWPORTS: tuple[tuple[int, int], ...] = ((1280, 720), (1920, 1080), (800, 450))
CONTROL_ROOT_PROPERTIES: dict[str, Any] = {
    "anchor_left": 0.0,
    "anchor_top": 0.0,
    "anchor_right": 1.0,
    "anchor_bottom": 1.0,
    "offset_left": 0.0,
    "offset_top": 0.0,
    "offset_right": 0.0,
    "offset_bottom": 0.0,
}
TOUCH_TARGET_MIN_SIZE = 44.0


class DesignUISpecError(ValueError):
    pass


class DesignUIError(RuntimeError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(_design_ui_error_message(report))


@dataclass(frozen=True)
class CompiledDesign:
    name: str
    scene_path: str
    root_class: str
    root_name: str
    root_properties: dict[str, Any]
    root_metadata: dict[str, Any]
    node_tree: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    viewports: list[tuple[int, int]]
    asset_paths: list[str] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)


def load_design_spec(path: str | Path) -> dict[str, Any]:
    spec_path = Path(path).expanduser()
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DesignUISpecError(f"Invalid design UI JSON in {spec_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DesignUISpecError("Design UI spec must be a JSON object")
    return data


def compile_design_spec(
    spec: dict[str, Any],
    *,
    project: str | Path | None = None,
    scene: str | None = None,
    viewports: list[tuple[int, int]] | None = None,
    max_nodes: int = 100,
) -> CompiledDesign:
    if not isinstance(spec, dict):
        raise DesignUISpecError("Design UI spec must be a JSON object")
    schema_version = spec.get("schema_version", 1)
    if schema_version not in (1, "1", "1.0"):
        raise DesignUISpecError(f"Unsupported design UI schema_version: {schema_version!r}")

    name = _clean_node_name(str(spec.get("name") or "GeneratedUi"))
    target = _optional_mapping(spec.get("target"), "target")
    scene_path = scene or str(target.get("scene") or f"res://scenes/ui/{_snake_name(name)}.tscn")
    _validate_res_path(scene_path, field_name="target.scene")

    tokens = _optional_mapping(spec.get("tokens"), "tokens")
    components = _optional_mapping(spec.get("components"), "components")
    root = _required_mapping(spec.get("root"), "root")
    root = _expand_node(root, components=components, tokens=tokens, stack=[])
    root_type = str(root.get("type", "screen"))
    counters: dict[str, int] = {}
    nodes: list[dict[str, Any]] = []
    asset_paths: list[str] = []
    compile_issues: list[dict[str, Any]] = []

    if root_type == "screen":
        root_class = str(root.get("class") or ("Panel" if _screen_has_background(root) else "Control"))
        root_name = _clean_node_name(str(root.get("name") or name))
        root_properties = dict(CONTROL_ROOT_PROPERTIES)
        root_properties.update(_layout_properties(root, tokens=tokens, root=True))
        root_properties.update(_style_properties(root, tokens=tokens, node_type="screen"))
        root_design_id = _design_id(root, "screen")
        counters[root_design_id] = 1
        root_metadata = _node_metadata(root, design_id=root_design_id, parent_id="", node_type="screen")
        children = root.get("children", [])
        if children is None:
            children = []
        if not isinstance(children, list):
            raise DesignUISpecError("root.children must be an array")
        node_tree = [
            _compile_node(
                child,
                tokens=tokens,
                parent_id=root_metadata["design_id"],
                counters=counters,
                nodes=nodes,
                asset_paths=asset_paths,
            )
            for child in children
        ]
    else:
        root_class = "Control"
        root_name = name
        root_properties = dict(CONTROL_ROOT_PROPERTIES)
        root_design_id = _snake_name(name)
        counters[root_design_id] = 1
        root_metadata = _node_metadata({"id": root_design_id}, design_id=root_design_id, parent_id="", node_type="screen")
        node_tree = [
            _compile_node(
                root,
                tokens=tokens,
                parent_id=root_metadata["design_id"],
                counters=counters,
                nodes=nodes,
                asset_paths=asset_paths,
            )
        ]

    if len(nodes) > max_nodes:
        raise DesignUISpecError(f"Design UI node count {len(nodes)} exceeds max_nodes {max_nodes}")

    viewport_values = viewports or _viewports_from_spec(spec)
    compile_issues.extend(_asset_issues(project, asset_paths))
    return CompiledDesign(
        name=name,
        scene_path=scene_path,
        root_class=root_class,
        root_name=root_name,
        root_properties=root_properties,
        root_metadata=root_metadata,
        node_tree=node_tree,
        nodes=nodes,
        viewports=viewport_values,
        asset_paths=sorted(dict.fromkeys(asset_paths)),
        issues=compile_issues,
    )


def generate_design_ui(
    project: str | Path,
    spec_path: str | Path,
    *,
    scene: str | None = None,
    viewports: list[tuple[int, int]] | None = None,
    artifacts_dir: str | Path = "godot-playwright-report/design-ui",
    executable: str = "godot",
    timeout: float = 20.0,
    max_nodes: int = 100,
    dry_run: bool = False,
    no_screenshots: bool = False,
    force: bool = False,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    spec_file = Path(spec_path).expanduser().resolve()
    artifacts = _artifact_root(artifacts_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    compiled = compile_design_spec(
        load_design_spec(spec_file),
        project=project_path,
        scene=scene,
        viewports=viewports,
        max_nodes=max_nodes,
    )
    target_path = _res_local_path(project_path, compiled.scene_path, field_name="target.scene")

    report: dict[str, Any] = {
        "project": str(project_path),
        "spec": str(spec_file),
        "target_scene": compiled.scene_path,
        "artifacts_dir": str(artifacts),
        "report_json": str(artifacts / "design-report.json"),
        "report_html": str(artifacts / "design-report.html"),
        "dry_run": dry_run,
        "force": force,
        "generated": False,
        "screenshots": not no_screenshots,
        "node_count": compiled.node_count,
        "viewports": [_viewport_dict(width, height) for width, height in compiled.viewports],
        "compiled": _compiled_summary(compiled),
        "issues": list(compiled.issues),
    }
    if target_path.exists() and not force:
        report["issues"].append(
            _issue(
                "error",
                "target_scene_exists",
                f"Target scene already exists: {compiled.scene_path}. Pass --force to overwrite it.",
            )
        )

    if dry_run:
        report["ok"] = _issues_are_ok(report["issues"])
        report["duration_ms"] = round((time.monotonic() - started) * 1000.0, 3)
        _write_design_reports(report, artifacts)
        if check and not report["ok"]:
            raise DesignUIError(report)
        return report

    if not _issues_are_ok(report["issues"]):
        report["ok"] = False
        report["duration_ms"] = round((time.monotonic() - started) * 1000.0, 3)
        _write_design_reports(report, artifacts)
        if check:
            raise DesignUIError(report)
        return report

    _ensure_res_parent(project_path, compiled.scene_path)

    with Godot(
        project_path,
        mode="editor",
        executable=executable,
        headless=no_screenshots,
        timeout=timeout,
    ) as client:
        generation = _author_compiled_design(client, compiled, timeout=timeout)
        report["generated"] = True
        report["generation"] = generation
        review = review_compiled_design(
            client,
            compiled,
            artifacts_dir=artifacts,
            no_screenshots=no_screenshots,
            timeout=timeout,
        )
        report["review"] = review
        report["issues"].extend(review.get("issues", []))

    report["ok"] = _issues_are_ok(report["issues"])
    report["duration_ms"] = round((time.monotonic() - started) * 1000.0, 3)
    _write_design_reports(report, artifacts)
    if check and not report["ok"]:
        raise DesignUIError(report)
    return report


def review_compiled_design(
    client: GodotClient,
    compiled: CompiledDesign,
    *,
    artifacts_dir: str | Path,
    no_screenshots: bool = False,
    timeout: float = 20.0,
) -> dict[str, Any]:
    artifacts = Path(artifacts_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    viewport_reports: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for width, height in compiled.viewports:
        label = f"{width}x{height}"
        viewport_report: dict[str, Any] = {
            "viewport": _viewport_dict(width, height),
            "nodes": [],
            "issues": [],
        }
        try:
            client.set_viewport_size(width, height)
            viewport_report["viewport_info"] = client.wait_for_viewport_size(width, height, timeout=min(timeout, 5.0))
        except Exception as exc:
            viewport_report["issues"].append(_issue("warning", "viewport_resize_failed", str(exc), viewport=label))

        snapshot_path = artifacts / f"{label}.scene.json"
        try:
            snapshot = client.snapshot(root="edited", max_depth=12, include_properties=True)
            snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
            viewport_report["scene_snapshot"] = str(snapshot_path)
        except Exception as exc:
            viewport_report["issues"].append(_issue("warning", "scene_snapshot_failed", str(exc), viewport=label))

        if no_screenshots:
            viewport_report["issues"].append(_issue("warning", "screenshot_skipped", "Screenshots disabled", viewport=label))
        else:
            screenshot_path = artifacts / f"{label}.png"
            try:
                screenshot = client.screenshot(screenshot_path)
                viewport_report["screenshot"] = str(screenshot_path)
                viewport_report["screenshot_result"] = screenshot
            except Exception as exc:
                viewport_report["issues"].append(_issue("warning", "screenshot_failed", str(exc), viewport=label))

        node_reports = _collect_node_reports(client, compiled, viewport=label)
        viewport_report["nodes"] = node_reports
        viewport_report["issues"].extend(_layout_issues(node_reports, width=width, height=height, viewport=label))
        issues.extend(viewport_report["issues"])
        viewport_reports.append(viewport_report)

    return {
        "ok": _issues_are_ok(issues),
        "viewports": viewport_reports,
        "issues": issues,
        "issue_count": len(issues),
    }


def _author_compiled_design(client: GodotClient, compiled: CompiledDesign, *, timeout: float) -> dict[str, Any]:
    result: dict[str, Any] = {"scene": compiled.scene_path}
    result["new_scene"] = client.editor_new_scene(class_name=compiled.root_class, name=compiled.root_name, timeout=timeout)
    client.set_node_properties("edited", compiled.root_properties, wait=False)
    client.set_node_metadata("edited", compiled.root_metadata, wait=False)
    if compiled.node_tree:
        result["node_tree"] = client.create_node_tree(
            compiled.node_tree,
            parent="edited",
            max_nodes=max(compiled.node_count, 1),
            wait=False,
        )
    result["save"] = client.editor_save_scene(compiled.scene_path, timeout=timeout)
    return result


def _compile_node(
    raw_node: dict[str, Any],
    *,
    tokens: dict[str, Any],
    parent_id: str,
    counters: dict[str, int],
    nodes: list[dict[str, Any]],
    asset_paths: list[str],
) -> dict[str, Any]:
    node = _required_mapping(raw_node, "node")
    node_type = str(node.get("type", "panel"))
    design_id = _unique_design_id(_design_id(node, node_type), counters)
    class_name = _node_class(node_type, node)
    compiled: dict[str, Any] = {
        "class": class_name,
        "name": _clean_node_name(str(node.get("name") or _pascal_name(design_id))),
        "properties": {},
        "metadata": _node_metadata(node, design_id=design_id, parent_id=parent_id, node_type=node_type),
        "groups": ["agent_ui"],
        "children": [],
    }
    properties = compiled["properties"]
    properties.update(_layout_properties(node, tokens=tokens, root=False))
    properties.update(_content_properties(node, tokens=tokens, node_type=node_type, asset_paths=asset_paths))
    properties.update(_style_properties(node, tokens=tokens, node_type=node_type))
    properties.update(_extra_properties(node, tokens=tokens))
    children = node.get("children", [])
    if children is None:
        children = []
    if not isinstance(children, list):
        raise DesignUISpecError(f"{design_id}.children must be an array")
    compiled["children"] = [
        _compile_node(
            child,
            tokens=tokens,
            parent_id=design_id,
            counters=counters,
            nodes=nodes,
            asset_paths=asset_paths,
        )
        for child in children
    ]
    node_info = {
        "id": design_id,
        "parent_id": parent_id,
        "name": compiled["name"],
        "class": class_name,
        "type": node_type,
        "test_id": compiled["metadata"]["test_id"],
        "text": str(node.get("text", "")) if node.get("text") is not None else "",
    }
    nodes.append(node_info)
    return compiled


def _expand_node(
    node: dict[str, Any],
    *,
    components: dict[str, Any],
    tokens: dict[str, Any],
    stack: list[str],
) -> dict[str, Any]:
    raw_type = str(node.get("type", "panel"))
    if raw_type != "instance":
        expanded = dict(node)
        if isinstance(expanded.get("children"), list):
            expanded["children"] = [
                _expand_node(_required_mapping(child, "child"), components=components, tokens=tokens, stack=stack)
                for child in expanded["children"]
            ]
        return expanded

    component_name = str(node.get("component", "")).strip()
    if not component_name:
        raise DesignUISpecError("instance.component is required")
    if component_name in stack:
        chain = " -> ".join(stack + [component_name])
        raise DesignUISpecError(f"Component cycle detected: {chain}")
    component = _required_mapping(components.get(component_name), f"components.{component_name}")
    base = _component_base(component)
    variant_name = str(node.get("variant", "default"))
    variants = _optional_mapping(component.get("variants"), f"components.{component_name}.variants")
    variant = _optional_mapping(variants.get(variant_name), f"components.{component_name}.variants.{variant_name}") if variant_name in variants else {}
    overrides = _optional_mapping(node.get("overrides"), "instance.overrides")
    direct = {key: value for key, value in node.items() if key not in {"type", "component", "variant", "overrides"}}
    merged = _deep_merge(_deep_merge(base, variant), _deep_merge(overrides, direct))
    return _expand_node(merged, components=components, tokens=tokens, stack=stack + [component_name])


def _component_base(component: dict[str, Any]) -> dict[str, Any]:
    if "base" in component:
        return _required_mapping(component["base"], "component.base")
    return {key: value for key, value in component.items() if key != "variants"}


def _node_class(node_type: str, node: dict[str, Any]) -> str:
    if "class" in node:
        return str(node["class"])
    if node_type == "screen":
        return "Control"
    if node_type == "panel":
        return "PanelContainer"
    if node_type == "stack":
        direction = str(_layout(node).get("direction", node.get("direction", "vertical"))).lower()
        return "HBoxContainer" if direction in {"horizontal", "row", "h"} else "VBoxContainer"
    if node_type == "text":
        return "Label"
    if node_type == "button":
        return "Button"
    if node_type == "meter":
        return "ProgressBar"
    if node_type == "image":
        return "TextureRect"
    if node_type == "spacer":
        return "Control"
    raise DesignUISpecError(f"Unsupported design UI node type: {node_type!r}")


def _layout_properties(node: dict[str, Any], *, tokens: dict[str, Any], root: bool) -> dict[str, Any]:
    layout = _layout(node)
    properties: dict[str, Any] = {}
    if root:
        anchor = str(layout.get("anchor", "full_rect"))
    else:
        anchor = str(layout.get("anchor", node.get("anchor", ""))).strip()
    if anchor:
        properties.update(_anchor_properties(anchor))
    size = layout.get("size", node.get("size"))
    min_size = layout.get("min_size", node.get("min_size"))
    if size is not None:
        width, height = _size_pair(_resolve_value(size, tokens), field_name="size")
        properties["size"] = _vector2(width, height)
        if min_size is None:
            properties["custom_minimum_size"] = _vector2(width, height)
    if min_size is not None:
        width, height = _size_pair(_resolve_value(min_size, tokens), field_name="min_size")
        properties["custom_minimum_size"] = _vector2(width, height)
    position = layout.get("position", node.get("position"))
    if position is not None:
        x, y = _size_pair(_resolve_value(position, tokens), field_name="position")
        properties["position"] = _vector2(x, y)
    gap = layout.get("gap", node.get("gap"))
    if gap is not None and _node_class(str(node.get("type", "panel")), node) in {"HBoxContainer", "VBoxContainer"}:
        properties["theme_override_constants/separation"] = int(_number(_resolve_value(gap, tokens), field_name="gap"))
    align = str(layout.get("align", node.get("align", ""))).lower()
    if align:
        properties["alignment"] = {"start": 0, "begin": 0, "left": 0, "top": 0, "center": 1, "end": 2, "right": 2, "bottom": 2}.get(align, 0)
    return properties


def _content_properties(
    node: dict[str, Any],
    *,
    tokens: dict[str, Any],
    node_type: str,
    asset_paths: list[str],
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    if node_type in {"text", "button"}:
        properties["text"] = str(_resolve_value(node.get("text", ""), tokens))
        align = str(node.get("text_align", node.get("align_text", ""))).lower()
        if align:
            properties["horizontal_alignment"] = {"left": 0, "start": 0, "center": 1, "right": 2, "end": 2, "fill": 3}.get(align, 0)
        vertical = str(node.get("vertical_align", "")).lower()
        if vertical:
            properties["vertical_alignment"] = {"top": 0, "start": 0, "center": 1, "bottom": 2, "end": 2, "fill": 3}.get(vertical, 0)
        if bool(node.get("wrap", False)):
            properties["autowrap_mode"] = 2
    elif node_type == "meter":
        properties["min_value"] = float(_number(_resolve_value(node.get("min", 0), tokens), field_name="min"))
        properties["max_value"] = float(_number(_resolve_value(node.get("max", 100), tokens), field_name="max"))
        properties["value"] = float(_number(_resolve_value(node.get("value", 0), tokens), field_name="value"))
        properties["show_percentage"] = bool(node.get("show_percentage", False))
    elif node_type == "image":
        texture = str(_resolve_value(node.get("asset", node.get("texture", "")), tokens)).strip()
        if texture:
            _validate_res_path(texture, field_name="image.asset")
            asset_paths.append(texture)
            properties["texture"] = {"$type": "ResourceRef", "path": texture, "class": "Texture2D"}
        properties["expand_mode"] = int(node.get("expand_mode", 1))
        properties["stretch_mode"] = int(node.get("stretch_mode", 5))
    return properties


def _style_properties(node: dict[str, Any], *, tokens: dict[str, Any], node_type: str) -> dict[str, Any]:
    style = _optional_mapping(node.get("style"), "style")
    properties: dict[str, Any] = {}
    background = style.get("background", style.get("bg", node.get("background")))
    if background is not None and node_type in {"screen", "panel", "button"}:
        stylebox = _stylebox_flat(style, tokens=tokens, background=background)
        target = "theme_override_styles/panel" if node_type in {"screen", "panel"} else "theme_override_styles/normal"
        properties[target] = stylebox
    font_color = style.get("font_color", style.get("text_color", node.get("font_color")))
    if font_color is not None:
        properties["theme_override_colors/font_color"] = _color(_resolve_value(font_color, tokens))
    font_size = style.get("font_size", node.get("font_size"))
    if font_size is not None:
        properties["theme_override_font_sizes/font_size"] = int(_number(_resolve_value(font_size, tokens), field_name="font_size"))
    return properties


def _screen_has_background(node: dict[str, Any]) -> bool:
    style = _optional_mapping(node.get("style"), "style")
    return "background" in style or "bg" in style or "background" in node


def _stylebox_flat(style: dict[str, Any], *, tokens: dict[str, Any], background: Any) -> dict[str, Any]:
    properties: dict[str, Any] = {"bg_color": _color(_resolve_value(background, tokens))}
    radius = style.get("radius", style.get("corner_radius"))
    if radius is not None:
        radius_value = int(_number(_resolve_value(radius, tokens), field_name="radius"))
        for name in ("corner_radius_top_left", "corner_radius_top_right", "corner_radius_bottom_left", "corner_radius_bottom_right"):
            properties[name] = radius_value
    border_color = style.get("border_color")
    if border_color is not None:
        properties["border_color"] = _color(_resolve_value(border_color, tokens))
    border_width = style.get("border_width")
    if border_width is not None:
        width = int(_number(_resolve_value(border_width, tokens), field_name="border_width"))
        for name in ("border_width_left", "border_width_top", "border_width_right", "border_width_bottom"):
            properties[name] = width
    padding = style.get("padding")
    if padding is not None:
        left, top, right, bottom = _box_values(_resolve_value(padding, tokens), field_name="padding")
        properties.update(
            {
                "content_margin_left": left,
                "content_margin_top": top,
                "content_margin_right": right,
                "content_margin_bottom": bottom,
            }
        )
    return {"$type": "SubResource", "class": "StyleBoxFlat", "properties": properties}


def _extra_properties(node: dict[str, Any], *, tokens: dict[str, Any]) -> dict[str, Any]:
    raw_properties = _optional_mapping(node.get("properties"), "properties")
    return {str(key): _resolve_value(value, tokens) for key, value in raw_properties.items()}


def _node_metadata(node: dict[str, Any], *, design_id: str, parent_id: str, node_type: str) -> dict[str, Any]:
    metadata = {
        "test_id": str(node.get("test_id") or design_id),
        "design_id": design_id,
        "design_role": str(node.get("role") or node_type),
        "design_parent_id": parent_id,
    }
    extra = _optional_mapping(node.get("metadata"), "metadata")
    for key, value in extra.items():
        metadata[str(key)] = value
    return metadata


def _collect_node_reports(client: GodotClient, compiled: CompiledDesign, *, viewport: str) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for node in compiled.nodes:
        entry = dict(node)
        selector = {"metadata": {"design_id": node["id"]}}
        try:
            locator = client.locator(selector, root="edited")
            bounds = locator.bounds()
            entry["bounds"] = bounds
            entry["rect"] = _bounds_rect(bounds)
            if node.get("type") in {"text", "button"}:
                try:
                    entry["minimum_size"] = locator.evaluate("node.get_minimum_size()")
                except Exception as exc:
                    entry["minimum_size_error"] = str(exc)
        except Exception as exc:
            entry["bounds_error"] = str(exc)
            entry["issue"] = _issue("error", "bounds_missing", str(exc), viewport=viewport, node=node["id"])
        reports.append(entry)
    return reports


def _layout_issues(node_reports: list[dict[str, Any]], *, width: int, height: int, viewport: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for node in node_reports:
        if "issue" in node:
            issues.append(node["issue"])
            continue
        rect = node.get("rect")
        if not isinstance(rect, dict):
            issues.append(_issue("error", "bounds_missing", "Node did not expose a rectangular Control bound", viewport=viewport, node=node.get("id")))
            continue
        if not _rect_within(rect, width=width, height=height):
            issues.append(_issue("error", "out_of_viewport", f"Bounds {rect} exceed viewport {width}x{height}", viewport=viewport, node=node.get("id")))
        if node.get("type") == "button" and (float(rect.get("width", 0)) < TOUCH_TARGET_MIN_SIZE or float(rect.get("height", 0)) < TOUCH_TARGET_MIN_SIZE):
            issues.append(_issue("error", "small_touch_target", "Button is smaller than 44x44", viewport=viewport, node=node.get("id")))
        min_size = _vector_from_encoded(node.get("minimum_size"))
        if node.get("type") in {"text", "button"} and min_size is not None:
            if min_size[0] > float(rect.get("width", 0)) + 1 or min_size[1] > float(rect.get("height", 0)) + 1:
                issues.append(_issue("error", "text_overflow", f"Minimum text size {min_size} exceeds bounds {rect}", viewport=viewport, node=node.get("id")))

    for left_index, left in enumerate(node_reports):
        left_rect = left.get("rect")
        if not isinstance(left_rect, dict) or left.get("type") == "spacer":
            continue
        for right in node_reports[left_index + 1 :]:
            right_rect = right.get("rect")
            if not isinstance(right_rect, dict) or right.get("type") == "spacer":
                continue
            if left.get("parent_id") != right.get("parent_id"):
                continue
            if _rect_overlap_area(left_rect, right_rect) > 1.0:
                issues.append(
                    _issue(
                        "error",
                        "sibling_overlap",
                        f"Sibling nodes overlap: {left.get('id')} and {right.get('id')}",
                        viewport=viewport,
                        node=left.get("id"),
                    )
                )
    return issues


def _asset_issues(project: str | Path | None, asset_paths: list[str]) -> list[dict[str, Any]]:
    if project is None:
        return []
    project_path = Path(project).expanduser().resolve()
    issues: list[dict[str, Any]] = []
    for asset_path in sorted(dict.fromkeys(asset_paths)):
        local_path = _res_local_path(project_path, asset_path, field_name="image.asset")
        if not local_path.exists():
            issues.append(_issue("error", "missing_asset", f"Asset does not exist: {asset_path}", node=None))
    return issues


def _write_design_reports(report: dict[str, Any], artifacts: Path) -> None:
    json_path = Path(report["report_json"])
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    html_path = Path(report["report_html"])
    html_path.write_text(_html_report(report, html_path.parent), encoding="utf-8")


def _html_report(report: dict[str, Any], report_dir: Path) -> str:
    issues = report.get("issues", [])
    review = report.get("review", {})
    screenshots = []
    for viewport in review.get("viewports", []) if isinstance(review, dict) else []:
        screenshot = viewport.get("screenshot")
        if screenshot:
            href = _relative_href(report_dir, Path(screenshot))
            label = f"{viewport.get('viewport', {}).get('width')}x{viewport.get('viewport', {}).get('height')}"
            screenshots.append(f'<figure><a href="{escape(href)}"><img src="{escape(href)}" alt="{escape(label)}"></a><figcaption>{escape(label)}</figcaption></figure>')
    issue_rows = "\n".join(
        "<tr>"
        f"<td><code>{escape(str(issue.get('severity', '')))}</code></td>"
        f"<td><code>{escape(str(issue.get('code', '')))}</code></td>"
        f"<td>{escape(str(issue.get('viewport', '')))}</td>"
        f"<td><code>{escape(str(issue.get('node', '')))}</code></td>"
        f"<td>{escape(str(issue.get('message', '')))}</td>"
        "</tr>"
        for issue in issues
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Godot UI Design Report</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; background: #111318; color: #eceef4; }}
    body {{ margin: 0; padding: 32px; }}
    header, main {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    h2 {{ margin-top: 28px; font-size: 18px; }}
    .subhead {{ color: #9aa3b2; margin: 0; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin: 24px 0; }}
    .metric {{ background: #1a1e27; border: 1px solid #2a303d; border-radius: 8px; padding: 14px; }}
    .metric span {{ display: block; color: #9aa3b2; font-size: 12px; text-transform: uppercase; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 22px; }}
    .screens {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
    figure {{ margin: 0; background: #1a1e27; border: 1px solid #2a303d; border-radius: 8px; padding: 10px; }}
    img {{ display: block; width: 100%; height: auto; border-radius: 4px; }}
    figcaption {{ margin-top: 8px; color: #9aa3b2; font-size: 13px; }}
    table {{ border-collapse: collapse; width: 100%; background: #1a1e27; border: 1px solid #2a303d; border-radius: 8px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid #2a303d; padding: 9px 10px; text-align: left; vertical-align: top; }}
    th {{ color: #9aa3b2; font-size: 11px; text-transform: uppercase; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
  </style>
</head>
<body>
  <header>
    <p class="subhead">Godot Playwright</p>
    <h1>UI Design Report</h1>
    <p class="subhead">{escape(str(report.get("target_scene", "")))}</p>
  </header>
  <main>
    <section class="metrics">
      <div class="metric"><span>Status</span><strong>{escape("pass" if report.get("ok") else "issues")}</strong></div>
      <div class="metric"><span>Nodes</span><strong>{escape(str(report.get("node_count", 0)))}</strong></div>
      <div class="metric"><span>Issues</span><strong>{escape(str(len(issues)))}</strong></div>
      <div class="metric"><span>Generated</span><strong>{escape(str(bool(report.get("generated"))).lower())}</strong></div>
    </section>
    <h2>Screenshots</h2>
    <section class="screens">{''.join(screenshots) if screenshots else '<p class="subhead">No screenshots captured.</p>'}</section>
    <h2>Issues</h2>
    <table>
      <thead><tr><th>Severity</th><th>Code</th><th>Viewport</th><th>Node</th><th>Message</th></tr></thead>
      <tbody>{issue_rows if issue_rows else '<tr><td colspan="5">No issues.</td></tr>'}</tbody>
    </table>
  </main>
</body>
</html>
"""


def _compiled_summary(compiled: CompiledDesign) -> dict[str, Any]:
    return {
        "name": compiled.name,
        "scene_path": compiled.scene_path,
        "root_class": compiled.root_class,
        "root_name": compiled.root_name,
        "node_count": compiled.node_count,
        "nodes": compiled.nodes,
        "asset_paths": compiled.asset_paths,
        "viewports": [_viewport_dict(width, height) for width, height in compiled.viewports],
    }


def _design_ui_error_message(report: dict[str, Any]) -> str:
    issues = report.get("issues", [])
    first = issues[0] if issues else {}
    return f"Design UI generation reported issues for {report.get('target_scene')}: {first.get('code', 'unknown')}"


def _format_issue(issue: dict[str, Any]) -> str:
    node = f" node={issue.get('node')}" if issue.get("node") else ""
    viewport = f" viewport={issue.get('viewport')}" if issue.get("viewport") else ""
    return f"{issue.get('severity', 'error')} {issue.get('code', 'issue')}{viewport}{node}: {issue.get('message', '')}"


def format_design_ui_report(report: dict[str, Any]) -> str:
    lines = [
        f"Design UI {'PASS' if report.get('ok') else 'ISSUES'}",
        f"scene: {report.get('target_scene')}",
        f"nodes: {report.get('node_count', 0)}",
        f"report: {report.get('report_html')}",
    ]
    issues = report.get("issues", [])
    if issues:
        lines.append("issues:")
        lines.extend(f"- {_format_issue(issue)}" for issue in issues[:20])
        if len(issues) > 20:
            lines.append(f"- ... {len(issues) - 20} more")
    return "\n".join(lines)


def _viewports_from_spec(spec: dict[str, Any]) -> list[tuple[int, int]]:
    review = _optional_mapping(spec.get("review"), "review")
    raw_viewports = review.get("viewports", spec.get("viewports"))
    if raw_viewports is None:
        return list(DEFAULT_VIEWPORTS)
    if not isinstance(raw_viewports, list):
        raise DesignUISpecError("review.viewports must be an array")
    return [_parse_viewport(value) for value in raw_viewports]


def _parse_viewport(value: Any) -> tuple[int, int]:
    if isinstance(value, str):
        text = value.lower().replace(" ", "")
        if "x" not in text:
            raise DesignUISpecError(f"Viewport must be WIDTHxHEIGHT: {value!r}")
        left, right = text.split("x", 1)
        return _positive_int(left, "viewport width"), _positive_int(right, "viewport height")
    if isinstance(value, dict):
        return _positive_int(value.get("width"), "viewport width"), _positive_int(value.get("height"), "viewport height")
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return _positive_int(value[0], "viewport width"), _positive_int(value[1], "viewport height")
    raise DesignUISpecError(f"Viewport must be a string, object, or pair: {value!r}")


def _layout(node: dict[str, Any]) -> dict[str, Any]:
    return _optional_mapping(node.get("layout", node.get("constraints", {})), "layout")


def _resolve_value(value: Any, tokens: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        path = value[1:].split(".")
        current: Any = tokens
        for part in path:
            if not isinstance(current, dict) or part not in current:
                raise DesignUISpecError(f"Unknown design token: {value}")
            current = current[part]
        return current
    if isinstance(value, list):
        return [_resolve_value(item, tokens) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_value(item, tokens) for key, item in value.items()}
    return value


def _color(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and value.get("$type") == "Color":
        return value
    if not isinstance(value, str):
        raise DesignUISpecError(f"Color must be a hex string, got {value!r}")
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) == 6:
        text += "ff"
    if len(text) != 8 or not re.fullmatch(r"[0-9a-fA-F]{8}", text):
        raise DesignUISpecError(f"Invalid color: {value!r}")
    return {
        "$type": "Color",
        "r": int(text[0:2], 16) / 255.0,
        "g": int(text[2:4], 16) / 255.0,
        "b": int(text[4:6], 16) / 255.0,
        "a": int(text[6:8], 16) / 255.0,
    }


def _vector2(x: float, y: float) -> dict[str, Any]:
    return {"$type": "Vector2", "x": float(x), "y": float(y)}


def _vector_from_encoded(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict) and value.get("$type") in {"Vector2", "Vector2i"}:
        return float(value.get("x", 0.0)), float(value.get("y", 0.0))
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return float(value[0]), float(value[1])
    return None


def _anchor_properties(anchor: str) -> dict[str, Any]:
    normalized = anchor.lower().replace("-", "_")
    presets: dict[str, dict[str, Any]] = {
        "full_rect": CONTROL_ROOT_PROPERTIES,
        "fill": CONTROL_ROOT_PROPERTIES,
        "top_left": {"anchor_left": 0.0, "anchor_top": 0.0, "anchor_right": 0.0, "anchor_bottom": 0.0},
        "top_right": {"anchor_left": 1.0, "anchor_top": 0.0, "anchor_right": 1.0, "anchor_bottom": 0.0},
        "bottom_left": {"anchor_left": 0.0, "anchor_top": 1.0, "anchor_right": 0.0, "anchor_bottom": 1.0},
        "bottom_right": {"anchor_left": 1.0, "anchor_top": 1.0, "anchor_right": 1.0, "anchor_bottom": 1.0},
        "center": {"anchor_left": 0.5, "anchor_top": 0.5, "anchor_right": 0.5, "anchor_bottom": 0.5},
        "top": {"anchor_left": 0.5, "anchor_top": 0.0, "anchor_right": 0.5, "anchor_bottom": 0.0},
        "bottom": {"anchor_left": 0.5, "anchor_top": 1.0, "anchor_right": 0.5, "anchor_bottom": 1.0},
        "left": {"anchor_left": 0.0, "anchor_top": 0.5, "anchor_right": 0.0, "anchor_bottom": 0.5},
        "right": {"anchor_left": 1.0, "anchor_top": 0.5, "anchor_right": 1.0, "anchor_bottom": 0.5},
    }
    if normalized not in presets:
        raise DesignUISpecError(f"Unsupported anchor preset: {anchor!r}")
    props = dict(presets[normalized])
    props.setdefault("offset_left", 0.0)
    props.setdefault("offset_top", 0.0)
    props.setdefault("offset_right", 0.0)
    props.setdefault("offset_bottom", 0.0)
    return props


def _size_pair(value: Any, *, field_name: str) -> tuple[float, float]:
    if isinstance(value, dict):
        return _number(value.get("width"), field_name=f"{field_name}.width"), _number(value.get("height"), field_name=f"{field_name}.height")
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return _number(value[0], field_name=f"{field_name}[0]"), _number(value[1], field_name=f"{field_name}[1]")
    raise DesignUISpecError(f"{field_name} must be [width, height] or an object")


def _box_values(value: Any, *, field_name: str) -> tuple[float, float, float, float]:
    if isinstance(value, (int, float)):
        number = float(value)
        return number, number, number, number
    if isinstance(value, (list, tuple)):
        if len(value) == 2:
            vertical = _number(value[0], field_name=field_name)
            horizontal = _number(value[1], field_name=field_name)
            return horizontal, vertical, horizontal, vertical
        if len(value) == 4:
            return tuple(_number(item, field_name=field_name) for item in value)  # type: ignore[return-value]
    if isinstance(value, dict):
        return (
            _number(value.get("left", 0), field_name=f"{field_name}.left"),
            _number(value.get("top", 0), field_name=f"{field_name}.top"),
            _number(value.get("right", 0), field_name=f"{field_name}.right"),
            _number(value.get("bottom", 0), field_name=f"{field_name}.bottom"),
        )
    raise DesignUISpecError(f"{field_name} must be a number, pair, 4-tuple, or object")


def _number(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or value is None:
        raise DesignUISpecError(f"{field_name} must be a number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise DesignUISpecError(f"{field_name} must be a number") from exc


def _positive_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DesignUISpecError(f"{field_name} must be a positive integer") from exc
    if parsed <= 0:
        raise DesignUISpecError(f"{field_name} must be a positive integer")
    return parsed


def _bounds_rect(bounds: Any) -> dict[str, float] | None:
    if not isinstance(bounds, dict) or not isinstance(bounds.get("rect"), dict):
        return None
    rect = bounds["rect"]
    return {
        "x": float(rect.get("x", 0.0)),
        "y": float(rect.get("y", 0.0)),
        "width": float(rect.get("width", 0.0)),
        "height": float(rect.get("height", 0.0)),
    }


def _rect_within(rect: dict[str, float], *, width: int, height: int) -> bool:
    return (
        rect["x"] >= -1
        and rect["y"] >= -1
        and rect["x"] + rect["width"] <= width + 1
        and rect["y"] + rect["height"] <= height + 1
    )


def _rect_overlap_area(left: dict[str, float], right: dict[str, float]) -> float:
    x_overlap = max(0.0, min(left["x"] + left["width"], right["x"] + right["width"]) - max(left["x"], right["x"]))
    y_overlap = max(0.0, min(left["y"] + left["height"], right["y"] + right["height"]) - max(left["y"], right["y"]))
    return x_overlap * y_overlap


def _issue(
    severity: str,
    code: str,
    message: str,
    *,
    viewport: str | None = None,
    node: Any = None,
) -> dict[str, Any]:
    issue = {"severity": severity, "code": code, "message": message}
    if viewport:
        issue["viewport"] = viewport
    if node:
        issue["node"] = node
    return issue


def _issues_are_ok(issues: list[dict[str, Any]]) -> bool:
    return not any(str(issue.get("severity", "error")) == "error" for issue in issues)


def _required_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DesignUISpecError(f"{field_name} must be an object")
    return value


def _optional_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DesignUISpecError(f"{field_name} must be an object")
    return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _design_id(node: dict[str, Any], node_type: str) -> str:
    return _snake_name(str(node.get("id") or node.get("name") or node_type))


def _unique_design_id(base: str, counters: dict[str, int]) -> str:
    base = base or "node"
    count = counters.get(base, 0)
    counters[base] = count + 1
    return base if count == 0 else f"{base}_{count + 1}"


def _snake_name(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").lower()
    return text or "node"


def _pascal_name(value: str) -> str:
    return "".join(part.capitalize() for part in _snake_name(value).split("_")) or "Node"


def _clean_node_name(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_")
    if not text:
        text = "Node"
    if text[0].isdigit():
        text = f"Node{text}"
    return text


def _validate_res_path(path: str, *, field_name: str) -> None:
    if not path.startswith("res://"):
        raise DesignUISpecError(f"{field_name} must be a res:// path")
    _res_relative_path(path, field_name=field_name)


def _ensure_res_parent(project_path: Path, res_path: str) -> None:
    local = _res_local_path(project_path, res_path, field_name="target.scene")
    local.parent.mkdir(parents=True, exist_ok=True)


def _res_local_path(project_path: Path, res_path: str, *, field_name: str) -> Path:
    relative = _res_relative_path(res_path, field_name=field_name)
    root = project_path.expanduser().resolve()
    local = (root / relative).resolve()
    if local != root and not local.is_relative_to(root):
        raise DesignUISpecError(f"{field_name} must stay within the project: {res_path}")
    return local


def _res_relative_path(res_path: str, *, field_name: str) -> PurePosixPath:
    if not res_path.startswith("res://"):
        raise DesignUISpecError(f"{field_name} must be a res:// path")
    relative_text = res_path.removeprefix("res://")
    if not relative_text:
        raise DesignUISpecError(f"{field_name} must include a project-relative path")
    if relative_text.startswith("/") or "\\" in relative_text:
        raise DesignUISpecError(f"{field_name} must be a project-relative res:// path")
    relative = PurePosixPath(relative_text)
    if relative.is_absolute() or any(part == ".." for part in relative.parts):
        raise DesignUISpecError(f"{field_name} must stay within the project: {res_path}")
    return relative


def _artifact_root(path: str | Path) -> Path:
    artifact_path = Path(path).expanduser()
    if artifact_path.is_absolute():
        return artifact_path
    return Path.cwd() / artifact_path


def _relative_href(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _viewport_dict(width: int, height: int) -> dict[str, int]:
    return {"width": int(width), "height": int(height)}

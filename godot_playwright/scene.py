from __future__ import annotations

import re
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


SECTION_PATTERN = re.compile(r"^\s*\[(?P<name>[A-Za-z0-9_]+)(?P<body>.*)\]\s*$")
ATTRIBUTE_PATTERN = re.compile(r'([A-Za-z0-9_./-]+)=("(?:[^"\\]|\\.)*"|\[(?:[^\]\\]|\\.)*\]|[^\s\]]+)')
RESOURCE_REF_PATTERN = re.compile(r'^(ExtResource|SubResource)\("([^"]+)"\)$')
CALL_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\((.*)\)$")


class SceneInspectError(RuntimeError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(_scene_inspect_error_message(report))


def inspect_project_scenes(
    project: str | Path,
    scenes: list[str | Path] | None = None,
    *,
    exclude: list[str] | None = None,
    include_properties: bool = True,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    started = time.monotonic()
    scene_paths = _discover_text_scenes(project_path, scenes or [], exclude or [])
    reports = [
        inspect_scene(project_path, scene, include_properties=include_properties)
        for scene in scene_paths
    ]
    failed_reports = [report for report in reports if not report.get("ok")]
    diagnostics = []
    for report in failed_reports:
        for diagnostic in report.get("diagnostics", []):
            merged = dict(diagnostic)
            merged["scene"] = report.get("scene")
            diagnostics.append(merged)
    report = {
        "project": str(project_path),
        "ok": not failed_reports,
        "scene_count": len(reports),
        "passed": len(reports) - len(failed_reports),
        "failed": len(failed_reports),
        "scenes": reports,
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
        "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
    }
    if check and not report["ok"]:
        raise SceneInspectError(report)
    return report


def inspect_scene(
    project: str | Path,
    scene_path: str | Path,
    *,
    include_properties: bool = True,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    started = time.monotonic()
    scene = _resource_res_path(project_path, scene_path)
    global_path = _resource_global_path(project_path, scene)
    diagnostics: list[dict[str, Any]] = []

    if not global_path.is_file():
        report = _scene_report(
            project_path,
            scene,
            global_path,
            started,
            exists=False,
            include_properties=include_properties,
            diagnostics=[
                {
                    "severity": "error",
                    "kind": "SCENE_NOT_FOUND",
                    "message": f"Scene file not found: {scene}",
                    "path": scene,
                    "global_path": str(global_path),
                    "line": None,
                }
            ],
        )
        if check:
            raise SceneInspectError(report)
        return report

    try:
        text = global_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        report = _scene_report(
            project_path,
            scene,
            global_path,
            started,
            exists=True,
            include_properties=include_properties,
            diagnostics=[
                {
                    "severity": "error",
                    "kind": "SCENE_READ_ERROR",
                    "message": f"Scene is not UTF-8 text: {exc}",
                    "path": scene,
                    "global_path": str(global_path),
                    "line": None,
                }
            ],
        )
        if check:
            raise SceneInspectError(report)
        return report

    parsed = _parse_scene_text(project_path, scene, global_path, text, include_properties)
    diagnostics.extend(parsed["diagnostics"])
    report = _scene_report(
        project_path,
        scene,
        global_path,
        started,
        exists=True,
        include_properties=include_properties,
        diagnostics=diagnostics,
        header=parsed["header"],
        ext_resources=parsed["ext_resources"],
        sub_resources=parsed["sub_resources"],
        connections=parsed["connections"],
        root=parsed["root"],
        nodes=parsed["nodes"],
    )
    if check and not report["ok"]:
        raise SceneInspectError(report)
    return report


class SceneFileExpect:
    def __init__(self, project: str | Path, scene_path: str | Path):
        self.project = Path(project).expanduser().resolve()
        self.scene_path = scene_path

    def to_exist(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_report(
            lambda report: bool(report.get("exists")),
            lambda report: f"Expected scene file {self.scene_path!r} to exist; last={report!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_be_valid(self, *, timeout: float = 5.0, interval: float = 0.05) -> dict[str, Any]:
        return self._wait_for_report(
            lambda report: bool(report.get("ok")),
            lambda report: f"Expected scene file {self.scene_path!r} to be valid; diagnostics={report.get('diagnostics', [])!r}",
            timeout=timeout,
            interval=interval,
        )

    def to_have_root(
        self,
        *,
        name: str | None = None,
        class_name: str | None = None,
        properties: dict[str, Any] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_report(
            lambda report: _scene_node_matches(
                report.get("root"),
                name=name,
                class_name=class_name,
                properties=properties,
            ),
            lambda report: (
                f"Expected scene file {self.scene_path!r} root "
                f"{_scene_node_filter_summary(name=name, class_name=class_name, properties=properties)}; "
                f"root={report.get('root')!r}"
            ),
            timeout=timeout,
            interval=interval,
        )["root"]

    def to_have_node(
        self,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        properties: dict[str, Any] | None = None,
        script: str | None = None,
        instance_path: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(report: dict[str, Any]) -> dict[str, Any] | None:
            for node in report.get("nodes", []):
                if _scene_node_matches(
                    node,
                    name=name,
                    path=path,
                    class_name=class_name,
                    properties=properties,
                    script=script,
                    instance_path=instance_path,
                    groups=groups,
                ):
                    return node
            return None

        return self._wait_for_report(
            lambda report: match(report) is not None,
            lambda report: (
                f"Expected scene file {self.scene_path!r} to have node "
                f"{_scene_node_filter_summary(name=name, path=path, class_name=class_name, properties=properties, script=script, instance_path=instance_path, groups=groups)}; "
                f"nodes={report.get('nodes', [])!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda report: match(report) or {},
        )

    def not_to_have_node(
        self,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        properties: dict[str, Any] | None = None,
        script: str | None = None,
        instance_path: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        return self._wait_for_report(
            lambda report: not any(
                _scene_node_matches(
                    node,
                    name=name,
                    path=path,
                    class_name=class_name,
                    properties=properties,
                    script=script,
                    instance_path=instance_path,
                    groups=groups,
                )
                for node in report.get("nodes", [])
            ),
            lambda report: (
                f"Expected scene file {self.scene_path!r} not to have node "
                f"{_scene_node_filter_summary(name=name, path=path, class_name=class_name, properties=properties, script=script, instance_path=instance_path, groups=groups)}; "
                f"nodes={report.get('nodes', [])!r}"
            ),
            timeout=timeout,
            interval=interval,
        )

    def to_have_node_count(
        self,
        expected: int,
        *,
        name: str | None = None,
        path: str | None = None,
        class_name: str | None = None,
        properties: dict[str, Any] | None = None,
        script: str | None = None,
        instance_path: str | None = None,
        groups: list[str] | tuple[str, ...] | set[str] | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> list[dict[str, Any]]:
        def matches(report: dict[str, Any]) -> list[dict[str, Any]]:
            return [
                node
                for node in report.get("nodes", [])
                if _scene_node_matches(
                    node,
                    name=name,
                    path=path,
                    class_name=class_name,
                    properties=properties,
                    script=script,
                    instance_path=instance_path,
                    groups=groups,
                )
            ]

        return self._wait_for_report(
            lambda report: len(matches(report)) == expected,
            lambda report: (
                f"Expected scene file {self.scene_path!r} node count {expected} for "
                f"{_scene_node_filter_summary(name=name, path=path, class_name=class_name, properties=properties, script=script, instance_path=instance_path, groups=groups)}; "
                f"got {len(matches(report))}"
            ),
            timeout=timeout,
            interval=interval,
            transform=matches,
        )

    def to_have_ext_resource(
        self,
        *,
        path: str | None = None,
        resource_type: str | None = None,
        uid: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(report: dict[str, Any]) -> dict[str, Any] | None:
            for resource in report.get("ext_resources", []):
                if not isinstance(resource, dict):
                    continue
                if path is not None and resource.get("path") != path:
                    continue
                if resource_type is not None and resource.get("type") != resource_type:
                    continue
                if uid is not None and resource.get("uid") != uid:
                    continue
                return resource
            return None

        return self._wait_for_report(
            lambda report: match(report) is not None,
            lambda report: (
                f"Expected scene file {self.scene_path!r} external resource "
                f"path={path!r} resource_type={resource_type!r} uid={uid!r}; "
                f"resources={report.get('ext_resources', [])!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda report: match(report) or {},
        )

    def to_have_connection(
        self,
        signal: str,
        *,
        from_node: str | None = None,
        to: str | None = None,
        method: str | None = None,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> dict[str, Any]:
        def match(report: dict[str, Any]) -> dict[str, Any] | None:
            for connection in report.get("connections", []):
                if not isinstance(connection, dict):
                    continue
                if signal and connection.get("signal") != signal:
                    continue
                if from_node is not None and connection.get("from") != from_node:
                    continue
                if to is not None and connection.get("to") != to:
                    continue
                if method is not None and connection.get("method") != method:
                    continue
                return connection
            return None

        return self._wait_for_report(
            lambda report: match(report) is not None,
            lambda report: (
                f"Expected scene file {self.scene_path!r} connection "
                f"signal={signal!r} from_node={from_node!r} to={to!r} method={method!r}; "
                f"connections={report.get('connections', [])!r}"
            ),
            timeout=timeout,
            interval=interval,
            transform=lambda report: match(report) or {},
        )

    def _wait_for_report(
        self,
        predicate: Any,
        message: Any,
        *,
        timeout: float,
        interval: float,
        transform: Any = None,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while True:
            last = inspect_scene(self.project, self.scene_path)
            if predicate(last):
                return transform(last) if transform is not None else last
            if time.monotonic() >= deadline:
                raise AssertionError(message(last))
            time.sleep(interval)


def expect_scene_file(project: str | Path, scene_path: str | Path) -> SceneFileExpect:
    return SceneFileExpect(project, scene_path)


def _scene_node_matches(
    node: Any,
    *,
    name: str | None = None,
    path: str | None = None,
    class_name: str | None = None,
    properties: dict[str, Any] | None = None,
    script: str | None = None,
    instance_path: str | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
) -> bool:
    if not isinstance(node, dict):
        return False
    if name is not None and node.get("name") != name:
        return False
    if path is not None and not _scene_node_path_matches(node, path):
        return False
    if class_name is not None and node.get("class") != class_name and node.get("type") != class_name:
        return False
    if properties is not None:
        node_properties = node.get("properties", {})
        if not isinstance(node_properties, dict) or not _dict_contains(node_properties, properties):
            return False
    if script is not None:
        script_value = node.get("properties", {}).get("script") if isinstance(node.get("properties"), dict) else None
        if not isinstance(script_value, dict) or script_value.get("path") != script:
            return False
    if instance_path is not None:
        instance = node.get("instance")
        if not isinstance(instance, dict) or instance.get("path") != instance_path:
            return False
    if groups is not None:
        node_groups = {str(group) for group in node.get("groups", [])}
        if not all(str(group) in node_groups for group in groups):
            return False
    return True


def _scene_node_path_matches(node: dict[str, Any], expected: str) -> bool:
    if expected.startswith("/"):
        return node.get("path") == expected
    return node.get("scene_path") == expected.strip("/")


def _scene_node_filter_summary(
    *,
    name: str | None = None,
    path: str | None = None,
    class_name: str | None = None,
    properties: dict[str, Any] | None = None,
    script: str | None = None,
    instance_path: str | None = None,
    groups: list[str] | tuple[str, ...] | set[str] | None = None,
) -> str:
    filters = []
    if name is not None:
        filters.append(f"name={name!r}")
    if path is not None:
        filters.append(f"path={path!r}")
    if class_name is not None:
        filters.append(f"class_name={class_name!r}")
    if properties is not None:
        filters.append(f"properties={properties!r}")
    if script is not None:
        filters.append(f"script={script!r}")
    if instance_path is not None:
        filters.append(f"instance_path={instance_path!r}")
    if groups is not None:
        filters.append(f"groups={list(groups)!r}")
    return ", ".join(filters) if filters else "any node"


def _dict_contains(value: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, expected_value in expected.items():
        if key not in value:
            return False
        actual_value = value[key]
        if isinstance(actual_value, dict) and isinstance(expected_value, dict):
            if not _dict_contains(actual_value, expected_value):
                return False
        elif actual_value != expected_value:
            return False
    return True


def _parse_scene_text(
    project_path: Path,
    scene: str,
    global_path: Path,
    text: str,
    include_properties: bool,
) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    header: dict[str, Any] = {}
    ext_resources: list[dict[str, Any]] = []
    sub_resources: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []
    raw_nodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        section = SECTION_PATTERN.match(line)
        if section:
            section_name = section.group("name")
            attrs = _parse_attrs(section.group("body"))
            current = None
            if section_name == "gd_scene":
                header = _scene_header(attrs)
            elif section_name == "ext_resource":
                ext_resources.append(_ext_resource(project_path, attrs, line_number))
            elif section_name == "sub_resource":
                current = _sub_resource(attrs, line_number)
                sub_resources.append(current)
            elif section_name == "node":
                current = _raw_node(attrs, line_number, len(raw_nodes))
                raw_nodes.append(current)
            elif section_name == "connection":
                connections.append(_connection(attrs, line_number))
            continue

        if "=" not in line:
            diagnostics.append(
                {
                    "severity": "warning",
                    "kind": "UNPARSED_SCENE_LINE",
                    "message": "Scene line is not a section or property assignment",
                    "path": scene,
                    "line": line_number,
                    "text": stripped,
                }
            )
            continue
        if current is None or current.get("$section") not in {"node", "sub_resource"}:
            continue
        if include_properties:
            name, value = line.split("=", 1)
            current["raw_properties"].append(
                {
                    "name": name.strip(),
                    "raw": value.strip(),
                    "line": line_number,
                }
            )

    ext_by_id = {str(resource.get("id", "")): resource for resource in ext_resources if resource.get("id", "") != ""}
    sub_by_id = {str(resource.get("id", "")): resource for resource in sub_resources if resource.get("id", "") != ""}
    for sub_resource in sub_resources:
        _finalize_properties(sub_resource, ext_by_id, sub_by_id)
    nodes, root = _build_scene_tree(raw_nodes, ext_by_id, sub_by_id, diagnostics, scene)
    if root is None:
        diagnostics.append(
            {
                "severity": "error",
                "kind": "SCENE_ROOT_MISSING",
                "message": "Scene has no root [node] section",
                "path": scene,
                "line": None,
            }
        )

    return {
        "header": header,
        "ext_resources": ext_resources,
        "sub_resources": [_public_sub_resource(item) for item in sub_resources],
        "connections": connections,
        "root": root,
        "nodes": [_flat_node(node) for node in nodes],
        "diagnostics": diagnostics,
    }


def _discover_text_scenes(project_path: Path, scenes: list[str | Path], exclude: list[str]) -> list[str]:
    discovered: list[str] = []
    roots = scenes or ["res://"]
    for raw in roots:
        for scene in _expand_text_scene_path(project_path, raw):
            if _is_excluded(scene, exclude):
                continue
            discovered.append(scene)
    return sorted(dict.fromkeys(discovered))


def _expand_text_scene_path(project_path: Path, raw: str | Path) -> list[str]:
    raw_text = str(raw)
    if raw_text.startswith("res://"):
        local = project_path / raw_text.removeprefix("res://")
        prefix = raw_text.rstrip("/")
    else:
        local = Path(raw)
        if not local.is_absolute():
            local = project_path / local
        local = local.resolve()
        try:
            prefix = "res://" + local.relative_to(project_path).as_posix()
        except ValueError:
            prefix = str(local)
    if local.is_file():
        return [prefix] if local.suffix == ".tscn" else []
    if not local.is_dir():
        return [prefix] if Path(raw_text).suffix == ".tscn" else []
    scene_paths = []
    for scene in local.rglob("*.tscn"):
        if _is_ignored_scene_path(project_path, scene):
            continue
        try:
            scene_paths.append("res://" + scene.resolve().relative_to(project_path).as_posix())
        except ValueError:
            scene_paths.append(str(scene.resolve()))
    return scene_paths


def _is_ignored_scene_path(project_path: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(project_path)
    except ValueError:
        relative = path
    return any(part in {".godot", "__pycache__"} for part in relative.parts)


def _is_excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) or fnmatch(path.removeprefix("res://"), pattern) for pattern in patterns)


def _scene_report(
    project_path: Path,
    scene: str,
    global_path: Path,
    started: float,
    *,
    exists: bool,
    include_properties: bool,
    diagnostics: list[dict[str, Any]],
    header: dict[str, Any] | None = None,
    ext_resources: list[dict[str, Any]] | None = None,
    sub_resources: list[dict[str, Any]] | None = None,
    connections: list[dict[str, Any]] | None = None,
    root: dict[str, Any] | None = None,
    nodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    error_count = sum(1 for item in diagnostics if item.get("severity") == "error")
    node_list = nodes or []
    return {
        "project": str(project_path),
        "scene": scene,
        "scene_path": str(global_path),
        "exists": exists,
        "ok": exists and error_count == 0,
        "include_properties": include_properties,
        "header": header or {},
        "root": root,
        "nodes": node_list,
        "node_count": len(node_list),
        "ext_resources": ext_resources or [],
        "ext_resource_count": len(ext_resources or []),
        "sub_resources": sub_resources or [],
        "sub_resource_count": len(sub_resources or []),
        "connections": connections or [],
        "connection_count": len(connections or []),
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
        "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
    }


def _scene_header(attrs: dict[str, str]) -> dict[str, Any]:
    header: dict[str, Any] = {}
    for key, value in attrs.items():
        header[key] = _parse_simple_header_value(value)
    return header


def _ext_resource(project_path: Path, attrs: dict[str, str], line_number: int) -> dict[str, Any]:
    path = attrs.get("path", "")
    global_path = ""
    exists: bool | None = None
    if path.startswith("res://"):
        file_path = (project_path / path.removeprefix("res://")).resolve()
        global_path = str(file_path)
        exists = file_path.is_file()
    return {
        "id": attrs.get("id", ""),
        "type": attrs.get("type", ""),
        "path": path,
        "uid": attrs.get("uid", ""),
        "line": line_number,
        "global_path": global_path,
        "exists": exists,
    }


def _sub_resource(attrs: dict[str, str], line_number: int) -> dict[str, Any]:
    return {
        "$section": "sub_resource",
        "id": attrs.get("id", ""),
        "type": attrs.get("type", ""),
        "line": line_number,
        "raw_properties": [],
        "properties": {},
        "property_count": 0,
    }


def _public_sub_resource(resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": resource.get("id", ""),
        "type": resource.get("type", ""),
        "line": resource.get("line"),
        "properties": resource.get("properties", {}),
        "property_count": resource.get("property_count", 0),
    }


def _raw_node(attrs: dict[str, str], line_number: int, index: int) -> dict[str, Any]:
    return {
        "$section": "node",
        "name": attrs.get("name", ""),
        "type": attrs.get("type", ""),
        "parent": attrs.get("parent", ""),
        "instance_raw": attrs.get("instance", ""),
        "groups": _parse_string_array(attrs.get("groups", "")),
        "line": line_number,
        "index": index,
        "raw_properties": [],
        "properties": {},
        "property_count": 0,
    }


def _connection(attrs: dict[str, str], line_number: int) -> dict[str, Any]:
    return {
        "signal": attrs.get("signal", ""),
        "from": attrs.get("from", ""),
        "to": attrs.get("to", ""),
        "method": attrs.get("method", ""),
        "flags": _parse_simple_header_value(attrs.get("flags", "")) if attrs.get("flags", "") != "" else None,
        "line": line_number,
    }


def _build_scene_tree(
    raw_nodes: list[dict[str, Any]],
    ext_by_id: dict[str, dict[str, Any]],
    sub_by_id: dict[str, dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    scene: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    root_raw = next((node for node in raw_nodes if node.get("parent", "") == ""), None)
    root_name = str(root_raw.get("name", "")) if root_raw is not None else ""
    nodes: list[dict[str, Any]] = []
    by_scene_path: dict[str, dict[str, Any]] = {}

    for raw in raw_nodes:
        _finalize_properties(raw, ext_by_id, sub_by_id)
        parent_raw = str(raw.get("parent", ""))
        scene_path = _node_scene_path(root_name, parent_raw, str(raw.get("name", "")))
        parent_scene_path = _parent_scene_path(root_name, parent_raw)
        instance = _parse_value(str(raw.get("instance_raw", "")), ext_by_id, sub_by_id) if raw.get("instance_raw") else None
        node = {
            "name": raw.get("name", ""),
            "class": raw.get("type", ""),
            "type": raw.get("type", ""),
            "path": f"/{scene_path}" if scene_path else "",
            "scene_path": scene_path,
            "parent": parent_raw,
            "parent_path": f"/{parent_scene_path}" if parent_scene_path else "",
            "instance": instance,
            "groups": list(raw.get("groups", [])),
            "line": raw.get("line"),
            "index": raw.get("index"),
            "properties": raw.get("properties", {}),
            "property_count": raw.get("property_count", 0),
            "children": [],
        }
        nodes.append(node)
        if scene_path:
            by_scene_path[scene_path] = node

    root: dict[str, Any] | None = None
    for node in nodes:
        if node.get("parent", "") == "":
            if root is None:
                root = node
            else:
                diagnostics.append(
                    {
                        "severity": "error",
                        "kind": "MULTIPLE_SCENE_ROOTS",
                        "message": f"Multiple root nodes found; extra root: {node.get('name')}",
                        "path": scene,
                        "line": node.get("line"),
                    }
                )
            continue
        parent_path = str(node.get("parent_path", "")).removeprefix("/")
        parent = by_scene_path.get(parent_path)
        if parent is None:
            diagnostics.append(
                {
                    "severity": "error",
                    "kind": "ORPHAN_SCENE_NODE",
                    "message": f"Node parent not found: {node.get('parent')}",
                    "path": scene,
                    "line": node.get("line"),
                    "node": node.get("scene_path"),
                }
            )
            continue
        parent["children"].append(node)

    return nodes, root


def _node_scene_path(root_name: str, parent_raw: str, name: str) -> str:
    if parent_raw == "":
        return name
    if root_name == "":
        return name
    parent = _normalize_parent_scene_path(parent_raw)
    if parent == "":
        return f"{root_name}/{name}"
    return f"{root_name}/{parent}/{name}"


def _parent_scene_path(root_name: str, parent_raw: str) -> str:
    if parent_raw == "":
        return ""
    if root_name == "":
        return _normalize_parent_scene_path(parent_raw)
    parent = _normalize_parent_scene_path(parent_raw)
    if parent == "":
        return root_name
    return f"{root_name}/{parent}"


def _normalize_parent_scene_path(parent_raw: str) -> str:
    parent = parent_raw.strip("/")
    while parent.startswith("./"):
        parent = parent[2:]
    return "" if parent == "." else parent


def _finalize_properties(
    item: dict[str, Any],
    ext_by_id: dict[str, dict[str, Any]],
    sub_by_id: dict[str, dict[str, Any]],
) -> None:
    properties = {}
    for property_item in item.get("raw_properties", []):
        properties[property_item["name"]] = _parse_value(property_item["raw"], ext_by_id, sub_by_id)
    item["properties"] = properties
    item["property_count"] = len(properties)


def _flat_node(node: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in node.items() if key != "children"}


def _parse_attrs(body: str) -> dict[str, str]:
    return {key: _strip_quotes(value) for key, value in ATTRIBUTE_PATTERN.findall(body)}


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return _unescape_godot_string(value[1:-1])
    return value


def _unescape_godot_string(value: str) -> str:
    return value.replace(r"\"", '"').replace(r"\\", "\\").replace(r"\n", "\n").replace(r"\t", "\t")


def _parse_string_array(value: str) -> list[str]:
    text = value.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return []
    body = text[1:-1].strip()
    if body == "":
        return []
    items: list[str] = []
    current = []
    in_string = False
    escaped = False
    for char in body:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\" and in_string:
            current.append(char)
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            current.append(char)
            continue
        if char == "," and not in_string:
            item = _strip_quotes("".join(current).strip())
            if item:
                items.append(item)
            current = []
            continue
        current.append(char)
    item = _strip_quotes("".join(current).strip())
    if item:
        items.append(item)
    return items


def _parse_simple_header_value(value: str) -> Any:
    if value == "":
        return ""
    if value in {"true", "false"}:
        return value == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?", value):
        return float(value)
    return value


def _parse_value(
    raw: str,
    ext_by_id: dict[str, dict[str, Any]],
    sub_by_id: dict[str, dict[str, Any]],
) -> Any:
    raw = raw.strip()
    if raw == "":
        return ""
    if raw.startswith('"') and raw.endswith('"'):
        return _strip_quotes(raw)
    if raw in {"true", "false"}:
        return raw == "true"
    if raw in {"null", "nil"}:
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?", raw):
        return float(raw)
    resource_ref = RESOURCE_REF_PATTERN.match(raw)
    if resource_ref:
        kind, resource_id = resource_ref.groups()
        if kind == "ExtResource":
            resource = ext_by_id.get(resource_id, {})
            return {
                "$type": "ExtResource",
                "id": resource_id,
                "path": resource.get("path", ""),
                "resource_type": resource.get("type", ""),
                "uid": resource.get("uid", ""),
            }
        resource = sub_by_id.get(resource_id, {})
        return {
            "$type": "SubResource",
            "id": resource_id,
            "resource_type": resource.get("type", ""),
        }
    call = CALL_PATTERN.match(raw)
    if call and call.group(1) in {"Vector2", "Vector2i", "Vector3", "Vector3i", "Color", "Rect2", "NodePath"}:
        name = call.group(1)
        args = _parse_call_args(call.group(2), ext_by_id, sub_by_id)
        if name == "NodePath" and len(args) == 1:
            return {"$type": name, "path": args[0]}
        return {"$type": name, "args": args, "raw": raw}
    return {"$raw": raw}


def _parse_call_args(
    raw_args: str,
    ext_by_id: dict[str, dict[str, Any]],
    sub_by_id: dict[str, dict[str, Any]],
) -> list[Any]:
    args: list[Any] = []
    current = []
    depth = 0
    in_string = False
    escaped = False
    for char in raw_args:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\" and in_string:
            current.append(char)
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            current.append(char)
            continue
        if not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                args.append(_parse_value("".join(current).strip(), ext_by_id, sub_by_id))
                current = []
                continue
        current.append(char)
    if current or raw_args.strip():
        args.append(_parse_value("".join(current).strip(), ext_by_id, sub_by_id))
    return args


def _resource_res_path(project_path: Path, resource_path: str | Path) -> str:
    resource = str(resource_path)
    if resource.startswith("res://"):
        return resource
    path = Path(resource_path)
    if not path.is_absolute():
        path = project_path / path
    path = path.resolve()
    try:
        return "res://" + path.relative_to(project_path).as_posix()
    except ValueError:
        return str(path)


def _resource_global_path(project_path: Path, resource_path: str) -> Path:
    if resource_path.startswith("res://"):
        return (project_path / resource_path.removeprefix("res://")).resolve()
    return Path(resource_path).expanduser().resolve()


def _scene_inspect_error_message(report: dict[str, Any]) -> str:
    diagnostics = report.get("diagnostics", [])
    if diagnostics:
        details = "\n".join(
            f"{item.get('kind')}: {item.get('message')} {item.get('path', '')}:{item.get('line', '')}".rstrip(":")
            for item in diagnostics[:8]
        )
    else:
        details = "unknown error"
    return f"Godot scene inspection failed for {report.get('scene')!r}\n{details}"

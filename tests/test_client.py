from __future__ import annotations

import base64
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from godot_playwright import (
    GodotClient,
    GodotPlaywrightError,
    expect,
    expect_engine,
    expect_editor,
    expect_filesystem,
    expect_inspector,
    expect_log,
    expect_node_class,
    expect_physics2d,
    expect_physics3d,
    expect_project,
    expect_project_scene,
    expect_resource,
    expect_resource_class,
    expect_runtime_scene,
    expect_script,
    expect_script_class,
    expect_signal,
    expect_trace,
    expect_viewport,
)
from godot_playwright.client import _GodotLogCollector


def _selector_is_missing(selector: Any) -> bool:
    if isinstance(selector, str) and selector in {"#Missing", "test_id=missing", "testid=missing"}:
        return True
    if not isinstance(selector, dict):
        return False
    metadata = selector.get("metadata", selector.get("meta", {}))
    return (
        selector.get("name") == "Missing"
        or selector.get("test_id") == "missing"
        or selector.get("testid") == "missing"
        or selector.get("path") == "/root/Main/Missing"
        or (isinstance(metadata, dict) and metadata.get("test_id") == "missing")
    )


def _fake_selector_name(selector: Any) -> str:
    if isinstance(selector, dict):
        if selector.get("name"):
            return str(selector["name"])
        if selector.get("test_id"):
            return str(selector["test_id"]).title().replace("-", "")
        if selector.get("path"):
            return str(selector["path"]).rsplit("/", 1)[-1]
    text = str(selector)
    if text in {"edited", "scene"}:
        return "Main"
    return text.rsplit("/", 1)[-1].lstrip("#")


def _fake_selector_path(selector: Any) -> str:
    if isinstance(selector, dict) and selector.get("path"):
        return str(selector["path"])
    text = str(selector)
    if text in {"edited", "scene"}:
        return "/root/Main"
    if text.startswith("/"):
        return text
    return f"/root/Main/{_fake_selector_name(selector)}"


def _fake_node_summary(selector: Any, server: Any, *, class_name: str | None = None) -> dict[str, Any]:
    path = _fake_selector_path(selector)
    stored = getattr(server, "node_summaries", {}).get(path)
    if stored:
        return dict(stored)
    parent = path.rsplit("/", 1)[0] if "/" in path.strip("/") else ""
    groups = sorted(getattr(server, "node_groups", {}).get(path, set()))
    name = _fake_selector_name(selector)
    return {
        "name": name,
        "class": class_name or "Button",
        "path": path,
        "parent": parent,
        "index": getattr(server, "node_indices", {}).get(path, 0),
        "groups": groups,
        "owner": "/root/Main",
        "child_count": 0,
    }


def _selector_key(selector: Any) -> str:
    return json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)


def _fake_text_for_selector(selector: Any) -> str:
    name = _fake_selector_name(selector)
    if name == "Title":
        return "Godot Playwright"
    if name == "NextSceneButton":
        return "Next Scene"
    return "Clicked 1"


def _fake_res_parent_dirs(path: str) -> set[str]:
    dirs = {"res://"}
    tail = path.removeprefix("res://").strip("/")
    if not tail:
        return dirs
    parts = tail.split("/")
    for index in range(1, len(parts)):
        dirs.add("res://" + "/".join(parts[:index]))
    return dirs


def _fake_resource_type_for_path(path: str) -> str:
    extension = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    return {
        "gd": "GDScript",
        "tscn": "PackedScene",
        "scn": "PackedScene",
        "tres": "Resource",
        "res": "Resource",
        "png": "CompressedTexture2D",
    }.get(extension, "")


_FAKE_IMPORTABLE_EXTENSIONS = {
    "apng",
    "bmp",
    "exr",
    "fbx",
    "glb",
    "gltf",
    "hdr",
    "jpg",
    "jpeg",
    "mp3",
    "obj",
    "ogg",
    "otf",
    "png",
    "svg",
    "tga",
    "ttf",
    "wav",
    "webp",
    "woff",
    "woff2",
}


def _fake_import_metadata_summary(
    path: str,
    files: dict[str, str | bytes],
    import_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_exists = path in files
    diagnostics = [
        {
            "kind": "IMPORT_FILE_MISSING",
            "severity": "warning" if source_exists else "error",
            "path": f"{path}.import",
            "source": path,
            "message": f"Import metadata file is missing: {path}.import",
        }
    ]
    return import_metadata.get(
        path,
        {
            "path": path,
            "global_path": f"/fake/project/{path.removeprefix('res://')}",
            "source_exists": source_exists,
            "import_path": f"{path}.import",
            "import_file": _fake_file_summary(f"{path}.import", files, exists=False),
            "source_file_state": _fake_file_summary(path, files),
            "exists": False,
            "imported": False,
            "resource_exists": False,
            "resource_type": "",
            "importer": "",
            "type": "",
            "uid": "",
            "source_file": "",
            "source_file_matches_path": True,
            "dest_files": [],
            "generated_files": [],
            "generated_files_ready": False,
            "generated_file_count": 0,
            "missing_generated_files": [],
            "missing_generated_file_count": 0,
            "stale_generated_files": [],
            "stale_generated_file_count": 0,
            "import_file_stale": False,
            "parse_error": 0,
            "remap": {},
            "deps": {},
            "params": {},
            "sections": {},
            "diagnostics": diagnostics,
            "diagnostic_count": len(diagnostics),
            "error_count": sum(1 for item in diagnostics if item["severity"] == "error"),
            "warning_count": sum(1 for item in diagnostics if item["severity"] == "warning"),
            "ok": False,
        },
    )


def _fake_resource_imports(
    files: dict[str, str | bytes],
    import_metadata: dict[str, dict[str, Any]],
    *,
    path: str = "res://",
    name: str = "",
    name_contains: str = "",
    importer: str = "",
    resource_type: str = "",
    extensions: list[str] | None = None,
    generated_files_ready: bool | None = None,
    imported: bool | None = None,
    ok: bool | None = None,
    include_missing_metadata: bool = True,
    max_results: int = 200,
) -> dict[str, Any]:
    extension_filter = {item.removeprefix(".").lower() for item in (extensions or sorted(_FAKE_IMPORTABLE_EXTENSIONS))}
    source_paths = sorted(
        file_path
        for file_path in (set(files) | set(import_metadata))
        if (file_path == path or file_path.startswith(path.rstrip("/") + "/") or path == "res://")
        and not file_path.endswith(".import")
        and file_path.rsplit(".", 1)[-1].lower() in extension_filter
    )
    imports: list[dict[str, Any]] = []
    total_matches = 0
    for source_path in source_paths:
        entry = _fake_import_metadata_summary(source_path, files, import_metadata)
        if not include_missing_metadata and not entry.get("exists"):
            continue
        if name and source_path.rsplit("/", 1)[-1] != name:
            continue
        if name_contains and name_contains not in source_path.rsplit("/", 1)[-1] and name_contains not in source_path:
            continue
        if importer and entry.get("importer") != importer:
            continue
        if resource_type and entry.get("resource_type") != resource_type and entry.get("type") != resource_type:
            continue
        if generated_files_ready is not None and bool(entry.get("generated_files_ready")) != generated_files_ready:
            continue
        if imported is not None and bool(entry.get("imported")) != imported:
            continue
        if ok is not None and bool(entry.get("ok")) != ok:
            continue
        total_matches += 1
        if len(imports) < max_results:
            imports.append(entry)
    return {
        "path": path,
        "global_path": f"/fake/project/{path.removeprefix('res://')}",
        "recursive": True,
        "include_hidden": False,
        "include_missing_metadata": include_missing_metadata,
        "extensions": sorted(extension_filter),
        "name": name,
        "name_contains": name_contains,
        "importer": importer,
        "resource_type": resource_type,
        "generated_files_ready": generated_files_ready,
        "imported": imported,
        "ok": ok,
        "imports": imports,
        "count": len(imports),
        "total_matches": total_matches,
        "truncated": total_matches > len(imports),
        "max_results": max_results,
        "scanned": len(source_paths),
    }


def _fake_script_source(path: str, files: dict[str, str | bytes]) -> str:
    value = files.get(path)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return "extends Node\n\nfunc generated_value() -> int:\n\treturn 42\n"


def _fake_symbol_name(line: str, prefix: str) -> str:
    value = line.removeprefix(prefix).strip()
    if value.startswith(("'", '"')):
        quote = value[0]
        end = value.find(quote, 1)
        if end >= 0:
            return value[1:end].strip()
    for separator in (" ", "(", ":", "=", "\t"):
        if separator in value:
            value = value.split(separator, 1)[0]
    return value.strip()


def _fake_script_symbols(source: str) -> dict[str, Any]:
    class_name = ""
    extends = ""
    functions: list[dict[str, Any]] = []
    variables: list[dict[str, Any]] = []
    constants: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("class_name "):
            class_name = _fake_symbol_name(stripped, "class_name ")
        if stripped.startswith("extends "):
            extends = _fake_symbol_name(stripped, "extends ")
        elif stripped.startswith("func "):
            name = _fake_symbol_name(stripped, "func ")
            if name:
                functions.append({"name": name, "line": line_number, "signature": stripped})
        elif stripped.startswith("static func "):
            name = _fake_symbol_name(stripped, "static func ")
            if name:
                functions.append({"name": name, "line": line_number, "signature": stripped, "static": True})
        elif stripped.startswith("@export var "):
            name = _fake_symbol_name(stripped, "@export var ")
            if name:
                variables.append({"name": name, "line": line_number, "signature": stripped, "exported": True})
        elif stripped.startswith("var "):
            name = _fake_symbol_name(stripped, "var ")
            if name:
                variables.append({"name": name, "line": line_number, "signature": stripped})
        elif stripped.startswith("const "):
            name = _fake_symbol_name(stripped, "const ")
            if name:
                constants.append({"name": name, "line": line_number, "signature": stripped})
        elif stripped.startswith("signal "):
            name = _fake_symbol_name(stripped, "signal ")
            if name:
                signals.append({"name": name, "line": line_number, "signature": stripped})
    return {
        "class_name": class_name,
        "extends": extends,
        "functions": functions,
        "variables": variables,
        "constants": constants,
        "signals": signals,
    }


def _fake_script_file_description(path: str, files: dict[str, str | bytes], *, include_source: bool = False) -> dict[str, Any]:
    source = _fake_script_source(path, files)
    symbols = _fake_script_symbols(source)
    exists = path in files or path == "res://scripts/generated/agent_tool.gd"
    result: dict[str, Any] = {
        "path": path,
        "name": path.rsplit("/", 1)[-1],
        "global_path": f"/fake/project/{path.removeprefix('res://')}",
        "exists": exists,
        "file_exists": exists,
        "resource_exists": exists,
        "load_error": False,
        "extension": "gd",
        "language": "GDScript",
        "class": "GDScript",
        "class_name": symbols["class_name"],
        "extends": symbols["extends"],
        "methods": list(symbols["functions"]),
        "method_count": len(symbols["functions"]),
        "functions": list(symbols["functions"]),
        "function_count": len(symbols["functions"]),
        "properties": list(symbols["variables"]),
        "property_count": len(symbols["variables"]),
        "variables": list(symbols["variables"]),
        "variable_count": len(symbols["variables"]),
        "constants": list(symbols["constants"]),
        "constant_count": len(symbols["constants"]),
        "signals": list(symbols["signals"]),
        "signal_count": len(symbols["signals"]),
        "symbols": symbols,
        "ok": exists,
        "open_error": 0,
    }
    if include_source:
        result["source"] = source
    return result


def _fake_script_class_is_a(extends: str, base_class: str, class_extends: dict[str, str], path_classes: dict[str, str]) -> bool:
    if not base_class or base_class == "Object":
        return True
    current = path_classes.get(extends, extends)
    seen: set[str] = set()
    while current:
        if current == base_class:
            return True
        if current in seen:
            return False
        seen.add(current)
        if base_class == "Node" and _fake_node_class_is_a(current, "Node"):
            return True
        if base_class == "Resource" and current in {"Resource", "Gradient", "GradientTexture1D"}:
            return True
        current = path_classes.get(class_extends.get(current, ""), class_extends.get(current, ""))
    return False


def _fake_script_classes(
    files: dict[str, str | bytes],
    *,
    path: str = "res://",
    class_name: str = "",
    name_contains: str = "",
    extends: str = "",
    base_class: str = "",
    include_anonymous: bool = False,
    max_results: int = 200,
) -> dict[str, Any]:
    script_paths = sorted(
        file_path
        for file_path in (set(files) | {"res://scripts/generated/agent_tool.gd"})
        if file_path.endswith(".gd") and (file_path == path or file_path.startswith(path.rstrip("/") + "/") or path == "res://")
    )
    parsed: list[tuple[str, str, dict[str, Any]]] = []
    class_extends: dict[str, str] = {}
    path_classes: dict[str, str] = {}
    for script_path in script_paths:
        source = _fake_script_source(script_path, files)
        symbols = _fake_script_symbols(source)
        parsed.append((script_path, source, symbols))
        script_class = str(symbols.get("class_name", ""))
        if script_class:
            class_extends[script_class] = str(symbols.get("extends", ""))
            path_classes[script_path] = script_class
    classes: list[dict[str, Any]] = []
    total_matches = 0
    for script_path, _source, symbols in parsed:
        script_class = str(symbols.get("class_name", ""))
        script_extends = str(symbols.get("extends", ""))
        display_name = script_class or Path(script_path).stem
        parent = path_classes.get(script_extends, script_extends)
        if not script_class and not include_anonymous:
            continue
        if class_name and script_class != class_name:
            continue
        if name_contains and name_contains not in display_name and name_contains not in script_path:
            continue
        if extends and script_extends != extends and parent != extends:
            continue
        if base_class and script_class != base_class and not _fake_script_class_is_a(script_extends, base_class, class_extends, path_classes):
            continue
        total_matches += 1
        if len(classes) >= max_results:
            continue
        functions = list(symbols.get("functions", []))
        signals = list(symbols.get("signals", []))
        variables = list(symbols.get("variables", []))
        constants = list(symbols.get("constants", []))
        classes.append(
            {
                "path": script_path,
                "global_path": f"/fake/project/{script_path.removeprefix('res://')}",
                "class": script_class,
                "class_name": script_class,
                "name": display_name,
                "language": "GDScript",
                "extends": script_extends,
                "parent": parent,
                "is_node": _fake_script_class_is_a(script_extends, "Node", class_extends, path_classes),
                "is_resource": _fake_script_class_is_a(script_extends, "Resource", class_extends, path_classes),
                "is_custom": bool(script_class),
                "functions": functions,
                "function_count": len(functions),
                "signals": signals,
                "signal_count": len(signals),
                "variables": variables,
                "variable_count": len(variables),
                "constants": constants,
                "constant_count": len(constants),
            }
        )
    return {
        "path": path,
        "global_path": f"/fake/project/{path.removeprefix('res://')}",
        "recursive": True,
        "include_hidden": False,
        "include_anonymous": include_anonymous,
        "class_name": class_name,
        "name_contains": name_contains,
        "extends": extends,
        "base_class": base_class,
        "classes": classes,
        "count": len(classes),
        "total_matches": total_matches,
        "truncated": total_matches > len(classes),
        "max_results": max_results,
    }


def _fake_text_search_path(path: str) -> bool:
    extension = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    return extension in {
        "",
        "cfg",
        "csv",
        "gd",
        "gdshader",
        "import",
        "json",
        "material",
        "md",
        "shader",
        "theme",
        "tres",
        "tscn",
        "txt",
        "translation",
    }


def _fake_text_line_at_offset(text: str, offset: int) -> dict[str, Any]:
    safe_offset = min(max(offset, 0), len(text))
    line = text.count("\n", 0, safe_offset) + 1
    line_start = text.rfind("\n", 0, safe_offset) + 1
    line_end = text.find("\n", line_start)
    if line_end < 0:
        line_end = len(text)
    return {
        "line": line,
        "column": safe_offset - line_start,
        "text": text[line_start:line_end].removesuffix("\r"),
    }


def _fake_replace_text(
    source: str,
    old_text: str,
    new_text: str,
    *,
    case_sensitive: bool,
    max_preview: int,
) -> dict[str, Any]:
    haystack = source if case_sensitive else source.lower()
    needle = old_text if case_sensitive else old_text.lower()
    positions: list[int] = []
    cursor = 0
    while True:
        position = haystack.find(needle, cursor)
        if position < 0:
            break
        positions.append(position)
        cursor = position + max(1, len(needle))
    output_parts: list[str] = []
    source_cursor = 0
    for position in positions:
        output_parts.append(source[source_cursor:position])
        output_parts.append(new_text)
        source_cursor = position + len(old_text)
    output_parts.append(source[source_cursor:])
    output = "".join(output_parts)
    edits: list[dict[str, Any]] = []
    delta = 0
    for position in positions[:max(0, max_preview)]:
        before = _fake_text_line_at_offset(source, position)
        after = _fake_text_line_at_offset(output, position + delta)
        edits.append({"line": before["line"], "column": before["column"], "before": before, "after": after})
        delta += len(new_text) - len(old_text)
    return {"text": output, "match_count": len(positions), "replacements": len(positions), "edits": edits}


_FAKE_PROTOCOL_METHODS = [
    "protocol.describe",
    "engine.info",
    "runtime.clock",
    "runtime.evaluate",
    "tree.snapshot",
    "node.find",
    "node.describe",
    "node.state",
    "node.bounds",
    "node.click",
    "node.dialog",
    "node.accept_dialog",
    "node.dismiss_dialog",
    "node.focus",
    "node.fill",
    "node.get_property",
    "node.get_properties",
    "node.set_property",
    "node.set_properties",
    "node.set_all_properties",
    "node.attach_script",
    "node.detach_script",
    "node.set_value",
    "node.set_checked",
    "node.select_option",
    "node.select_tab",
    "node.menu_items",
    "node.select_menu_item",
    "node.select_item",
    "node.select_tree_item",
    "node.call",
    "node.call_all",
    "node.evaluate",
    "node.evaluate_all",
    "animation.describe",
    "animation.play",
    "animation.stop",
    "animation.pause",
    "animation.seek",
    "animation.advance",
    "physics2d.point",
    "physics2d.ray",
    "physics3d.point",
    "physics3d.ray",
    "camera3d.ray",
    "camera3d.pick",
    "node.class.describe",
    "node.classes",
    "node.create",
    "node.create_tree",
    "node.instantiate_scene",
    "node.save_as_scene",
    "node.metadata",
    "node.set_metadata",
    "node.remove_metadata",
    "node.groups",
    "node.add_group",
    "node.remove_group",
    "node.reparent",
    "node.move",
    "node.duplicate",
    "node.delete",
    "scene.current",
    "scene.files",
    "scene.file.describe",
    "scene.change",
    "scene.reload",
    "scene.new",
    "scene.open",
    "scene.save",
    "editor.play",
    "editor.stop",
    "editor.status",
    "editor.ui.status",
    "editor.ui.switch_main_screen",
    "editor.ui.hide_bottom_panel",
    "editor.history",
    "editor.undo",
    "editor.redo",
    "editor.selection.get",
    "editor.selection.set",
    "editor.inspect",
    "editor.inspector.describe",
    "editor.inspector.get_property",
    "editor.inspector.set_property",
    "editor.inspector.set_properties",
    "editor.script.open",
    "editor.script.status",
    "editor.script.describe",
    "script.file.describe",
    "script.classes",
    "editor.filesystem.scan",
    "editor.filesystem.describe",
    "editor.filesystem.find",
    "editor.filesystem.select",
    "editor.filesystem.open",
    "input.actions",
    "input.action.describe",
    "input.action.configure",
    "input.action.erase",
    "input.action",
    "input.key",
    "input.text",
    "input.mouse",
    "input.touch",
    "input.joypad",
    "viewport.info",
    "viewport.set_size",
    "viewport.screenshot",
    "fs.exists",
    "fs.info",
    "fs.read_text",
    "fs.write_text",
    "fs.replace_text",
    "fs.replace_text_many",
    "fs.read_bytes",
    "fs.write_bytes",
    "fs.mkdir",
    "fs.list",
    "fs.find",
    "fs.grep",
    "fs.copy",
    "fs.move",
    "fs.delete",
    "resource.files",
    "resource.file.describe",
    "resource.save",
    "resource.inspect",
    "resource.classes",
    "resource.class.describe",
    "resource.set_properties",
    "resource.duplicate",
    "resource.dependencies",
    "resource.references",
    "resource.move",
    "resource.imports",
    "resource.import_metadata",
    "resource.reimport",
    "project.get_setting",
    "project.set_setting",
    "project.doctor",
    "project.summary",
    "project.export_presets",
    "project.set_export_preset",
    "project.main_scene",
    "project.set_main_scene",
    "project.autoloads",
    "project.add_autoload",
    "project.remove_autoload",
    "trace.start",
    "trace.stop",
    "trace.events",
    "trace.clear",
    "signal.watch",
    "signal.unwatch",
    "signal.events",
    "signal.clear",
    "signal.connections",
    "signal.connect",
    "signal.disconnect",
]


def _fake_protocol_description(server: Any, params: dict[str, Any]) -> dict[str, Any]:
    def domain(method: str) -> str:
        return method.split(".", 1)[0]

    def helper(method: str) -> str:
        aliases = {
            "runtime.clock": "clock",
            "runtime.evaluate": "evaluate",
            "tree.snapshot": "snapshot",
            "scene.current": "current_scene",
            "scene.change": "change_scene",
            "scene.reload": "reload_scene",
            "scene.new": "editor_new_scene",
            "scene.open": "editor_open_scene",
            "scene.save": "editor_save_scene",
            "viewport.set_size": "set_viewport_size",
            "viewport.screenshot": "screenshot",
            "input.key": "key_down/key_up",
        }
        return aliases.get(method, method.replace(".", "_"))

    domains: list[dict[str, Any]] = []
    for name in sorted({domain(method) for method in _FAKE_PROTOCOL_METHODS}):
        methods = sorted(method for method in _FAKE_PROTOCOL_METHODS if domain(method) == name)
        domains.append({"name": name, "count": len(methods), "methods": methods})
    result: dict[str, Any] = {
        "server": "godot-playwright",
        "version": "0.1.0",
        "transport": {"http": True, "jsonrpc": "2.0", "health": "/health", "rpc": "/rpc"},
        "editor": True,
        "godot": {"major": 4, "minor": 6, "patch": 2, "status": "stable", "string": "4.6.2.stable.fake"},
        "project_path": "/tmp/fake-godot-project/",
        "server_port": server.server_port,
        "uptime_ms": 16,
        "method_count": len(_FAKE_PROTOCOL_METHODS),
        "domain_count": len(domains),
        "last_error": "",
    }
    if params.get("include_methods", True):
        result["methods"] = [
            {"method": method, "domain": domain(method), "python_helper": helper(method)}
            for method in _FAKE_PROTOCOL_METHODS
        ]
    if params.get("include_domains", True):
        result["domains"] = domains
    if params.get("include_features", True):
        result["features"] = [
            "runtime_rpc",
            "editor_rpc",
            "trace_codegen",
            "project_doctor",
            "resource_safe_move",
            "protocol_discovery",
        ]
    return result


def _fake_editor_filesystem_entry(
    path: str,
    files: dict[str, str | bytes],
    directories: set[str],
    deleted: set[str],
    selected_path: str = "",
) -> dict[str, Any]:
    normalized_directory = "res://" if path == "res://" else path.rstrip("/")
    static_file = path == "res://scripts/generated/agent_tool.gd"
    is_deleted = path in deleted or normalized_directory in deleted
    is_file = not is_deleted and (path in files or static_file)
    is_directory = not is_deleted and normalized_directory in directories
    value = files.get(path, "extends Node\n" if static_file else b"")
    bytes_count = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
    return {
        "path": path,
        "name": "res://" if path == "res://" else path.rsplit("/", 1)[-1],
        "exists": is_file or is_directory,
        "kind": "file" if is_file else ("directory" if is_directory else "missing"),
        "type": "file" if is_file else ("directory" if is_directory else "missing"),
        "is_file": is_file,
        "is_directory": is_directory,
        "is_resource": is_file,
        "resource_type": _fake_resource_type_for_path(path) if is_file else "",
        "extension": path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else "",
        "bytes": bytes_count if is_file else -1,
        "selected": (is_file or is_directory) and path == selected_path,
    }


def _fake_file_summary(
    path: str,
    files: dict[str, str | bytes],
    *,
    exists: bool | None = None,
    bytes_count: int | None = None,
    modified_time: int = 100,
) -> dict[str, Any]:
    file_exists = path in files if exists is None else exists
    value = files.get(path, b"")
    if bytes_count is None:
        bytes_count = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
    return {
        "path": path,
        "name": path.rsplit("/", 1)[-1],
        "global_path": f"/fake/project/{path.removeprefix('res://')}",
        "exists": file_exists,
        "bytes": bytes_count if file_exists else -1,
        "modified_time": modified_time if file_exists else 0,
    }


def _fake_script_editor_status(server: Any) -> dict[str, Any]:
    open_paths = list(getattr(server, "open_scripts", []))
    current_path = str(getattr(server, "current_script", "") or "")
    return {
        "available": True,
        "has_script_editor": True,
        "can_list_open_scripts": True,
        "can_get_current_script": True,
        "open_scripts": [{"path": path, "class": "GDScript"} for path in open_paths],
        "open_paths": open_paths,
        "open_count": len(open_paths),
        "current_script": {"path": current_path, "class": "GDScript"} if current_path else {},
        "current_path": current_path,
    }


def _fake_resource_readback_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_fake_resource_readback_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    type_name = str(value.get("$type", ""))
    if type_name in {"ResourceRef", "ExtResource"}:
        result: dict[str, Any] = {"$type": "Resource", "path": str(value.get("path") or value.get("resource_path") or "")}
        if value.get("class"):
            result["class"] = value["class"]
        return result
    if type_name in {"Resource", "SubResource"}:
        path = str(value.get("path") or value.get("resource_path") or "")
        result = {"$type": "Resource", "class": str(value.get("class") or value.get("class_name") or "Resource")}
        if path:
            result["path"] = path
        if "resource_name" in value:
            result["resource_name"] = value["resource_name"]
        return result
    return {str(key): _fake_resource_readback_value(item) for key, item in value.items()}


def _fake_resource_readback_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _fake_resource_readback_value(value) for key, value in properties.items()}


def _fake_resource_dependency_paths(value: Any) -> list[str]:
    if isinstance(value, list):
        paths: list[str] = []
        for item in value:
            paths.extend(_fake_resource_dependency_paths(item))
        return paths
    if not isinstance(value, dict):
        return []
    type_name = str(value.get("$type", ""))
    if type_name in {"ResourceRef", "ExtResource"}:
        path = str(value.get("path") or value.get("resource_path") or "")
        return [path] if path else []
    paths = []
    for item in value.values():
        paths.extend(_fake_resource_dependency_paths(item))
    return paths


def _fake_dependency_state(path: str, dependencies: list[str], existing_paths: set[str]) -> dict[str, Any]:
    dependency_entries = [_fake_dependency_summary(f"{dependency}::Resource", existing_paths) for dependency in dependencies]
    missing = [entry for entry in dependency_entries if not entry["exists"]]
    return {
        "path": path,
        "global_path": f"/fake/project/{path.removeprefix('res://')}",
        "exists": path in existing_paths,
        "file_exists": path in existing_paths,
        "resource_exists": path in existing_paths,
        "ok": path in existing_paths and not missing,
        "dependencies": dependency_entries,
        "dependency_count": len(dependency_entries),
        "missing": missing,
        "missing_count": len(missing),
    }


def _fake_resource_class_describe(
    class_name: str,
    *,
    include_values: bool = True,
    storage_only: bool = False,
    properties: list[str] | None = None,
    name_contains: str = "",
) -> dict[str, Any]:
    known = {"Resource", "Gradient", "GradientTexture1D"}
    exists = class_name in known or class_name == "Node"
    is_resource = class_name in known
    can_instantiate = exists
    schema_properties = [
        {
            "name": "resource_name",
            "type": 4,
            "type_name": "String",
            "hint": 0,
            "hint_string": "",
            "usage": 6,
            "storage": True,
            "editor_visible": True,
            "exists": True,
            "value": "",
        }
    ]
    if class_name == "GradientTexture1D":
        schema_properties.append(
            {
                "name": "gradient",
                "type": 24,
                "type_name": "Object",
                "hint": 17,
                "hint_string": "Gradient",
                "usage": 6,
                "storage": True,
                "editor_visible": True,
                "exists": True,
                "value": None,
            }
        )
    property_filter = set(properties or [])
    filtered = []
    for entry in schema_properties if is_resource else []:
        if property_filter and entry["name"] not in property_filter:
            continue
        if name_contains and name_contains not in entry["name"]:
            continue
        if storage_only and not entry["storage"]:
            continue
        item = dict(entry)
        if not include_values:
            item.pop("value", None)
        filtered.append(item)
    return {
        "requested_class": class_name,
        "class": class_name,
        "exists": exists,
        "can_instantiate": can_instantiate,
        "is_resource": is_resource,
        "properties": filtered,
        "property_count": len(filtered),
        "storage_property_count": sum(1 for entry in filtered if entry["storage"]),
        "editor_property_count": sum(1 for entry in filtered if entry["editor_visible"]),
        "values": {entry["name"]: entry.get("value") for entry in filtered if "value" in entry} if include_values else {},
    }


def _fake_resource_classes(
    *,
    base_class: str = "Resource",
    name_contains: str = "",
    include_abstract: bool = False,
    include_property_counts: bool = True,
    max_results: int = 200,
) -> dict[str, Any]:
    entries = [
        {"class": "Resource", "parent": "RefCounted", "can_instantiate": True, "is_resource": True},
        {"class": "Gradient", "parent": "Resource", "can_instantiate": True, "is_resource": True},
        {"class": "GradientTexture1D", "parent": "Texture2D", "can_instantiate": True, "is_resource": True},
        {"class": "Texture2D", "parent": "Texture", "can_instantiate": False, "is_resource": True},
    ]
    filtered = []
    for entry in entries:
        if base_class and base_class != "Resource" and entry["class"] != base_class and entry["parent"] != base_class:
            continue
        if name_contains and name_contains not in entry["class"]:
            continue
        if not include_abstract and not entry["can_instantiate"]:
            continue
        item = {
            "class": entry["class"],
            "name": entry["class"],
            "parent": entry["parent"],
            "is_resource": entry["is_resource"],
            "can_instantiate": entry["can_instantiate"],
            "enabled": True,
            "api_type": 0,
        }
        if include_property_counts:
            schema = _fake_resource_class_describe(entry["class"], include_values=False)
            item["property_count"] = schema["property_count"]
            item["storage_property_count"] = schema["storage_property_count"]
            item["editor_property_count"] = schema["editor_property_count"]
        filtered.append(item)
    total = len(filtered)
    return {
        "base_class": base_class,
        "name_contains": name_contains,
        "include_abstract": include_abstract,
        "include_disabled": False,
        "include_property_counts": include_property_counts,
        "classes": filtered[:max_results],
        "count": min(total, max_results),
        "total_matches": total,
        "truncated": total > max_results,
        "max_results": max_results,
    }


_FAKE_NODE_CLASS_PARENTS = {
    "Node": "Object",
    "CanvasItem": "Node",
    "Control": "CanvasItem",
    "Label": "Control",
    "BaseButton": "Control",
    "Button": "BaseButton",
    "Container": "Control",
    "VBoxContainer": "Container",
    "PanelContainer": "Container",
    "Node2D": "CanvasItem",
    "Sprite2D": "Node2D",
    "Node3D": "Node",
    "Camera3D": "Node3D",
}


def _fake_node_class_is_a(class_name: str, base_class: str) -> bool:
    if not base_class or base_class == "Object":
        return True
    cursor = class_name
    while cursor:
        if cursor == base_class:
            return True
        cursor = _FAKE_NODE_CLASS_PARENTS.get(cursor, "")
    return False


def _fake_node_class_describe(
    class_name: str,
    *,
    include_values: bool = True,
    storage_only: bool = False,
    properties: list[str] | None = None,
    name_contains: str = "",
    include_methods: bool = True,
    include_signals: bool = True,
    methods: list[str] | None = None,
    signals: list[str] | None = None,
    method_contains: str = "",
    signal_contains: str = "",
    max_methods: int = 200,
    max_signals: int = 200,
) -> dict[str, Any]:
    known = set(_FAKE_NODE_CLASS_PARENTS)
    exists = class_name in known
    is_node = exists and _fake_node_class_is_a(class_name, "Node")
    can_instantiate = exists and class_name != "CanvasItem"
    schema_properties = [
        {
            "name": "name",
            "type": 4,
            "type_name": "String",
            "hint": 0,
            "hint_string": "",
            "usage": 6,
            "storage": True,
            "editor_visible": True,
            "exists": True,
            "value": class_name,
        },
        {
            "name": "visible",
            "type": 1,
            "type_name": "bool",
            "hint": 0,
            "hint_string": "",
            "usage": 6,
            "storage": True,
            "editor_visible": True,
            "exists": True,
            "value": True,
        },
    ]
    if class_name in {"Label", "Button"}:
        schema_properties.append(
            {
                "name": "text",
                "type": 4,
                "type_name": "String",
                "hint": 0,
                "hint_string": "",
                "usage": 6,
                "storage": True,
                "editor_visible": True,
                "exists": True,
                "value": "",
            }
        )
    property_filter = set(properties or [])
    filtered = []
    for entry in schema_properties if is_node and can_instantiate else []:
        if property_filter and entry["name"] not in property_filter:
            continue
        if name_contains and name_contains not in entry["name"]:
            continue
        if storage_only and not entry["storage"]:
            continue
        item = dict(entry)
        if not include_values:
            item.pop("value", None)
        filtered.append(item)
    schema_methods = [{"name": "get_meta", "args": [], "arg_count": 0, "return": {"type": 0, "type_name": "Nil"}}]
    if class_name in {"Label", "Button"}:
        schema_methods.append(
            {
                "name": "set_text",
                "args": [{"name": "text", "type": 4, "type_name": "String"}],
                "arg_count": 1,
                "return": {"type": 0, "type_name": "Nil"},
            }
        )
    method_filter = set(methods or [])
    filtered_methods = []
    if include_methods and is_node and can_instantiate:
        for entry in schema_methods:
            if method_filter and entry["name"] not in method_filter:
                continue
            if method_contains and method_contains not in entry["name"]:
                continue
            filtered_methods.append(dict(entry))
    schema_signals = [{"name": "renamed", "args": [], "arg_count": 0}]
    if class_name == "Button":
        schema_signals.append({"name": "pressed", "args": [], "arg_count": 0})
    signal_filter = set(signals or [])
    filtered_signals = []
    if include_signals and is_node and can_instantiate:
        for entry in schema_signals:
            if signal_filter and entry["name"] not in signal_filter:
                continue
            if signal_contains and signal_contains not in entry["name"]:
                continue
            filtered_signals.append(dict(entry))
    return {
        "requested_class": class_name,
        "class": class_name,
        "exists": exists,
        "can_instantiate": can_instantiate,
        "is_node": is_node,
        "properties": filtered,
        "property_count": len(filtered),
        "storage_property_count": sum(1 for entry in filtered if entry["storage"]),
        "editor_property_count": sum(1 for entry in filtered if entry["editor_visible"]),
        "methods": filtered_methods[:max_methods],
        "method_count": len(filtered_methods),
        "methods_truncated": len(filtered_methods) > max_methods,
        "max_methods": max_methods,
        "signals": filtered_signals[:max_signals],
        "signal_count": len(filtered_signals),
        "signals_truncated": len(filtered_signals) > max_signals,
        "max_signals": max_signals,
        "values": {entry["name"]: entry.get("value") for entry in filtered if "value" in entry} if include_values else {},
    }


def _fake_node_classes(
    *,
    base_class: str = "Node",
    name_contains: str = "",
    include_abstract: bool = False,
    include_property_counts: bool = True,
    max_results: int = 200,
) -> dict[str, Any]:
    entries = [
        {"class": "Node", "can_instantiate": True},
        {"class": "CanvasItem", "can_instantiate": False},
        {"class": "Control", "can_instantiate": True},
        {"class": "Label", "can_instantiate": True},
        {"class": "Button", "can_instantiate": True},
        {"class": "VBoxContainer", "can_instantiate": True},
        {"class": "PanelContainer", "can_instantiate": True},
        {"class": "Node2D", "can_instantiate": True},
        {"class": "Sprite2D", "can_instantiate": True},
        {"class": "Camera3D", "can_instantiate": True},
    ]
    filtered = []
    for entry in entries:
        class_name = entry["class"]
        if not _fake_node_class_is_a(class_name, base_class):
            continue
        if name_contains and name_contains not in class_name:
            continue
        if not include_abstract and not entry["can_instantiate"]:
            continue
        item = {
            "class": class_name,
            "name": class_name,
            "parent": _FAKE_NODE_CLASS_PARENTS.get(class_name, ""),
            "is_node": True,
            "can_instantiate": entry["can_instantiate"],
            "enabled": True,
            "api_type": 0,
        }
        if include_property_counts:
            schema = _fake_node_class_describe(class_name, include_values=False)
            item["property_count"] = schema["property_count"]
            item["storage_property_count"] = schema["storage_property_count"]
            item["editor_property_count"] = schema["editor_property_count"]
        filtered.append(item)
    total = len(filtered)
    return {
        "base_class": base_class,
        "name_contains": name_contains,
        "include_abstract": include_abstract,
        "include_disabled": False,
        "include_property_counts": include_property_counts,
        "classes": filtered[:max_results],
        "count": min(total, max_results),
        "total_matches": total,
        "truncated": total > max_results,
        "max_results": max_results,
    }


def _fake_editor_ui_status(server: Any) -> dict[str, Any]:
    main_screen_name = str(getattr(server, "main_screen_name", "2D") or "2D")
    base_control = {
        "name": "EditorNode",
        "class": "Panel",
        "path": "/root/EditorNode",
        "parent": "/root",
        "index": 0,
        "groups": [],
        "owner": "",
        "child_count": 3,
        "visible": True,
        "visible_in_tree": True,
    }
    main_screen = {
        "name": main_screen_name,
        "api_name": main_screen_name,
        "class": "VBoxContainer",
        "path": f"/root/EditorNode/MainScreen/{main_screen_name}",
        "parent": "/root/EditorNode/MainScreen",
        "index": 0,
        "groups": [],
        "owner": "",
        "child_count": 0,
        "visible": True,
        "visible_in_tree": True,
    }
    return {
        "available": True,
        "has_base_control": True,
        "base_control": base_control,
        "can_get_main_screen": True,
        "can_set_main_screen": True,
        "can_list_main_screens": False,
        "main_screen": main_screen,
        "main_screen_name": main_screen_name,
        "main_screen_api_name": main_screen_name,
        "main_screen_path": main_screen["path"],
        "main_screen_container": {
            "name": "MainScreen",
            "class": "VBoxContainer",
            "path": "/root/EditorNode/MainScreen",
            "parent": "/root/EditorNode",
            "index": 0,
            "groups": [],
            "owner": "",
            "child_count": 1,
            "visible": True,
            "visible_in_tree": True,
        },
        "main_screens": [main_screen],
        "main_screens_source": "get_editor_main_screen_children",
        "main_screens_heuristic": True,
        "bottom_panel": {
            "available": True,
            "can_make_visible": True,
            "can_hide": True,
            "can_list_items": False,
            "can_read_visibility": False,
            "visible": None,
            "items": [],
            "hints": [
                {
                    "name": "BottomPanel",
                    "class": "PanelContainer",
                    "path": "/root/EditorNode/BottomPanel",
                    "parent": "/root/EditorNode",
                    "index": 2,
                    "groups": [],
                    "owner": "",
                    "child_count": 1,
                    "visible": True,
                    "visible_in_tree": True,
                }
            ],
            "hint_count": 1,
        },
        "capabilities": {
            "get_base_control": True,
            "get_editor_main_screen": True,
            "set_main_screen_editor": True,
            "bottom_panel_make_visible": True,
            "bottom_panel_hide": True,
            "bottom_panel_list_items": False,
            "bottom_panel_read_visibility": False,
        },
    }


def _fake_editor_filesystem_entries(
    path: str,
    files: dict[str, str | bytes],
    directories: set[str],
    deleted: set[str],
    selected_path: str = "",
    *,
    recursive: bool,
    include_dirs: bool,
) -> list[dict[str, Any]]:
    root = "res://" if path == "res://" else path.rstrip("/")
    prefix = root if root == "res://" else f"{root}/"
    file_paths = set(files) | {"res://scripts/generated/agent_tool.gd"}
    directory_paths = set(directories) if include_dirs else set()
    entries: list[dict[str, Any]] = []
    for entry_path in sorted(file_paths | directory_paths):
        if entry_path == root:
            if not include_dirs:
                continue
        elif not entry_path.startswith(prefix):
            continue
        elif not recursive and "/" in entry_path.removeprefix(prefix).strip("/"):
            continue
        entry = _fake_editor_filesystem_entry(entry_path, files, directories, deleted, selected_path)
        if entry["exists"] and (include_dirs or entry["is_file"]):
            entries.append(entry)
    return entries


def _fake_scene_tag_attributes(line: str) -> dict[str, str]:
    body = line.strip().removeprefix("[").removesuffix("]")
    parts = body.split(" ", 1)
    if len(parts) < 2:
        return {}
    text = parts[1]
    attrs: dict[str, str] = {}
    cursor = 0
    while cursor < len(text):
        while cursor < len(text) and text[cursor] == " ":
            cursor += 1
        equals = text.find("=", cursor)
        if equals < 0:
            break
        key = text[cursor:equals].strip()
        cursor = equals + 1
        if cursor >= len(text):
            attrs[key] = ""
            break
        if text[cursor] in {"'", '"'}:
            quote = text[cursor]
            end = text.find(quote, cursor + 1)
            if end < 0:
                attrs[key] = text[cursor + 1 :]
                break
            attrs[key] = text[cursor + 1 : end]
            cursor = end + 1
        else:
            end = text.find(" ", cursor)
            if end < 0:
                attrs[key] = text[cursor:]
                break
            attrs[key] = text[cursor:end]
            cursor = end + 1
    return attrs


def _fake_scene_property_value(raw: str) -> Any:
    value = raw.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith("ExtResource("):
        return {"$type": "ExtResource", "id": value.split('"')[1] if '"' in value else "", "raw": value}
    if value.startswith("SubResource("):
        return {"$type": "SubResource", "id": value.split('"')[1] if '"' in value else "", "raw": value}
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return {"raw": value}


def _fake_scene_node_path(root_name: str, parent: str, name: str) -> str:
    if not parent:
        return name
    if parent == ".":
        return f"{root_name}/{name}" if root_name else name
    return f"{root_name}/{parent.strip('/')}/{name}" if root_name else f"{parent.strip('/')}/{name}"


def _fake_scene_parent_path(root_name: str, parent: str) -> str:
    if not parent:
        return ""
    if parent == ".":
        return root_name
    return f"{root_name}/{parent.strip('/')}" if root_name else parent


def _fake_text_scene_summary(
    source: str,
    *,
    include_nodes: bool = False,
    include_properties: bool = False,
    include_resources: bool = False,
    include_connections: bool = False,
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    ext_resources: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []
    root: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if stripped.startswith("["):
            current = None
            if stripped.startswith("[ext_resource "):
                attrs = _fake_scene_tag_attributes(stripped)
                ext_resources.append(
                    {
                        "id": attrs.get("id", ""),
                        "type": attrs.get("type", ""),
                        "path": attrs.get("path", ""),
                        "uid": attrs.get("uid", ""),
                        "line": line_number,
                        "global_path": f"/fake/project/{attrs.get('path', '').removeprefix('res://')}"
                        if attrs.get("path", "").startswith("res://")
                        else "",
                        "exists": True,
                    }
                )
            elif stripped.startswith("[node "):
                attrs = _fake_scene_tag_attributes(stripped)
                node = {
                    "name": attrs.get("name", ""),
                    "class": attrs.get("type", ""),
                    "type": attrs.get("type", ""),
                    "parent": attrs.get("parent", ""),
                    "parent_path": "",
                    "path": "",
                    "scene_path": "",
                    "instance": _fake_scene_property_value(attrs["instance"]) if "instance" in attrs else None,
                    "instance_path": "",
                    "groups": [],
                    "line": line_number,
                    "index": len(nodes),
                    "properties": {},
                    "property_count": 0,
                }
                if not root and not attrs.get("parent"):
                    root = node
                nodes.append(node)
                current = node
            elif stripped.startswith("[connection "):
                attrs = _fake_scene_tag_attributes(stripped)
                connections.append(
                    {
                        "signal": attrs.get("signal", ""),
                        "from": attrs.get("from", ""),
                        "to": attrs.get("to", ""),
                        "method": attrs.get("method", ""),
                        "flags": _fake_scene_property_value(attrs["flags"]) if "flags" in attrs else None,
                        "line": line_number,
                    }
                )
            continue
        if include_properties and current is not None and "=" in stripped:
            key, value = stripped.split("=", 1)
            current["properties"][key.strip()] = _fake_scene_property_value(value)
            current["property_count"] = len(current["properties"])
    if not root and nodes:
        root = nodes[0]
    ext_by_id = {resource["id"]: resource for resource in ext_resources if resource.get("id")}
    root_name = str(root.get("name", ""))
    for node in nodes:
        scene_path = _fake_scene_node_path(root_name, str(node.get("parent", "")), str(node.get("name", "")))
        parent_path = _fake_scene_parent_path(root_name, str(node.get("parent", "")))
        node["scene_path"] = scene_path
        node["path"] = f"/{scene_path}" if scene_path else ""
        node["parent_path"] = f"/{parent_path}" if parent_path else ""
        instance = node.get("instance")
        if isinstance(instance, dict) and instance.get("$type") == "ExtResource":
            node["instance_path"] = ext_by_id.get(instance.get("id"), {}).get("path", "")
        script = node.get("properties", {}).get("script")
        if isinstance(script, dict) and script.get("$type") == "ExtResource":
            node["script"] = ext_by_id.get(script.get("id"), {}).get("path", "")
        if not include_properties:
            node.pop("properties", None)
    summary: dict[str, Any] = {
        "root_name": root.get("name", ""),
        "root_class": root.get("class", ""),
        "node_count": len(nodes),
    }
    if include_nodes:
        summary["nodes"] = nodes
    if include_resources:
        summary["ext_resources"] = ext_resources
        summary["ext_resource_count"] = len(ext_resources)
        summary["sub_resources"] = []
        summary["sub_resource_count"] = 0
    if include_connections:
        summary["connections"] = connections
        summary["connection_count"] = len(connections)
    return summary


def _fake_scene_summary(
    path: str,
    files: dict[str, str | bytes],
    resource_dependencies: dict[str, list[str]],
    *,
    include_dependencies: bool = True,
    include_nodes: bool = False,
    include_properties: bool = False,
    include_resources: bool = False,
    include_connections: bool = False,
) -> dict[str, Any]:
    value = files.get(path, "")
    source = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
    extension = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    summary: dict[str, Any] = {
        "path": path,
        "name": path.rsplit("/", 1)[-1],
        "global_path": f"/fake/project/{path.removeprefix('res://')}",
        "exists": path in files,
        "file_exists": path in files,
        "resource_exists": path in files,
        "resource_type": "PackedScene" if extension in {"tscn", "scn"} else _fake_resource_type_for_path(path),
        "extension": extension,
        "is_scene": extension in {"tscn", "scn"},
        "root_name": "",
        "root_class": "",
        "node_count": 0,
        "ok": path in files,
    }
    if extension == "tscn":
        summary.update(
            _fake_text_scene_summary(
                source,
                include_nodes=include_nodes,
                include_properties=include_properties,
                include_resources=include_resources,
                include_connections=include_connections,
            )
        )
    if include_dependencies:
        existing_paths = set(files)
        dependencies = [_fake_dependency_summary(str(raw), existing_paths) for raw in resource_dependencies.get(path, [])]
        missing = [dependency for dependency in dependencies if dependency["checked"] and not dependency["exists"]]
        summary.update(
            {
                "dependencies": dependencies,
                "dependency_count": len(dependencies),
                "missing": missing,
                "missing_count": len(missing),
                "ok": bool(summary["ok"]) and not missing,
            }
        )
    return summary


def _fake_text_resource_summary(
    source: str,
    existing_paths: set[str],
    *,
    include_properties: bool = True,
    include_resources: bool = True,
) -> dict[str, Any]:
    header: dict[str, Any] = {}
    root: dict[str, Any] = {}
    ext_resources: list[dict[str, Any]] = []
    sub_resources: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_section = ""
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if stripped.startswith("["):
            current = None
            current_section = ""
            if stripped.startswith("[gd_resource"):
                attrs = _fake_scene_tag_attributes(stripped)
                header = {
                    "type": attrs.get("type", ""),
                    "class": attrs.get("type", ""),
                    "script_class": attrs.get("script_class", ""),
                    "load_steps": int(attrs.get("load_steps", 0) or 0),
                    "format": int(attrs.get("format", 0) or 0),
                    "uid": attrs.get("uid", ""),
                    "line": line_number,
                }
            elif stripped.startswith("[ext_resource "):
                attrs = _fake_scene_tag_attributes(stripped)
                resource_path = attrs.get("path", "")
                ext_resources.append(
                    {
                        "id": attrs.get("id", ""),
                        "type": attrs.get("type", ""),
                        "path": resource_path,
                        "uid": attrs.get("uid", ""),
                        "line": line_number,
                        "global_path": f"/fake/project/{resource_path.removeprefix('res://')}"
                        if resource_path.startswith("res://")
                        else "",
                        "exists": resource_path in existing_paths,
                    }
                )
            elif stripped.startswith("[sub_resource "):
                attrs = _fake_scene_tag_attributes(stripped)
                current = {
                    "id": attrs.get("id", ""),
                    "type": attrs.get("type", ""),
                    "line": line_number,
                    "properties": {},
                    "property_count": 0,
                }
                sub_resources.append(current)
                current_section = "sub_resource"
            elif stripped.startswith("[resource"):
                resource_type = header.get("type", "")
                current = {
                    "type": resource_type,
                    "class": resource_type,
                    "script_class": header.get("script_class", ""),
                    "line": line_number,
                    "properties": {},
                    "property_count": 0,
                    "script": "",
                }
                root = current
                current_section = "resource"
            continue
        if include_properties and current is not None and current_section in {"resource", "sub_resource"} and "=" in stripped:
            key, value = stripped.split("=", 1)
            current["properties"][key.strip()] = _fake_scene_property_value(value)
            current["property_count"] = len(current["properties"])
    if not root:
        resource_type = header.get("type", "")
        root = {
            "type": resource_type,
            "class": resource_type,
            "script_class": header.get("script_class", ""),
            "line": 0,
            "properties": {},
            "property_count": 0,
            "script": "",
        }
    ext_by_id = {resource["id"]: resource for resource in ext_resources if resource.get("id")}
    script = root.get("properties", {}).get("script")
    if isinstance(script, dict) and script.get("$type") == "ExtResource":
        root["script"] = ext_by_id.get(script.get("id"), {}).get("path", "")
    if not include_properties:
        root.pop("properties", None)
        for sub_resource in sub_resources:
            sub_resource.pop("properties", None)
    summary: dict[str, Any] = {
        "header": header,
        "root": root,
        "root_class": root.get("type", ""),
        "root_type": root.get("type", ""),
        "script_class": header.get("script_class", ""),
        "resource_uid": header.get("uid", ""),
        "load_steps": header.get("load_steps", 0),
        "format": header.get("format", 0),
        "property_count": root.get("property_count", 0),
    }
    if include_properties:
        summary["properties"] = root.get("properties", {})
    if include_resources:
        summary["ext_resources"] = ext_resources
        summary["ext_resource_count"] = len(ext_resources)
        summary["sub_resources"] = sub_resources
        summary["sub_resource_count"] = len(sub_resources)
    return summary


def _fake_resource_file_description(
    path: str,
    files: dict[str, str | bytes],
    resources: dict[str, dict[str, Any]],
    resource_dependencies: dict[str, list[str]],
    *,
    include_dependencies: bool = True,
    include_properties: bool = True,
    include_resources: bool = True,
    include_source: bool = False,
) -> dict[str, Any]:
    summary = _fake_resource_summary(
        path,
        files,
        resources,
        resource_dependencies,
        include_dependencies=include_dependencies,
        include_properties=False,
    )
    extension = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    summary.update(
        {
            "file_format": "text" if extension == "tres" else "binary",
            "is_resource_file": extension in {"tres", "res"},
            "root_class": summary.get("class", ""),
            "root_type": summary.get("class", ""),
            "script_class": "",
            "resource_uid": "",
            "load_steps": 0,
            "format": 0,
            "header": {},
            "root": {},
            "property_count": 0,
        }
    )
    if include_properties:
        summary["properties"] = {}
    if include_resources:
        summary.update({"ext_resources": [], "ext_resource_count": 0, "sub_resources": [], "sub_resource_count": 0})
    value = files.get(path, "")
    source = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
    if extension == "tres":
        summary.update(
            _fake_text_resource_summary(
                source,
                set(files) | set(resources),
                include_properties=include_properties,
                include_resources=include_resources,
            )
        )
    if include_properties and not summary.get("properties"):
        properties = resources.get(path, {}).get("properties", {})
        if isinstance(properties, dict):
            summary["properties"] = properties
            summary["property_count"] = len(properties)
            if isinstance(summary.get("root"), dict):
                summary["root"].setdefault("properties", properties)
                summary["root"]["property_count"] = len(properties)
    if include_source and extension == "tres":
        summary["source"] = source
    return summary


def _fake_scene_files(
    files: dict[str, str | bytes],
    resource_dependencies: dict[str, list[str]],
    *,
    path: str = "res://",
    name: str = "",
    name_contains: str = "",
    root_name: str = "",
    root_class: str = "",
    extensions: list[str] | None = None,
    include_dependencies: bool = True,
    include_nodes: bool = False,
    max_results: int = 200,
) -> dict[str, Any]:
    extension_filter = {item.removeprefix(".").lower() for item in (extensions or ["tscn", "scn"])}
    scene_paths = sorted(
        file_path
        for file_path in files
        if (file_path == path or file_path.startswith(path.rstrip("/") + "/") or path == "res://")
        and file_path.rsplit(".", 1)[-1].lower() in extension_filter
    )
    scenes: list[dict[str, Any]] = []
    total_matches = 0
    for scene_path in scene_paths:
        scene = _fake_scene_summary(
            scene_path,
            files,
            resource_dependencies,
            include_dependencies=include_dependencies,
            include_nodes=include_nodes,
        )
        if name and scene["name"] != name:
            continue
        if name_contains and name_contains not in scene["name"] and name_contains not in scene_path:
            continue
        if root_name and scene["root_name"] != root_name:
            continue
        if root_class and scene["root_class"] != root_class:
            continue
        total_matches += 1
        if len(scenes) < max_results:
            scenes.append(scene)
    return {
        "path": path,
        "global_path": f"/fake/project/{path.removeprefix('res://')}",
        "recursive": True,
        "include_hidden": False,
        "include_dependencies": include_dependencies,
        "include_nodes": include_nodes,
        "extensions": sorted(extension_filter),
        "name": name,
        "name_contains": name_contains,
        "root_name": root_name,
        "root_class": root_class,
        "scenes": scenes,
        "count": len(scenes),
        "total_matches": total_matches,
        "truncated": total_matches > len(scenes),
        "max_results": max_results,
        "scanned": len(scene_paths),
    }


def _fake_resource_summary(
    path: str,
    files: dict[str, str | bytes],
    resources: dict[str, dict[str, Any]],
    resource_dependencies: dict[str, list[str]],
    *,
    include_dependencies: bool = True,
    include_properties: bool = False,
) -> dict[str, Any]:
    resource = resources.get(path, {})
    path_exists = path in files or path in resources
    extension = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    class_name = str(resource.get("class", "")) or (_fake_resource_type_for_path(path) if path_exists else "")
    properties = resource.get("properties", {})
    summary: dict[str, Any] = {
        "path": path,
        "name": path.rsplit("/", 1)[-1],
        "global_path": f"/fake/project/{path.removeprefix('res://')}",
        "exists": path_exists,
        "file_exists": path in files,
        "resource_exists": path_exists,
        "load_error": False,
        "extension": extension,
        "class": class_name,
        "class_name": class_name,
        "type": class_name,
        "resource_type": class_name,
        "resource_name": properties.get("resource_name", ""),
        "ok": path_exists,
    }
    if include_properties:
        summary["properties"] = properties
    if include_dependencies:
        existing_paths = set(files) | set(resources)
        dependencies = [_fake_dependency_summary(str(raw), existing_paths) for raw in resource_dependencies.get(path, [])]
        missing = [dependency for dependency in dependencies if dependency["checked"] and not dependency["exists"]]
        summary.update(
            {
                "dependencies": dependencies,
                "dependency_count": len(dependencies),
                "missing": missing,
                "missing_count": len(missing),
                "ok": path_exists and not missing,
            }
        )
    return summary


def _fake_resource_class_matches(actual_class: str, expected_class: str) -> bool:
    if not expected_class:
        return True
    if actual_class == expected_class:
        return True
    return expected_class == "Resource" and actual_class not in {"", "GDScript", "PackedScene"}


def _fake_resource_files(
    files: dict[str, str | bytes],
    resources: dict[str, dict[str, Any]],
    resource_dependencies: dict[str, list[str]],
    *,
    path: str = "res://",
    name: str = "",
    name_contains: str = "",
    resource_name: str = "",
    class_name: str = "",
    extensions: list[str] | None = None,
    include_dependencies: bool = True,
    include_properties: bool = False,
    max_results: int = 200,
) -> dict[str, Any]:
    extension_filter = {item.removeprefix(".").lower() for item in (extensions or ["tres", "res"])}
    resource_paths = sorted(
        file_path
        for file_path in (set(files) | set(resources))
        if (file_path == path or file_path.startswith(path.rstrip("/") + "/") or path == "res://")
        and file_path.rsplit(".", 1)[-1].lower() in extension_filter
    )
    listed_resources: list[dict[str, Any]] = []
    total_matches = 0
    for resource_path in resource_paths:
        resource = _fake_resource_summary(
            resource_path,
            files,
            resources,
            resource_dependencies,
            include_dependencies=include_dependencies,
            include_properties=include_properties,
        )
        if name and resource["name"] != name:
            continue
        if name_contains and name_contains not in resource["name"] and name_contains not in resource_path:
            continue
        if resource_name and resource["resource_name"] != resource_name:
            continue
        if class_name and not _fake_resource_class_matches(str(resource["class"]), class_name):
            continue
        total_matches += 1
        if len(listed_resources) < max_results:
            listed_resources.append(resource)
    return {
        "path": path,
        "global_path": f"/fake/project/{path.removeprefix('res://')}",
        "recursive": True,
        "include_hidden": False,
        "include_dependencies": include_dependencies,
        "include_properties": include_properties,
        "extensions": sorted(extension_filter),
        "name": name,
        "name_contains": name_contains,
        "class": class_name,
        "class_name": class_name,
        "resource_name": resource_name,
        "resources": listed_resources,
        "count": len(listed_resources),
        "total_matches": total_matches,
        "truncated": total_matches > len(listed_resources),
        "max_results": max_results,
        "scanned": len(resource_paths),
    }


def _fake_resource_references(
    files: dict[str, str | bytes],
    resources: dict[str, dict[str, Any]],
    resource_dependencies: dict[str, list[str]],
    *,
    target_path: str = "",
    target_uid: str = "",
    search_path: str = "res://",
    dependency_type: str = "",
    resource_type: str = "",
    exists: bool | None = None,
    extensions: list[str] | None = None,
    max_results: int = 200,
) -> dict[str, Any]:
    extension_filter = {item.removeprefix(".").lower() for item in (extensions or ["tscn", "scn", "tres", "res"])}
    existing_paths = set(files) | set(resources)
    scanned_paths = sorted(
        file_path
        for file_path in existing_paths
        if (file_path == search_path or file_path.startswith(search_path.rstrip("/") + "/") or search_path == "res://")
        and file_path.rsplit(".", 1)[-1].lower() in extension_filter
    )
    references: list[dict[str, Any]] = []
    total_matches = 0
    for file_path in scanned_paths:
        for raw_dependency in resource_dependencies.get(file_path, []):
            dependency = _fake_dependency_summary(str(raw_dependency), existing_paths)
            if target_path and dependency.get("path") != target_path:
                continue
            if target_uid and dependency.get("uid") != target_uid:
                continue
            if dependency_type and dependency.get("type") != dependency_type:
                continue
            if resource_type and dependency.get("resource_type") != resource_type:
                continue
            if exists is not None and bool(dependency.get("exists")) != exists:
                continue
            total_matches += 1
            if len(references) < max_results:
                references.append(
                    {
                        "path": file_path,
                        "name": file_path.rsplit("/", 1)[-1],
                        "global_path": f"/fake/project/{file_path.removeprefix('res://')}",
                        "extension": file_path.rsplit(".", 1)[-1].lower(),
                        "resource_type": _fake_resource_type_for_path(file_path),
                        "dependency": dependency,
                    }
                )
            break
    return {
        "path": target_path,
        "target_path": target_path,
        "uid": target_uid,
        "target_uid": target_uid,
        "search_path": search_path,
        "global_search_path": f"/fake/project/{search_path.removeprefix('res://')}",
        "recursive": True,
        "include_hidden": False,
        "extensions": sorted(extension_filter),
        "dependency_type": dependency_type,
        "resource_type": resource_type,
        "exists": exists,
        "references": references,
        "count": len(references),
        "total_matches": total_matches,
        "truncated": total_matches > len(references),
        "max_results": max_results,
        "scanned": len(scanned_paths),
    }


def _fake_metadata_defaults(selector: Any) -> dict[str, Any]:
    name = _fake_selector_name(selector)
    if name == "CounterButton":
        return {"test_id": "counter-button"}
    return {}


def _fake_dependency_path(raw: str) -> str:
    for part in raw.split("::"):
        if part.startswith("res://"):
            return part
    start = raw.find("res://")
    if start == -1:
        return ""
    tail = raw[start:]
    end = tail.find("::")
    return tail if end == -1 else tail[:end]


def _fake_dependency_summary(raw: str, existing_paths: set[str]) -> dict[str, Any]:
    path = _fake_dependency_path(raw)
    uid = next((part for part in raw.split("::") if part.startswith("uid://")), "")
    type_name = next(
        (
            part
            for part in reversed(raw.split("::"))
            if part and part != path and part != uid and not part.startswith(("res://", "uid://"))
        ),
        "",
    )
    exists = path in existing_paths if path else False
    return {
        "raw": raw,
        "path": path,
        "uid": uid,
        "type": type_name,
        "global_path": f"/fake/project/{path.removeprefix('res://')}" if path else "",
        "exists": exists,
        "file_exists": exists,
        "resource_exists": exists,
        "checked": bool(path),
        "resource_type": type_name,
    }


class FakeGodotHandler(BaseHTTPRequestHandler):
    server_version = "FakeGodot/1"

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        self._json({"ok": True, "server": "godot-playwright"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        method = payload["method"]
        params = payload.get("params", {})
        self.server.calls.append((method, params))  # type: ignore[attr-defined]
        result: Any
        if method == "protocol.describe":
            result = _fake_protocol_description(self.server, params)
        elif method == "tree.snapshot":
            root_spec = params.get("root", "edited")
            selector = root_spec.get("selector", "#Main") if isinstance(root_spec, dict) else root_spec
            include_properties = bool(params.get("include_properties", False))

            def snapshot_node(name: str, class_name: str, path: str, text: str | None = None, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
                node = {
                    "name": name,
                    "class": class_name,
                    "path": path,
                    "parent": path.rsplit("/", 1)[0],
                    "index": 0,
                    "groups": [],
                    "owner": "/root/Main",
                    "child_count": len(children or []),
                    "children": children or [],
                }
                if include_properties:
                    properties: dict[str, Any] = {"visible": True}
                    if text is not None:
                        properties["text"] = text
                    node["properties"] = properties
                return node

            title = snapshot_node("Title", "Label", "/root/Main/Title", "Godot Playwright")
            counter = snapshot_node("CounterButton", "Button", "/root/Main/CounterButton", "Clicked 1")
            if selector == "#CounterButton" or selector == {"path": "/root/Main/CounterButton"}:
                result = counter
            else:
                result = snapshot_node("Main", "Control", "/root/Main", None, [title, counter])
        elif method == "node.find":
            selector = params["selector"]
            path = _fake_selector_path(selector)
            if _selector_is_missing(selector) or path in self.server.deleted_nodes:  # type: ignore[attr-defined]
                result = {"nodes": []}
            elif isinstance(selector, str) and selector in {".button", "role=button"}:
                result = {
                    "nodes": [
                        {"name": "CounterButton", "path": "/root/Main/CounterButton"},
                        {"name": "NextSceneButton", "path": "/root/Main/NextSceneButton"},
                    ]
                }
            else:
                result = {"nodes": [_fake_node_summary(selector, self.server)]}
        elif method == "node.bounds":
            selector = params["selector"]
            selector_name = selector if isinstance(selector, str) else selector.get("name", "")
            if selector_name in {"#PointMarker", "PointMarker"}:
                result = {"point": {"x": 24.0, "y": 36.0}}
            else:
                x = 200.0 if selector_name in {"#DropTarget", "DropTarget"} else 10.0
                result = {"rect": {"x": x, "y": 20.0, "width": 100.0, "height": 50.0}}
        elif method == "node.state":
            selector = params["selector"]
            selector_text = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)
            is_input = "NameInput" in selector_text or "textbox" in selector_text
            is_option = "ThemeSelect" in selector_text or "combobox" in selector_text
            is_range = "VolumeSlider" in selector_text or "slider" in selector_text
            is_tab = "ModeTabs" in selector_text or "tablist" in selector_text
            is_dialog = "ConfirmDialog" in selector_text or "dialog" in selector_text
            is_item_list = "InventoryList" in selector_text or selector_text == "role=list" or '"role": "list"' in selector_text
            is_tree = "QuestTree" in selector_text
            disabled = selector_text in self.server.disabled_selectors  # type: ignore[attr-defined]
            visible = self.server.dialog_visible if is_dialog else selector_text not in self.server.hidden_selectors  # type: ignore[attr-defined]
            node_name = (
                "NameInput"
                if is_input
                else "ThemeSelect"
                if is_option
                else "VolumeSlider"
                if is_range
                else "ModeTabs"
                if is_tab
                else "ConfirmDialog"
                if is_dialog
                else "InventoryList"
                if is_item_list
                else "QuestTree"
                if is_tree
                else "CounterButton"
            )
            node_path = f"/root/Main/{node_name}"
            text_value = (
                self.server.input_text  # type: ignore[attr-defined]
                if is_input
                else self.server.selected_options.get(selector_text, "Arcade")  # type: ignore[attr-defined]
                if is_option
                else None
                if is_tab or is_item_list
                else "Clicked 1"
            )
            input_value = (
                self.server.input_text  # type: ignore[attr-defined]
                if is_input
                else self.server.selected_options.get(selector_text, "Arcade")  # type: ignore[attr-defined]
                if is_option
                else self.server.range_values.get(selector_text, 25.0)  # type: ignore[attr-defined]
                if is_range
                else self.server.selected_tabs.get(selector_text, "General")  # type: ignore[attr-defined]
                if is_tab
                else self.server.selected_items.get(selector_text, "Potion")  # type: ignore[attr-defined]
                if is_item_list
                else self.server.selected_tree_items.get(selector_text, "Root")  # type: ignore[attr-defined]
                if is_tree
                else None
            )
            result = {
                "node": {
                    "name": node_name,
                    "path": node_path,
                },
                "visible": visible,
                "visible_in_tree": visible,
                "enabled": not disabled,
                "disabled": disabled,
                "editable": is_input and not disabled,
                "focused": selector_text == self.server.focused_selector,  # type: ignore[attr-defined]
                "focusable": True,
                "has_bounds": True,
                "receives_input": True,
                "actionable": not disabled,
                "text": text_value,
                "value": input_value,
                "checked": selector_text in self.server.checked_selectors,  # type: ignore[attr-defined]
            }
        elif method == "node.describe":
            selector = params.get("selector", "#CounterButton")
            result = _fake_node_summary(selector, self.server)
            result.update(
                {
                    "properties": {"text": "Clicked 1", "visible": True},
                    "methods": ["get_meta", "set_meta", "emit_signal", "grab_focus", "press"],
                    "signals": ["pressed", "button_down", "button_up", "toggled"],
                }
            )
        elif method == "node.get_property":
            selector = params.get("selector", "#CounterButton")
            selector_text = _selector_key(selector)
            values = {"text": _fake_text_for_selector(selector), "visible": True}
            values.update(self.server.node_properties.get(selector_text, {}))  # type: ignore[attr-defined]
            result = {"value": values.get(params["property"])}
        elif method == "node.get_properties":
            selector = params.get("selector", "#CounterButton")
            selector_text = _selector_key(selector)
            values = {"text": _fake_text_for_selector(selector), "visible": True}
            values.update(self.server.node_properties.get(selector_text, {}))  # type: ignore[attr-defined]
            properties = params.get("properties")
            if isinstance(properties, str):
                names = [properties]
            elif properties:
                names = list(properties)
            else:
                names = list(values)
            result = {
                "node": {
                    "name": _fake_selector_name(selector),
                    "path": _fake_selector_path(selector),
                    "class": "Button",
                },
                "values": {str(name): values.get(str(name)) for name in names},
                "count": len(names),
            }
        elif method == "node.metadata":
            selector = params.get("selector", "#CounterButton")
            selector_text = _selector_key(selector)
            metadata = _fake_metadata_defaults(selector)
            metadata.update(self.server.node_metadata.get(selector_text, {}))  # type: ignore[attr-defined]
            names_param = params.get("names", params.get("name"))
            if isinstance(names_param, str):
                names = [names_param]
            elif names_param:
                names = list(names_param)
            else:
                names = list(metadata)
            selected = {str(name): metadata[str(name)] for name in names if str(name) in metadata}
            result = {
                "node": {
                    "name": _fake_selector_name(selector),
                    "path": _fake_selector_path(selector),
                    "class": "Button",
                },
                "metadata": selected,
                "values": selected,
                "count": len(selected),
            }
        elif method == "node.set_metadata":
            selector = params.get("selector", "#CounterButton")
            selector_text = _selector_key(selector)
            metadata = self.server.node_metadata.setdefault(selector_text, {})  # type: ignore[attr-defined]
            defaults = _fake_metadata_defaults(selector)
            values = dict(params.get("values", params.get("metadata", {})))
            if not values:
                values = {str(params["name"]): params.get("value")}
            previous = {
                key: {
                    "exists": key in metadata or key in defaults,
                    "value": metadata.get(key, defaults.get(key)),
                }
                for key in values
            }
            metadata.update(values)
            if params.get("undo", True):
                self.server.undo_stack.append(  # type: ignore[attr-defined]
                    {
                        "type": "set_metadata",
                        "selector": selector_text,
                        "previous": previous,
                        "values": values,
                    }
                )
                self.server.redo_stack = []  # type: ignore[attr-defined]
            result = {
                "node": {
                    "name": _fake_selector_name(selector),
                    "path": _fake_selector_path(selector),
                    "class": "Button",
                },
                "metadata": values,
                "values": values,
                "count": len(values),
                "undo": params.get("undo", True),
            }
        elif method == "node.remove_metadata":
            selector = params.get("selector", "#CounterButton")
            selector_text = _selector_key(selector)
            metadata = self.server.node_metadata.setdefault(selector_text, {})  # type: ignore[attr-defined]
            defaults = _fake_metadata_defaults(selector)
            names_param = params.get("names", params.get("name"))
            names = [names_param] if isinstance(names_param, str) else list(names_param)
            previous = {
                str(name): {
                    "exists": str(name) in metadata or str(name) in defaults,
                    "value": metadata.get(str(name), defaults.get(str(name))),
                }
                for name in names
            }
            removed = []
            for name in names:
                key = str(name)
                if previous[key]["exists"]:
                    removed.append(key)
                metadata.pop(key, None)
            if params.get("undo", True):
                self.server.undo_stack.append(  # type: ignore[attr-defined]
                    {
                        "type": "remove_metadata",
                        "selector": selector_text,
                        "previous": previous,
                        "names": [str(name) for name in names],
                    }
                )
                self.server.redo_stack = []  # type: ignore[attr-defined]
            result = {
                "node": {
                    "name": _fake_selector_name(selector),
                    "path": _fake_selector_path(selector),
                    "class": "Button",
                },
                "removed": removed,
                "metadata": metadata,
                "count": len(removed),
                "undo": params.get("undo", True),
            }
        elif method == "node.set_property":
            selector = params.get("selector", "#CounterButton")
            selector_text = _selector_key(selector)
            properties = self.server.node_properties.setdefault(selector_text, {})  # type: ignore[attr-defined]
            defaults = {"text": "Clicked 1", "visible": True}
            previous = properties.get(params["property"], defaults.get(params["property"]))
            properties[params["property"]] = params.get("value")
            if params.get("undo", True):
                self.server.undo_stack.append(  # type: ignore[attr-defined]
                    {
                        "type": "set_property",
                        "selector": selector_text,
                        "property": params["property"],
                        "previous": previous,
                        "value": params.get("value"),
                    }
                )
                self.server.redo_stack = []  # type: ignore[attr-defined]
            result = {
                "name": _fake_selector_name(selector),
                "path": _fake_selector_path(selector),
                "class": "Button",
            }
        elif method == "node.set_properties":
            selector = params.get("selector", "#CounterButton")
            selector_text = _selector_key(selector)
            properties = self.server.node_properties.setdefault(selector_text, {})  # type: ignore[attr-defined]
            defaults = {"text": "Clicked 1", "visible": True}
            values = dict(params["values"])
            previous = {key: properties.get(key, defaults.get(key)) for key in values}
            properties.update(values)
            if params.get("undo", True):
                self.server.undo_stack.append(  # type: ignore[attr-defined]
                    {
                        "type": "set_properties",
                        "selector": selector_text,
                        "previous": previous,
                        "values": values,
                    }
                )
                self.server.redo_stack = []  # type: ignore[attr-defined]
            result = {
                "node": {
                    "name": _fake_selector_name(selector),
                    "path": _fake_selector_path(selector),
                    "class": "Button",
                },
                "values": values,
                "count": len(values),
                "undo": params.get("undo", True),
            }
        elif method == "node.set_all_properties":
            selector = params.get("selector", "#CounterButton")
            selector_text = _selector_key(selector)
            values = dict(params["values"])
            if selector_text in {".button", "role=button"}:
                paths = ["/root/Main/CounterButton", "/root/Main/NextSceneButton"]
            else:
                paths = [_fake_selector_path(selector)]
            nodes = []
            previous_entries = []
            defaults = {"text": "Clicked 1", "visible": True}
            for path in paths:
                name = path.rsplit("/", 1)[-1]
                keys = [_selector_key({"path": path}), f"#{name}"]
                previous = {}
                for key in keys:
                    properties = self.server.node_properties.setdefault(key, {})  # type: ignore[attr-defined]
                    previous.update({property_name: properties.get(property_name, defaults.get(property_name)) for property_name in values})
                    properties.update(values)
                previous_entries.append({"keys": keys, "previous": previous, "values": values})
                nodes.append({"name": name, "path": path, "class": "Button", "values": dict(values)})
            if params.get("undo", True):
                self.server.undo_stack.append(  # type: ignore[attr-defined]
                    {
                        "type": "set_all_properties",
                        "entries": previous_entries,
                    }
                )
                self.server.redo_stack = []  # type: ignore[attr-defined]
            result = {
                "nodes": nodes,
                "count": len(nodes),
                "properties": list(values),
                "property_count": len(values),
                "undo": params.get("undo", True),
            }
        elif method == "node.click":
            selector_text = json.dumps(params["selector"], sort_keys=True) if isinstance(params["selector"], dict) else str(params["selector"])
            if "ShowConfirmButton" in selector_text:
                self.server.dialog_visible = True  # type: ignore[attr-defined]
            for watch_id in self.server.signal_watches:  # type: ignore[attr-defined]
                self.server.signal_events.append(  # type: ignore[attr-defined]
                    {
                        "watch_id": watch_id,
                        "signal": "pressed",
                        "path": "/root/Main/CounterButton",
                        "args": [],
                    }
                )
            result = {"strategy": "pressed_signal"}
        elif method == "node.dialog":
            result = self.server.dialog_summary()  # type: ignore[attr-defined]
        elif method == "node.accept_dialog":
            self.server.dialog_visible = False  # type: ignore[attr-defined]
            result = self.server.dialog_summary()  # type: ignore[attr-defined]
        elif method == "node.dismiss_dialog":
            self.server.dialog_visible = False  # type: ignore[attr-defined]
            result = self.server.dialog_summary()  # type: ignore[attr-defined]
        elif method == "node.set_checked":
            selector = params["selector"]
            selector_text = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)
            checked = bool(params["checked"])
            previous = selector_text in self.server.checked_selectors  # type: ignore[attr-defined]
            if checked:
                self.server.checked_selectors.add(selector_text)  # type: ignore[attr-defined]
            else:
                self.server.checked_selectors.discard(selector_text)  # type: ignore[attr-defined]
            result = {"checked": checked, "previous": previous, "changed": previous != checked}
        elif method == "node.set_value":
            selector = params["selector"]
            selector_text = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)
            value = float(params["value"])
            previous = self.server.range_values.get(selector_text, 25.0)  # type: ignore[attr-defined]
            self.server.range_values[selector_text] = value  # type: ignore[attr-defined]
            result = {"value": value, "previous": previous, "changed": previous != value}
        elif method == "node.select_option":
            selector = params["selector"]
            selector_text = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)
            option = params["option"]
            if isinstance(option, dict):
                selected = option.get("text") or option.get("value") or option.get("label") or "Simulation"
            elif isinstance(option, int):
                selected = ["Arcade", "Story", "Simulation"][option]
            else:
                selected = str(option)
            previous = self.server.selected_options.get(selector_text, "Arcade")  # type: ignore[attr-defined]
            self.server.selected_options[selector_text] = selected  # type: ignore[attr-defined]
            result = {
                "selected": {"index": 1, "id": 20, "text": selected},
                "previous": {"index": 0, "id": 10, "text": previous},
                "changed": previous != selected,
            }
        elif method == "node.select_tab":
            selector = params["selector"]
            selector_text = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)
            tab = params["tab"]
            tabs = ["General", "Advanced", "Telemetry"]
            if isinstance(tab, dict):
                if "index" in tab:
                    selected = tabs[int(tab["index"])]
                else:
                    selected = tab.get("title") or tab.get("text") or tab.get("value") or "Advanced"
            elif isinstance(tab, int):
                selected = tabs[tab]
            else:
                selected = str(tab)
            previous = self.server.selected_tabs.get(selector_text, "General")  # type: ignore[attr-defined]
            self.server.selected_tabs[selector_text] = selected  # type: ignore[attr-defined]
            result = {
                "selected": {"index": tabs.index(selected), "text": selected, "title": selected},
                "previous": {"index": tabs.index(previous), "text": previous, "title": previous},
                "changed": previous != selected,
            }
        elif method == "node.menu_items":
            result = {
                "items": list(self.server.menu_items),  # type: ignore[attr-defined]
                "count": len(self.server.menu_items),  # type: ignore[attr-defined]
                "focused": None,
            }
        elif method == "node.select_menu_item":
            selector = params["selector"]
            selector_text = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)
            item = params["item"]
            menu_items = list(self.server.menu_items)  # type: ignore[attr-defined]

            def selected_menu_item(item_spec: Any) -> dict[str, Any]:
                if isinstance(item_spec, dict):
                    if "index" in item_spec:
                        return menu_items[int(item_spec["index"])]
                    if "id" in item_spec:
                        return next(entry for entry in menu_items if entry["id"] == item_spec["id"])
                    if item_spec.get("metadata") == {"action": "save"} or item_spec.get("meta") == {"action": "save"}:
                        return next(entry for entry in menu_items if entry["text"] == "Save")
                    text = item_spec.get("text") or item_spec.get("value") or item_spec.get("label") or "Save"
                    return next(entry for entry in menu_items if entry["text"] == text)
                if isinstance(item_spec, int):
                    return menu_items[item_spec]
                return next(entry for entry in menu_items if entry["text"] == str(item_spec))

            selected = dict(selected_menu_item(item))
            previous_text = self.server.selected_menu_items.get(selector_text, "")  # type: ignore[attr-defined]
            previous = next((entry for entry in menu_items if entry["text"] == previous_text), None)
            if "checked" in params:
                selected["checked"] = bool(params["checked"])
            self.server.selected_menu_items[selector_text] = selected["text"]  # type: ignore[attr-defined]
            result = {
                "selected": selected,
                "previous": previous,
                "changed": previous_text != selected["text"],
                "value": selected["text"],
            }
        elif method == "node.select_item":
            selector = params["selector"]
            selector_text = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)
            item = params["item"]
            items = ["Potion", "Elixir", "Key"]

            def selected_text(item_spec: Any) -> str:
                if isinstance(item_spec, dict):
                    if "index" in item_spec:
                        return items[int(item_spec["index"])]
                    if item_spec.get("metadata") == {"kind": "key"} or item_spec.get("meta") == {"kind": "key"}:
                        return "Key"
                    return item_spec.get("text") or item_spec.get("value") or item_spec.get("label") or "Elixir"
                if isinstance(item_spec, int):
                    return items[item_spec]
                return str(item_spec)

            selected = [selected_text(entry) for entry in item] if isinstance(item, list) else selected_text(item)
            previous = self.server.selected_items.get(selector_text, "Potion")  # type: ignore[attr-defined]
            self.server.selected_items[selector_text] = selected  # type: ignore[attr-defined]
            selected_texts = selected if isinstance(selected, list) else [selected]
            previous_texts = previous if isinstance(previous, list) else [previous]
            result = {
                "selected": {
                    "indices": [items.index(text) for text in selected_texts],
                    "texts": selected_texts,
                    "items": [{"index": items.index(text), "text": text} for text in selected_texts],
                    "value": selected,
                },
                "previous": {
                    "indices": [items.index(text) for text in previous_texts],
                    "texts": previous_texts,
                    "value": previous,
                },
                "changed": previous != selected,
                "value": selected,
            }
        elif method == "node.select_tree_item":
            selector = params["selector"]
            selector_text = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)
            item = params["item"]
            tree_items = ["Root", "Forest", "Cave", "Boss"]

            def selected_tree_text(item_spec: Any) -> str:
                if isinstance(item_spec, dict):
                    if "index" in item_spec:
                        return tree_items[int(item_spec["index"])]
                    if item_spec.get("metadata") == {"quest": "boss"} or item_spec.get("meta") == {"quest": "boss"}:
                        return "Boss"
                    if item_spec.get("path") == ["Cave", "Boss"]:
                        return "Boss"
                    return item_spec.get("text") or item_spec.get("value") or item_spec.get("label") or "Forest"
                if isinstance(item_spec, int):
                    return tree_items[item_spec]
                return str(item_spec)

            selected = [selected_tree_text(entry) for entry in item] if isinstance(item, list) else selected_tree_text(item)
            previous = self.server.selected_tree_items.get(selector_text, "Root")  # type: ignore[attr-defined]
            self.server.selected_tree_items[selector_text] = selected  # type: ignore[attr-defined]
            selected_texts = selected if isinstance(selected, list) else [selected]
            previous_texts = previous if isinstance(previous, list) else [previous]
            result = {
                "selected": {
                    "texts": selected_texts,
                    "items": [
                        {"column": 0, "text": text, "path": [text], "index_path": [tree_items.index(text)]}
                        for text in selected_texts
                    ],
                    "value": selected,
                },
                "previous": {
                    "texts": previous_texts,
                    "value": previous,
                },
                "changed": previous != selected,
                "value": selected,
            }
        elif method == "node.evaluate":
            expression = params["expression"]
            variables = params.get("variables", {})
            if expression == 'node.get("text")':
                result = {"value": "Clicked 1"}
            elif expression == 'node.get("text") == expected':
                result = {"value": "Clicked 1" == variables.get("expected")}
            else:
                result = {
                    "value": {
                        "expression": expression,
                        "variables": variables,
                    }
                }
        elif method == "runtime.evaluate":
            expression = params["expression"]
            variables = params.get("variables", {})
            if expression == "ready":
                result = {"value": True}
            elif expression == "counter >= target":
                self.server.runtime_counter += 1  # type: ignore[attr-defined]
                result = {"value": self.server.runtime_counter >= variables.get("target", 1)}  # type: ignore[attr-defined]
            else:
                result = {
                    "value": {
                        "expression": expression,
                        "variables": variables,
                        "root": params.get("root", "edited"),
                    }
                }
        elif method == "node.evaluate_all":
            result = {
                "value": {
                    "expression": params["expression"],
                    "variables": params.get("variables", {}),
                    "limit": params.get("limit", 0),
                }
            }
        elif method == "node.call_all":
            selector = params.get("selector", "#CounterButton")
            if _selector_key(selector) in {".button", "role=button"}:
                nodes = [
                    {"name": "CounterButton", "path": "/root/Main/CounterButton", "class": "Button"},
                    {"name": "NextSceneButton", "path": "/root/Main/NextSceneButton", "class": "Button"},
                ]
            else:
                nodes = [
                    {
                        "name": _fake_selector_name(selector),
                        "path": _fake_selector_path(selector),
                        "class": "Button",
                    }
                ]
            method_name = params["method"]
            args = params.get("args", [])
            results = []
            error_count = 0
            for index, node in enumerate(nodes[: int(params.get("limit", 0)) or None]):
                if method_name == "missing_method":
                    results.append(
                        {
                            "ok": False,
                            "index": index,
                            "node": node,
                            "value": None,
                            "message": f"Node {node['path']} has no method {method_name}",
                        }
                    )
                    error_count += 1
                elif method_name == "get_meta":
                    metadata = _fake_metadata_defaults(f"#{node['name']}")
                    metadata.update(self.server.node_metadata.get(f"#{node['name']}", {}))  # type: ignore[attr-defined]
                    results.append({"ok": True, "index": index, "node": node, "value": metadata.get(args[0], args[1] if len(args) > 1 else None)})
                else:
                    results.append({"ok": True, "index": index, "node": node, "value": {"method": method_name, "args": args}})
            result = {
                "results": results,
                "values": [entry.get("value") for entry in results],
                "count": len(results),
                "error_count": error_count,
            }
        elif method == "node.create":
            name = params.get("name") or params.get("class", "Node")
            parent_path = _fake_selector_path(params.get("parent", "edited"))
            path = f"{parent_path}/{name}"
            self.server.created_nodes.add(path)  # type: ignore[attr-defined]
            self.server.deleted_nodes.discard(path)  # type: ignore[attr-defined]
            summary = {
                "name": name,
                "class": params.get("class", "Node"),
                "path": path,
                "parent": parent_path,
                "index": 0,
                "groups": [],
                "owner": "/root/Main",
                "child_count": 0,
            }
            self.server.node_summaries[path] = summary  # type: ignore[attr-defined]
            if params.get("undo", True):
                self.server.undo_stack.append({"type": "create_node", "path": path, "summary": dict(summary)})  # type: ignore[attr-defined]
                self.server.redo_stack = []  # type: ignore[attr-defined]
            result = dict(summary)
        elif method == "node.create_tree":
            parent_path = _fake_selector_path(params.get("parent", "edited"))
            summaries: list[dict[str, Any]] = []

            def create_from_spec(current_parent: str, spec: dict[str, Any]) -> None:
                class_name = str(spec.get("class", spec.get("type", "Node")))
                name = str(spec.get("name") or class_name)
                path = f"{current_parent}/{name}"
                children = list(spec.get("children", []))
                groups = [str(group) for group in spec.get("groups", [])]
                summary: dict[str, Any] = {
                    "name": name,
                    "class": class_name,
                    "path": path,
                    "parent": current_parent,
                    "index": int(spec.get("index", 0)),
                    "groups": sorted(groups),
                    "owner": "/root/Main",
                    "child_count": len(children),
                }
                properties = dict(spec.get("properties", {}))
                metadata = dict(spec.get("metadata", spec.get("meta", {})))
                if properties:
                    summary["properties"] = dict(properties)
                if metadata:
                    summary["metadata"] = dict(metadata)
                script_path = str(spec.get("script", spec.get("script_path", "")))
                if script_path:
                    script = {
                        "path": script_path,
                        "global_path": f"/fake/project/{script_path.removeprefix('res://')}",
                        "class": "GDScript",
                        "resource_name": "",
                    }
                    summary["script"] = script
                    properties["script"] = script
                self.server.node_summaries[path] = dict(summary)  # type: ignore[attr-defined]
                self.server.created_nodes.add(path)  # type: ignore[attr-defined]
                self.server.deleted_nodes.discard(path)  # type: ignore[attr-defined]
                selector_keys = {_selector_key({"path": path}), path, f"#{name}"}
                for selector_key in selector_keys:
                    if properties:
                        self.server.node_properties.setdefault(selector_key, {}).update(properties)  # type: ignore[attr-defined]
                    if metadata:
                        self.server.node_metadata.setdefault(selector_key, {}).update(metadata)  # type: ignore[attr-defined]
                if groups:
                    self.server.node_groups.setdefault(path, set()).update(groups)  # type: ignore[attr-defined]
                summaries.append(summary)
                for child in children:
                    create_from_spec(path, dict(child))

            for raw_spec in params.get("nodes", []):
                create_from_spec(parent_path, dict(raw_spec))
            result = {
                "parent": _fake_node_summary({"path": parent_path}, self.server),
                "nodes": summaries,
                "count": len(summaries),
            }
        elif method == "node.instantiate_scene":
            name = params.get("name") or Pathish(params["path"]).stem_title
            parent_path = _fake_selector_path(params.get("parent", "edited"))
            path = f"{parent_path}/{name}"
            summary = {
                "name": name,
                "class": "Node",
                "path": path,
                "parent": parent_path,
                "index": params.get("index", 0),
                "groups": [],
                "owner": "/root/Main",
                "child_count": 0,
            }
            self.server.node_summaries[path] = summary  # type: ignore[attr-defined]
            self.server.deleted_nodes.discard(path)  # type: ignore[attr-defined]
            result = {
                **summary,
                "source_scene": params["path"],
                "packed_scene": {
                    "path": params["path"],
                    "global_path": f"/fake/project/{params['path'].removeprefix('res://')}",
                    "class": "PackedScene",
                    "resource_name": "",
                },
            }
        elif method == "node.save_as_scene":
            source_path = _fake_selector_path(params.get("selector", params.get("node", "Node")))
            path = params["path"]
            self.server.files[path] = f'[gd_scene format=3]\n\n[node name="{source_path.rsplit("/", 1)[-1]}" type="Node"]\n'  # type: ignore[attr-defined]
            result = {
                "path": path,
                "global_path": f"/fake/project/{path.removeprefix('res://')}",
                "source": {
                    "name": source_path.rsplit("/", 1)[-1],
                    "class": "Node",
                    "path": source_path,
                    "groups": [],
                    "child_count": 0,
                },
                "packed_scene": {
                    "path": path,
                    "global_path": f"/fake/project/{path.removeprefix('res://')}",
                    "class": "PackedScene",
                    "resource_name": "",
                },
                "saved": True,
            }
        elif method == "node.groups":
            path = _fake_selector_path(params.get("selector", "Node"))
            groups = sorted(self.server.node_groups.get(path, set()))  # type: ignore[attr-defined]
            result = {
                "node": {**_fake_node_summary({"path": path}, self.server, class_name="Node"), "groups": groups},
                "groups": groups,
                "count": len(groups),
            }
        elif method == "node.add_group":
            path = _fake_selector_path(params.get("selector", "Node"))
            groups = self.server.node_groups.setdefault(path, set())  # type: ignore[attr-defined]
            previous = params["group"] in groups
            groups.add(params["group"])
            group_list = sorted(groups)
            summary = {**_fake_node_summary({"path": path}, self.server, class_name="Node"), "groups": group_list}
            result = {
                "node": summary,
                "group": params["group"],
                "added": not previous,
                "persistent": params.get("persistent", True),
                "groups": group_list,
                "count": len(group_list),
            }
        elif method == "node.remove_group":
            path = _fake_selector_path(params.get("selector", "Node"))
            groups = self.server.node_groups.setdefault(path, set())  # type: ignore[attr-defined]
            previous = params["group"] in groups
            groups.discard(params["group"])
            group_list = sorted(groups)
            summary = {**_fake_node_summary({"path": path}, self.server, class_name="Node"), "groups": group_list}
            result = {
                "node": summary,
                "group": params["group"],
                "removed": previous,
                "groups": group_list,
                "count": len(group_list),
            }
        elif method == "node.reparent":
            name = _fake_selector_name(params.get("selector", "Node"))
            parent_path = _fake_selector_path(params.get("parent", "edited"))
            old_path = _fake_selector_path(params.get("selector", "Node"))
            path = f"{parent_path}/{name}"
            summary = _fake_node_summary(params.get("selector", "Node"), self.server, class_name="Node")
            summary.update({"name": name, "path": path, "parent": parent_path, "index": params.get("index", 0)})
            self.server.node_summaries.pop(old_path, None)  # type: ignore[attr-defined]
            self.server.node_summaries[path] = summary  # type: ignore[attr-defined]
            result = {
                **summary,
                "name": name,
                "path": path,
                "old_path": old_path,
                "new_parent": parent_path,
                "index": params.get("index", 0),
            }
        elif method == "node.move":
            path = _fake_selector_path(params.get("selector", "Node"))
            summary = _fake_node_summary(params.get("selector", "Node"), self.server, class_name="Node")
            summary["index"] = params["index"]
            self.server.node_summaries[path] = summary  # type: ignore[attr-defined]
            result = {
                **summary,
                "old_index": 0,
                "index": params["index"],
            }
        elif method == "node.duplicate":
            source_name = _fake_selector_name(params.get("selector", "Node"))
            name = params.get("name") or f"{source_name}2"
            parent_path = _fake_selector_path(params.get("parent", "edited"))
            path = f"{parent_path}/{name}"
            summary = {
                "name": name,
                "class": "Node",
                "path": path,
                "parent": parent_path,
                "index": params.get("index", 0),
                "groups": [],
                "owner": "/root/Main",
                "child_count": 0,
            }
            self.server.node_summaries[path] = summary  # type: ignore[attr-defined]
            self.server.deleted_nodes.discard(path)  # type: ignore[attr-defined]
            result = {
                **summary,
                "source": {"name": source_name, "path": _fake_selector_path(params.get("selector", "Node"))},
            }
        elif method == "node.attach_script":
            selector = params.get("selector", "Node")
            selector_text = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)
            script = {
                "path": params["path"],
                "global_path": f"/fake/project/{params['path'].removeprefix('res://')}",
                "class": "GDScript",
                "resource_name": "",
            }
            properties = self.server.node_properties.setdefault(selector_text, {})  # type: ignore[attr-defined]
            properties["script"] = script
            result = {
                "name": _fake_selector_name(selector),
                "class": "Node",
                "path": _fake_selector_path(selector),
                "script": script,
            }
        elif method == "node.detach_script":
            selector = params.get("selector", "Node")
            selector_text = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)
            properties = self.server.node_properties.setdefault(selector_text, {})  # type: ignore[attr-defined]
            previous_script = properties.get(
                "script",
                {
                    "path": "res://scripts/generated/status_label.gd",
                    "global_path": "/fake/project/scripts/generated/status_label.gd",
                    "class": "GDScript",
                    "resource_name": "",
                },
            )
            properties["script"] = None
            result = {
                "name": _fake_selector_name(selector),
                "class": "Node",
                "path": _fake_selector_path(selector),
                "script": None,
                "previous_script": previous_script,
            }
        elif method == "node.delete":
            selector = params.get("selector", "")
            path = _fake_selector_path(selector)
            self.server.deleted_nodes.add(path)  # type: ignore[attr-defined]
            self.server.created_nodes.discard(path)  # type: ignore[attr-defined]
            self.server.node_summaries.pop(path, None)  # type: ignore[attr-defined]
            result = {"deleted": path}
        elif method == "signal.watch":
            watch_id = f"watch-{len(self.server.signal_watches) + 1}"  # type: ignore[attr-defined]
            self.server.signal_watches.append(watch_id)  # type: ignore[attr-defined]
            result = {"watch_id": watch_id, "path": "/root/Main/CounterButton", "signal": params["signal"]}
        elif method == "signal.events":
            events = [
                event
                for event in self.server.signal_events  # type: ignore[attr-defined]
                if not params.get("watch_id") or event["watch_id"] == params["watch_id"]
            ]
            if params.get("clear"):
                self.server.signal_events = [  # type: ignore[attr-defined]
                    event
                    for event in self.server.signal_events  # type: ignore[attr-defined]
                    if params.get("watch_id") and event["watch_id"] != params["watch_id"]
                ]
            result = {"events": events}
        elif method == "signal.clear":
            watch_id = params.get("watch_id", "")
            if watch_id:
                self.server.signal_events = [  # type: ignore[attr-defined]
                    event for event in self.server.signal_events if event["watch_id"] != watch_id  # type: ignore[attr-defined]
                ]
            else:
                self.server.signal_events = []  # type: ignore[attr-defined]
            result = {"events": len(self.server.signal_events)}  # type: ignore[attr-defined]
        elif method == "signal.unwatch":
            result = {"removed": True, "watch_id": params["watch_id"]}
        elif method == "signal.connections":
            source_path = _fake_selector_path(params.get("selector", params.get("source", "Node")))
            signal_filter = params.get("signal", "")
            connections = [
                connection
                for connection in self.server.signal_connections  # type: ignore[attr-defined]
                if connection["source_path"] == source_path
                and (not signal_filter or connection["signal"] == signal_filter)
            ]
            result = {
                "node": {"name": source_path.rsplit("/", 1)[-1], "path": source_path, "class": "Node"},
                "signal": signal_filter,
                "connections": connections,
                "count": len(connections),
            }
        elif method == "signal.connect":
            source_path = _fake_selector_path(params.get("selector", params.get("source", "Node")))
            target_path = _fake_selector_path(params.get("target", params.get("receiver", params.get("selector", "Node"))))
            signal_name = params["signal"]
            method_name = params["method"]
            existing = next(
                (
                    connection
                    for connection in self.server.signal_connections  # type: ignore[attr-defined]
                    if connection["source_path"] == source_path
                    and connection["signal"] == signal_name
                    and connection["target_path"] == target_path
                    and connection["method"] == method_name
                ),
                None,
            )
            if existing is not None and params.get("replace"):
                self.server.signal_connections.remove(existing)  # type: ignore[attr-defined]
                existing = None
            if existing is None:
                flags = int(params.get("flags", 0))
                persistent = bool(params.get("persistent", True))
                if persistent:
                    flags |= 2
                existing = {
                    "source_path": source_path,
                    "source_class": "Node",
                    "signal": signal_name,
                    "target_path": target_path,
                    "target_class": "Node",
                    "target_id": len(self.server.signal_connections) + 1,  # type: ignore[attr-defined]
                    "method": method_name,
                    "binds": params.get("binds", []),
                    "flags": flags,
                    "persistent": persistent,
                    "deferred": bool(params.get("deferred", False)),
                    "one_shot": bool(params.get("one_shot", False)),
                    "reference_counted": bool(params.get("reference_counted", False)),
                    "valid": True,
                    "callable": f"{target_path}.{method_name}",
                }
                self.server.signal_connections.append(existing)  # type: ignore[attr-defined]
                connected = True
            else:
                connected = False
            connections = [
                connection
                for connection in self.server.signal_connections  # type: ignore[attr-defined]
                if connection["source_path"] == source_path and connection["signal"] == signal_name
            ]
            result = {
                "source": {"name": source_path.rsplit("/", 1)[-1], "path": source_path, "class": "Node"},
                "target": {"name": target_path.rsplit("/", 1)[-1], "path": target_path, "class": "Node"},
                "signal": signal_name,
                "method": method_name,
                "connected": connected,
                "already_connected": not connected,
                "connection": existing,
                "connections": connections,
            }
        elif method == "signal.disconnect":
            source_path = _fake_selector_path(params.get("selector", params.get("source", "Node")))
            target_path = _fake_selector_path(params.get("target", params.get("receiver", params.get("selector", "Node"))))
            signal_name = params["signal"]
            method_name = params["method"]
            connection = next(
                (
                    item
                    for item in self.server.signal_connections  # type: ignore[attr-defined]
                    if item["source_path"] == source_path
                    and item["signal"] == signal_name
                    and item["target_path"] == target_path
                    and item["method"] == method_name
                ),
                None,
            )
            removed = connection is not None
            if connection is not None:
                self.server.signal_connections.remove(connection)  # type: ignore[attr-defined]
            connections = [
                item
                for item in self.server.signal_connections  # type: ignore[attr-defined]
                if item["source_path"] == source_path and item["signal"] == signal_name
            ]
            result = {
                "source": {"name": source_path.rsplit("/", 1)[-1], "path": source_path, "class": "Node"},
                "target": {"name": target_path.rsplit("/", 1)[-1], "path": target_path, "class": "Node"},
                "signal": signal_name,
                "method": method_name,
                "removed": removed,
                "connection": connection,
                "connections": connections,
            }
        elif method == "node.focus":
            selector = params["selector"]
            self.server.focused_selector = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)  # type: ignore[attr-defined]
            result = {"ok": True}
        elif method == "node.fill":
            self.server.input_text = params["text"]  # type: ignore[attr-defined]
            selector = params["selector"]
            self.server.focused_selector = json.dumps(selector, sort_keys=True) if isinstance(selector, dict) else str(selector)  # type: ignore[attr-defined]
            result = {"ok": True}
        elif method == "input.actions":
            actions = []
            for name, entry in self.server.input_actions.items():  # type: ignore[attr-defined]
                if not params.get("include_ui", True) and str(name).startswith("ui_"):
                    continue
                if params.get("prefix") and not str(name).startswith(params["prefix"]):
                    continue
                strength = float(self.server.input_action_states.get(name, 0.0))  # type: ignore[attr-defined]
                actions.append(
                    {
                        "name": name,
                        "exists": True,
                        "pressed": strength > 0.0,
                        "strength": strength,
                        "deadzone": entry["deadzone"],
                        "events": list(entry["events"]) if params.get("include_events", True) else [],
                        "event_count": len(entry["events"]),
                    }
                )
            result = {"actions": actions, "count": len(actions)}
        elif method == "input.action.describe":
            action = params["action"]
            entry = self.server.input_actions.get(action)  # type: ignore[attr-defined]
            strength = float(self.server.input_action_states.get(action, 0.0))  # type: ignore[attr-defined]
            result = {
                "name": action,
                "exists": entry is not None,
                "pressed": entry is not None and strength > 0.0,
                "strength": strength if entry is not None else 0.0,
                "deadzone": entry["deadzone"] if entry else None,
                "events": list(entry["events"]) if entry and params.get("include_events", True) else [],
                "event_count": len(entry["events"]) if entry else 0,
            }
        elif method == "input.action.configure":
            action = params["action"]
            created = action not in self.server.input_actions  # type: ignore[attr-defined]
            entry = self.server.input_actions.setdefault(  # type: ignore[attr-defined]
                action,
                {"deadzone": params.get("deadzone", 0.5), "events": []},
            )
            if "deadzone" in params:
                entry["deadzone"] = params["deadzone"]
            if params.get("replace"):
                entry["events"] = []
            events = params.get("events", [])
            if isinstance(events, (dict, str)):
                events = [events]
            added = []
            existing = []
            for event in events:
                if event in entry["events"]:
                    existing.append(event)
                else:
                    entry["events"].append(event)
                    added.append(event)
            result = {
                "name": action,
                "exists": True,
                "pressed": float(self.server.input_action_states.get(action, 0.0)) > 0.0,  # type: ignore[attr-defined]
                "strength": float(self.server.input_action_states.get(action, 0.0)),  # type: ignore[attr-defined]
                "deadzone": entry["deadzone"],
                "events": list(entry["events"]),
                "event_count": len(entry["events"]),
                "created": created,
                "replaced": bool(params.get("replace")),
                "added_events": added,
                "existing_events": existing,
            }
        elif method == "input.action.erase":
            action = params["action"]
            entry = self.server.input_actions.get(action)  # type: ignore[attr-defined]
            if entry is None:
                result = {"action": action, "exists": False, "erased": False, "events_erased": 0}
            elif params.get("events") is not None:
                events = params["events"]
                if isinstance(events, (dict, str)):
                    events = [events]
                before = len(entry["events"])
                entry["events"] = [event for event in entry["events"] if event not in events]
                result = {
                    "name": action,
                    "exists": True,
                    "pressed": float(self.server.input_action_states.get(action, 0.0)) > 0.0,  # type: ignore[attr-defined]
                    "strength": float(self.server.input_action_states.get(action, 0.0)),  # type: ignore[attr-defined]
                    "deadzone": entry["deadzone"],
                    "events": list(entry["events"]),
                    "event_count": len(entry["events"]),
                    "events_erased": before - len(entry["events"]),
                }
            elif params.get("events_only"):
                erased = len(entry["events"])
                entry["events"] = []
                result = {
                    "name": action,
                    "exists": True,
                    "pressed": float(self.server.input_action_states.get(action, 0.0)) > 0.0,  # type: ignore[attr-defined]
                    "strength": float(self.server.input_action_states.get(action, 0.0)),  # type: ignore[attr-defined]
                    "deadzone": entry["deadzone"],
                    "events": [],
                    "event_count": 0,
                    "events_erased": erased,
                }
            else:
                erased = len(entry["events"])
                del self.server.input_actions[action]  # type: ignore[attr-defined]
                self.server.input_action_states.pop(action, None)  # type: ignore[attr-defined]
                result = {"action": action, "exists": False, "erased": True, "events_erased": erased}
        elif method == "input.action":
            action = str(params["action"])
            pressed = bool(params.get("pressed", True))
            strength = float(params.get("strength", 1.0)) if pressed else 0.0
            if pressed:
                self.server.input_action_states[action] = strength  # type: ignore[attr-defined]
            else:
                self.server.input_action_states[action] = 0.0  # type: ignore[attr-defined]
            result = {"action": action, "pressed": pressed, "strength": strength}
        elif method in {"input.key", "input.text"}:
            result = {"ok": True}
        elif method in {"input.mouse", "input.touch", "input.joypad"}:
            result = {"ok": True}
        elif method == "viewport.info":
            result = self.server.viewport_info()  # type: ignore[attr-defined]
        elif method == "viewport.set_size":
            self.server.viewport_width = int(params["width"])  # type: ignore[attr-defined]
            self.server.viewport_height = int(params["height"])  # type: ignore[attr-defined]
            result = self.server.viewport_info()  # type: ignore[attr-defined]
        elif method == "viewport.screenshot":
            screenshot_path = Path(str(params["path"]))
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
            result = {
                "path": str(params["path"]),
                "global_path": str(screenshot_path),
                "width": self.server.viewport_width,  # type: ignore[attr-defined]
                "height": self.server.viewport_height,  # type: ignore[attr-defined]
            }
        elif method in {"engine.info", "runtime.clock"}:
            self.server.process_frames += 1  # type: ignore[attr-defined]
            if self.server.process_frames % 2 == 0:  # type: ignore[attr-defined]
                self.server.physics_frames += 1  # type: ignore[attr-defined]
            result = {
                "uptime_ms": self.server.process_frames * 16,  # type: ignore[attr-defined]
                "process_frames": self.server.process_frames,  # type: ignore[attr-defined]
                "physics_frames": self.server.physics_frames,  # type: ignore[attr-defined]
                "drawn_frames": self.server.process_frames,  # type: ignore[attr-defined]
                "physics_ticks_per_second": 60,
                "time_scale": 1.0,
            }
            if method == "engine.info":
                result.update(
                    {
                        "godot": {
                            "major": 4,
                            "minor": 6,
                            "patch": 2,
                            "status": "stable",
                            "string": "4.6.2.stable.fake",
                        },
                        "editor": True,
                        "project_path": "/tmp/fake-godot-project/",
                        "root": "/root",
                        "current_scene": "/root/Main",
                        "edited_scene": "/root/Main",
                        "open_scenes": list(self.server.open_scenes),  # type: ignore[attr-defined]
                        "server_port": self.server.server_port,  # type: ignore[attr-defined]
                    }
                )
        elif method == "animation.describe":
            path = _fake_selector_path(params.get("selector", params.get("node", "AnimationPlayer")))
            result = self.server.animation_summary(path, include_tracks=params.get("include_tracks", False))  # type: ignore[attr-defined]
        elif method == "animation.play":
            path = _fake_selector_path(params.get("selector", params.get("node", "AnimationPlayer")))
            state = self.server.animation_state(path)  # type: ignore[attr-defined]
            animation = params.get("animation") or state["assigned_animation"]
            state["current_animation"] = animation
            state["assigned_animation"] = animation
            state["is_playing"] = True
            state["position"] = float(params.get("position", state["animations"][animation]["length"] if params.get("from_end") else 0.0))
            result = self.server.animation_summary(path, include_tracks=params.get("include_tracks", False))  # type: ignore[attr-defined]
        elif method == "animation.stop":
            path = _fake_selector_path(params.get("selector", params.get("node", "AnimationPlayer")))
            state = self.server.animation_state(path)  # type: ignore[attr-defined]
            state["is_playing"] = False
            if not params.get("keep_state", False):
                state["position"] = 0.0
            result = self.server.animation_summary(path, include_tracks=params.get("include_tracks", False))  # type: ignore[attr-defined]
        elif method == "animation.pause":
            path = _fake_selector_path(params.get("selector", params.get("node", "AnimationPlayer")))
            state = self.server.animation_state(path)  # type: ignore[attr-defined]
            state["is_playing"] = False
            result = self.server.animation_summary(path, include_tracks=params.get("include_tracks", False))  # type: ignore[attr-defined]
        elif method == "animation.seek":
            path = _fake_selector_path(params.get("selector", params.get("node", "AnimationPlayer")))
            state = self.server.animation_state(path)  # type: ignore[attr-defined]
            state["position"] = float(params["position"])
            result = self.server.animation_summary(path, include_tracks=params.get("include_tracks", False))  # type: ignore[attr-defined]
        elif method == "animation.advance":
            path = _fake_selector_path(params.get("selector", params.get("node", "AnimationPlayer")))
            state = self.server.animation_state(path)  # type: ignore[attr-defined]
            current = state["current_animation"] or state["assigned_animation"]
            length = float(state["animations"][current]["length"])
            state["position"] = min(length, float(state["position"]) + float(params.get("delta", 0.0)))
            result = self.server.animation_summary(path, include_tracks=params.get("include_tracks", False))  # type: ignore[attr-defined]
        elif method == "physics2d.point":
            x = float(params.get("x", 0.0))
            y = float(params.get("y", 0.0))
            collision = self.server.physics_collision() if 600.0 <= x <= 680.0 and 400.0 <= y <= 440.0 else None  # type: ignore[attr-defined]
            result = {
                "position": {"$type": "Vector2", "x": x, "y": y},
                "collisions": [] if collision is None else [collision],
                "count": 0 if collision is None else 1,
            }
        elif method == "physics2d.ray":
            from_x = float(params.get("from_x", 0.0))
            from_y = float(params.get("from_y", 0.0))
            to_x = float(params.get("to_x", 0.0))
            to_y = float(params.get("to_y", 0.0))
            hit = from_y == 420.0 and min(from_x, to_x) <= 640.0 <= max(from_x, to_x)
            collision = self.server.physics_collision(position_x=600.0 if from_x < to_x else 680.0, position_y=420.0) if hit else {}  # type: ignore[attr-defined]
            result = {
                "from": {"$type": "Vector2", "x": from_x, "y": from_y},
                "to": {"$type": "Vector2", "x": to_x, "y": to_y},
                "hit": hit,
                "collision": collision,
            }
        elif method == "physics3d.point":
            x = float(params.get("x", 0.0))
            y = float(params.get("y", 0.0))
            z = float(params.get("z", 0.0))
            collision = (
                self.server.physics3d_collision()  # type: ignore[attr-defined]
                if x == 1.0 and y == 2.0 and z == 3.0
                else None
            )
            result = {
                "position": {"$type": "Vector3", "x": x, "y": y, "z": z},
                "collisions": [] if collision is None else [collision],
                "count": 0 if collision is None else 1,
            }
        elif method == "physics3d.ray":
            from_x = float(params.get("from_x", 0.0))
            from_y = float(params.get("from_y", 0.0))
            from_z = float(params.get("from_z", 0.0))
            to_x = float(params.get("to_x", 0.0))
            to_y = float(params.get("to_y", 0.0))
            to_z = float(params.get("to_z", 0.0))
            crosses_target = (
                from_y == 2.0
                and to_y == 2.0
                and from_z == 3.0
                and to_z == 3.0
                and min(from_x, to_x) <= 1.0 <= max(from_x, to_x)
            )
            collision = (
                self.server.physics3d_collision(position_x=0.0 if from_x < to_x else 2.0)  # type: ignore[attr-defined]
                if crosses_target
                else {}
            )
            result = {
                "from": {"$type": "Vector3", "x": from_x, "y": from_y, "z": from_z},
                "to": {"$type": "Vector3", "x": to_x, "y": to_y, "z": to_z},
                "hit": crosses_target,
                "collision": collision,
            }
        elif method == "camera3d.ray":
            result = self.server.camera3d_ray(  # type: ignore[attr-defined]
                float(params.get("x", 0.0)),
                float(params.get("y", 0.0)),
                max_distance=float(params.get("max_distance", 1000.0)),
            )
        elif method == "camera3d.pick":
            x = float(params.get("x", 0.0))
            y = float(params.get("y", 0.0))
            result = self.server.camera3d_ray(  # type: ignore[attr-defined]
                x,
                y,
                max_distance=float(params.get("max_distance", 1000.0)),
            )
            hit = x == 360.0 and y == 225.0 and int(params.get("collision_mask", 8)) == 8
            result["hit"] = hit
            result["collision"] = (
                self.server.physics3d_collision(position_x=0.0, position_y=0.0, position_z=1.0)  # type: ignore[attr-defined]
                if hit
                else {}
            )
        elif method == "trace.start":
            if params.get("clear", True):
                self.server.trace_events = []  # type: ignore[attr-defined]
            self.server.trace_enabled = True  # type: ignore[attr-defined]
            self.server.trace_max_events = max(1, int(params.get("max_events", 1000)))  # type: ignore[attr-defined]
            self.server.trace_events.append(  # type: ignore[attr-defined]
                {"type": "trace.start", "data": {"max_events": self.server.trace_max_events}}
            )
            result = {"enabled": True, "events": len(self.server.trace_events), "max_events": self.server.trace_max_events}  # type: ignore[attr-defined]
        elif method == "trace.stop":
            self.server.trace_events.append({"type": "trace.stop", "data": {}})  # type: ignore[attr-defined]
            self.server.trace_enabled = False  # type: ignore[attr-defined]
            result = {"enabled": False, "events": len(self.server.trace_events)}  # type: ignore[attr-defined]
        elif method == "trace.events":
            result = {"enabled": self.server.trace_enabled, "events": list(self.server.trace_events)}  # type: ignore[attr-defined]
            if params.get("clear"):
                self.server.trace_events = []  # type: ignore[attr-defined]
        elif method == "trace.clear":
            self.server.trace_events = []  # type: ignore[attr-defined]
            result = {"enabled": self.server.trace_enabled, "events": 0}  # type: ignore[attr-defined]
        elif method == "scene.current":
            scene = self.server.current_scene  # type: ignore[attr-defined]
            result = {
                "path": "/root/" + Pathish(scene).stem_title,
                "name": Pathish(scene).stem_title,
                "scene_file_path": scene,
            }
        elif method == "scene.files":
            raw_extensions = params.get("extensions", params.get("extension"))
            if isinstance(raw_extensions, str):
                extensions = [raw_extensions]
            elif isinstance(raw_extensions, list):
                extensions = [str(item) for item in raw_extensions]
            else:
                extensions = None
            result = _fake_scene_files(
                self.server.files,  # type: ignore[attr-defined]
                self.server.resource_dependencies,  # type: ignore[attr-defined]
                path=str(params.get("path", "res://")),
                name=str(params.get("name", "")),
                name_contains=str(params.get("name_contains", "")),
                root_name=str(params.get("root_name", "")),
                root_class=str(params.get("root_class", params.get("class", params.get("class_name", "")))),
                extensions=extensions,
                include_dependencies=bool(params.get("include_dependencies", True)),
                include_nodes=bool(params.get("include_nodes", False)),
                max_results=int(params.get("max_results", 200)),
            )
        elif method == "scene.file.describe":
            result = _fake_scene_summary(
                str(params["path"]),
                self.server.files,  # type: ignore[attr-defined]
                self.server.resource_dependencies,  # type: ignore[attr-defined]
                include_dependencies=bool(params.get("include_dependencies", True)),
                include_nodes=bool(params.get("include_nodes", True)),
                include_properties=bool(params.get("include_properties", False)),
                include_resources=bool(params.get("include_resources", True)),
                include_connections=bool(params.get("include_connections", True)),
            )
            if params.get("include_source"):
                value = self.server.files.get(params["path"], "")  # type: ignore[attr-defined]
                result["source"] = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
        elif method == "scene.change":
            result = {"requested_path": params["path"], "error": 0}
            self.server.current_scene = params["path"]  # type: ignore[attr-defined]
        elif method == "scene.new":
            self.server.current_scene = ""  # type: ignore[attr-defined]
            self.server.edited_scene_name = params.get("name", "Main")  # type: ignore[attr-defined]
            result = {
                "name": self.server.edited_scene_name,  # type: ignore[attr-defined]
                "class": params.get("class", "Node2D"),
                "path": f"/root/{self.server.edited_scene_name}",  # type: ignore[attr-defined]
            }
        elif method == "scene.open":
            self.server.current_scene = params["path"]  # type: ignore[attr-defined]
            self.server.edited_scene_name = Pathish(params["path"]).stem_title  # type: ignore[attr-defined]
            if params["path"] not in self.server.open_scenes:  # type: ignore[attr-defined]
                self.server.open_scenes.append(params["path"])  # type: ignore[attr-defined]
            result = {"path": params["path"]}
        elif method == "scene.save":
            path = params.get("path", "")
            if path:
                self.server.current_scene = path  # type: ignore[attr-defined]
                self.server.edited_scene_name = Pathish(path).stem_title  # type: ignore[attr-defined]
                self.server.files[path] = "[gd_scene format=3]\n"  # type: ignore[attr-defined]
                if path not in self.server.open_scenes:  # type: ignore[attr-defined]
                    self.server.open_scenes.append(path)  # type: ignore[attr-defined]
            result = {"saved": True, "path": path}
        elif method == "editor.selection.get":
            result = {"nodes": self.server.selected_nodes, "count": len(self.server.selected_nodes)}  # type: ignore[attr-defined]
        elif method == "editor.selection.set":
            selectors = params.get("selectors") or [params.get("selector", params.get("path"))]
            self.server.selected_nodes = [  # type: ignore[attr-defined]
                {
                    "name": str(selector).rsplit("/", 1)[-1].lstrip("#"),
                    "path": f"/root/Main/{str(selector).rsplit('/', 1)[-1].lstrip('#')}",
                }
                for selector in selectors
                if selector
            ]
            result = {"nodes": self.server.selected_nodes, "count": len(self.server.selected_nodes)}  # type: ignore[attr-defined]
        elif method == "editor.play":
            scene = str(params.get("scene", "current"))
            if scene == "main":
                playing_scene = self.server.project_settings.get("application/run/main_scene", "")  # type: ignore[attr-defined]
            elif scene == "current":
                playing_scene = self.server.current_scene  # type: ignore[attr-defined]
            else:
                playing_scene = scene
            self.server.playing = True  # type: ignore[attr-defined]
            self.server.playing_scene = playing_scene  # type: ignore[attr-defined]
            result = {"playing": True, "scene": scene}
        elif method == "editor.stop":
            self.server.playing = False  # type: ignore[attr-defined]
            self.server.playing_scene = ""  # type: ignore[attr-defined]
            result = {"playing": False}
        elif method == "editor.status":
            scene = self.server.current_scene  # type: ignore[attr-defined]
            scene_name = self.server.edited_scene_name or Pathish(scene).stem_title  # type: ignore[attr-defined]
            result = {
                "editor": True,
                "open_scenes": list(self.server.open_scenes),  # type: ignore[attr-defined]
                "edited_scene": f"/root/{scene_name}",
                "edited_scene_name": scene_name,
                "edited_scene_file_path": scene,
                "selection": {"nodes": self.server.selected_nodes, "count": len(self.server.selected_nodes)},  # type: ignore[attr-defined]
                "playing": self.server.playing,  # type: ignore[attr-defined]
                "playing_scene": self.server.playing_scene,  # type: ignore[attr-defined]
                "ui": _fake_editor_ui_status(self.server),
                "script_editor": _fake_script_editor_status(self.server),
            }
        elif method == "editor.ui.status":
            result = _fake_editor_ui_status(self.server)
        elif method == "editor.ui.switch_main_screen":
            self.server.main_screen_name = str(params["name"])  # type: ignore[attr-defined]
            ui_status = _fake_editor_ui_status(self.server)
            result = {
                "name": params["name"],
                "requested": params["name"],
                "before": {},
                "ui": ui_status,
                "main_screen": ui_status["main_screen"],
                "main_screen_name": ui_status["main_screen_name"],
                "main_screen_path": ui_status["main_screen_path"],
                "changed": True,
                "matched": True,
            }
        elif method == "editor.ui.hide_bottom_panel":
            self.server.bottom_panel_hidden = True  # type: ignore[attr-defined]
            ui_status = _fake_editor_ui_status(self.server)
            result = {
                "hidden": True,
                "before": {},
                "ui": ui_status,
                "bottom_panel": ui_status["bottom_panel"],
            }
        elif method == "editor.history":
            result = {
                "available": True,
                "history_id": params.get("history_id", 0),
                "can_undo": bool(self.server.undo_stack),  # type: ignore[attr-defined]
                "can_redo": bool(self.server.redo_stack),  # type: ignore[attr-defined]
                "version": len(self.server.undo_stack),  # type: ignore[attr-defined]
                "current_action_name": "",
                "target": None,
            }
        elif method == "editor.undo":
            changed = bool(self.server.undo_stack)  # type: ignore[attr-defined]
            if changed:
                action = self.server.undo_stack.pop()  # type: ignore[attr-defined]
                if action["type"] == "set_property":
                    self.server.node_properties.setdefault(action["selector"], {})[action["property"]] = action["previous"]  # type: ignore[attr-defined]
                elif action["type"] == "set_properties":
                    self.server.node_properties.setdefault(action["selector"], {}).update(action["previous"])  # type: ignore[attr-defined]
                elif action["type"] == "set_all_properties":
                    for entry in action["entries"]:
                        for key in entry["keys"]:
                            self.server.node_properties.setdefault(key, {}).update(entry["previous"])  # type: ignore[attr-defined]
                elif action["type"] == "set_metadata":
                    metadata = self.server.node_metadata.setdefault(action["selector"], {})  # type: ignore[attr-defined]
                    for key, previous in action["previous"].items():
                        if previous["exists"]:
                            metadata[key] = previous["value"]
                        else:
                            metadata.pop(key, None)
                elif action["type"] == "remove_metadata":
                    metadata = self.server.node_metadata.setdefault(action["selector"], {})  # type: ignore[attr-defined]
                    for key, previous in action["previous"].items():
                        if previous["exists"]:
                            metadata[key] = previous["value"]
                        else:
                            metadata.pop(key, None)
                elif action["type"] == "create_node":
                    self.server.created_nodes.discard(action["path"])  # type: ignore[attr-defined]
                    self.server.deleted_nodes.add(action["path"])  # type: ignore[attr-defined]
                    self.server.node_summaries.pop(action["path"], None)  # type: ignore[attr-defined]
                self.server.redo_stack.append(action)  # type: ignore[attr-defined]
            result = {
                "available": True,
                "history_id": params.get("history_id", 0),
                "can_undo": bool(self.server.undo_stack),  # type: ignore[attr-defined]
                "can_redo": bool(self.server.redo_stack),  # type: ignore[attr-defined]
                "changed": changed,
                "action": "undo",
            }
        elif method == "editor.redo":
            changed = bool(self.server.redo_stack)  # type: ignore[attr-defined]
            if changed:
                action = self.server.redo_stack.pop()  # type: ignore[attr-defined]
                if action["type"] == "set_property":
                    self.server.node_properties.setdefault(action["selector"], {})[action["property"]] = action["value"]  # type: ignore[attr-defined]
                elif action["type"] == "set_properties":
                    self.server.node_properties.setdefault(action["selector"], {}).update(action["values"])  # type: ignore[attr-defined]
                elif action["type"] == "set_all_properties":
                    for entry in action["entries"]:
                        for key in entry["keys"]:
                            self.server.node_properties.setdefault(key, {}).update(entry["values"])  # type: ignore[attr-defined]
                elif action["type"] == "set_metadata":
                    self.server.node_metadata.setdefault(action["selector"], {}).update(action["values"])  # type: ignore[attr-defined]
                elif action["type"] == "remove_metadata":
                    metadata = self.server.node_metadata.setdefault(action["selector"], {})  # type: ignore[attr-defined]
                    for key in action["names"]:
                        metadata.pop(key, None)
                elif action["type"] == "create_node":
                    self.server.created_nodes.add(action["path"])  # type: ignore[attr-defined]
                    self.server.deleted_nodes.discard(action["path"])  # type: ignore[attr-defined]
                    self.server.node_summaries[action["path"]] = dict(action.get("summary", {}))  # type: ignore[attr-defined]
                self.server.undo_stack.append(action)  # type: ignore[attr-defined]
            result = {
                "available": True,
                "history_id": params.get("history_id", 0),
                "can_undo": bool(self.server.undo_stack),  # type: ignore[attr-defined]
                "can_redo": bool(self.server.redo_stack),  # type: ignore[attr-defined]
                "changed": changed,
                "action": "redo",
            }
        elif method == "editor.inspect":
            target = params.get("selector") or params.get("path") or params.get("resource_path")
            result = {
                "target": {"path": str(target)},
                "property": params.get("property", ""),
                "inspector_only": params.get("inspector_only", False),
            }
        elif method == "editor.inspector.describe":
            target = params.get("resource_path") or params.get("selector", "#CounterButton")
            state = self.server.inspector_state(str(target))  # type: ignore[attr-defined]
            requested = params.get("properties") or ["text"]
            properties = []
            for property_name in requested:
                value = state.get(str(property_name))
                properties.append(
                    {
                        "name": str(property_name),
                        "type": 4 if isinstance(value, str) else 1,
                        "type_name": "String" if isinstance(value, str) else "Bool",
                        "hint": 0,
                        "hint_string": "",
                        "usage": 4096,
                        "editor_visible": True,
                        "exists": str(property_name) in state,
                        "value": value,
                    }
                )
            result = {
                "target": {"path": str(target), "name": str(target).rsplit("/", 1)[-1].lstrip("#")},
                "count": len(properties),
                "properties": properties,
            }
        elif method == "editor.inspector.get_property":
            target = params.get("resource_path") or params.get("selector", "#CounterButton")
            state = self.server.inspector_state(str(target))  # type: ignore[attr-defined]
            value = state.get(params["property"])
            result = {
                "target": {"path": str(target), "name": str(target).rsplit("/", 1)[-1].lstrip("#")},
                "property": {
                    "name": params["property"],
                    "type": 4 if isinstance(value, str) else 1,
                    "type_name": "String" if isinstance(value, str) else "Bool",
                    "hint": 0,
                    "hint_string": "",
                    "usage": 4096,
                    "editor_visible": True,
                    "exists": params["property"] in state,
                    "value": value,
                },
                "value": value,
            }
        elif method == "editor.inspector.set_property":
            target = params.get("resource_path") or params.get("selector", "#CounterButton")
            state = self.server.inspector_state(str(target))  # type: ignore[attr-defined]
            state[params["property"]] = params["value"]
            result = {
                "target": {"path": str(target), "name": str(target).rsplit("/", 1)[-1].lstrip("#")},
                "property": {
                    "name": params["property"],
                    "type": 4 if isinstance(params["value"], str) else 1,
                    "type_name": "String" if isinstance(params["value"], str) else "Bool",
                    "hint": 0,
                    "hint_string": "",
                    "usage": 4096,
                    "editor_visible": True,
                    "exists": True,
                    "value": params["value"],
                },
                "value": params["value"],
                "saved": params.get("save", False),
            }
        elif method == "editor.inspector.set_properties":
            target = params.get("resource_path") or params.get("selector", "#CounterButton")
            state = self.server.inspector_state(str(target))  # type: ignore[attr-defined]
            values = dict(params["values"])
            state.update(values)
            properties = [
                {
                    "name": str(property_name),
                    "type": 4 if isinstance(value, str) else 1,
                    "type_name": "String" if isinstance(value, str) else "Bool",
                    "hint": 0,
                    "hint_string": "",
                    "usage": 4096,
                    "editor_visible": True,
                    "exists": True,
                    "value": value,
                }
                for property_name, value in values.items()
            ]
            result = {
                "target": {"path": str(target), "name": str(target).rsplit("/", 1)[-1].lstrip("#")},
                "properties": properties,
                "values": values,
                "count": len(values),
                "saved": params.get("save", False),
            }
        elif method == "editor.script.open":
            if params["path"] not in self.server.open_scripts:  # type: ignore[attr-defined]
                self.server.open_scripts.append(params["path"])  # type: ignore[attr-defined]
            if params.get("grab_focus", True):
                self.server.current_script = params["path"]  # type: ignore[attr-defined]
            result = {
                "script": {"path": params["path"], "class": "Script"},
                "path": params["path"],
                "line": params.get("line", -1),
                "column": params.get("column", 0),
                "opened": True,
                "script_editor": _fake_script_editor_status(self.server),
            }
        elif method == "editor.script.status":
            result = _fake_script_editor_status(self.server)
        elif method == "editor.script.describe":
            result = _fake_script_file_description(
                str(params["path"]),
                self.server.files,  # type: ignore[attr-defined]
                include_source=bool(params.get("include_source", False)),
            )
        elif method == "script.file.describe":
            result = _fake_script_file_description(
                str(params["path"]),
                self.server.files,  # type: ignore[attr-defined]
                include_source=bool(params.get("include_source", False)),
            )
        elif method == "script.classes":
            result = _fake_script_classes(
                self.server.files,  # type: ignore[attr-defined]
                path=str(params.get("path", "res://")),
                class_name=str(params.get("class_name", params.get("class", ""))),
                name_contains=str(params.get("name_contains", "")),
                extends=str(params.get("extends", "")),
                base_class=str(params.get("base_class", "")),
                include_anonymous=bool(params.get("include_anonymous", False)),
                max_results=int(params.get("max_results", 200)),
            )
        elif method == "editor.filesystem.scan":
            result = {"paths": params.get("paths") or ([params["path"]] if params.get("path") else []), "requested": True}
        elif method == "editor.filesystem.describe":
            result = _fake_editor_filesystem_entry(
                params["path"],
                self.server.files,  # type: ignore[attr-defined]
                self.server.directories,  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted,  # type: ignore[attr-defined]
                self.server.editor_filesystem_selected_path,  # type: ignore[attr-defined]
            )
        elif method == "editor.filesystem.find":
            entries = _fake_editor_filesystem_entries(
                params["path"],
                self.server.files,  # type: ignore[attr-defined]
                self.server.directories,  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted,  # type: ignore[attr-defined]
                self.server.editor_filesystem_selected_path,  # type: ignore[attr-defined]
                recursive=bool(params.get("recursive", True)),
                include_dirs=bool(params.get("include_dirs", False)),
            )
            if params.get("name"):
                entries = [entry for entry in entries if entry["name"] == params["name"]]
            if params.get("name_contains"):
                entries = [entry for entry in entries if str(params["name_contains"]) in entry["name"]]
            if params.get("extension"):
                entries = [entry for entry in entries if entry.get("extension") == params["extension"]]
            if params.get("resource_type"):
                entries = [entry for entry in entries if entry.get("resource_type") == params["resource_type"]]
            result = {
                "path": params["path"],
                "count": len(entries),
                "entries": entries[: int(params.get("max_results", 500))],
            }
        elif method == "editor.filesystem.select":
            self.server.editor_filesystem_selected_path = params["path"]  # type: ignore[attr-defined]
            result = _fake_editor_filesystem_entry(
                params["path"],
                self.server.files,  # type: ignore[attr-defined]
                self.server.directories,  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted,  # type: ignore[attr-defined]
                self.server.editor_filesystem_selected_path,  # type: ignore[attr-defined]
            )
        elif method == "editor.filesystem.open":
            path = str(params["path"])
            self.server.editor_filesystem_selected_path = path  # type: ignore[attr-defined]
            entry = _fake_editor_filesystem_entry(
                path,
                self.server.files,  # type: ignore[attr-defined]
                self.server.directories,  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted,  # type: ignore[attr-defined]
                self.server.editor_filesystem_selected_path,  # type: ignore[attr-defined]
            )
            mode = str(params.get("mode", "auto"))
            action = mode
            if mode == "auto":
                if entry.get("is_directory"):
                    action = "select"
                elif entry.get("extension") in {"tscn", "scn"} or entry.get("resource_type") == "PackedScene":
                    action = "scene"
                elif entry.get("extension") == "gd" or entry.get("resource_type") == "GDScript":
                    action = "script"
                elif entry.get("is_resource"):
                    action = "resource"
                else:
                    action = "select"
            result = {
                "path": path,
                "mode": mode,
                "action": action,
                "selected": True,
                "entry": entry,
                "opened": False,
                "inspected": False,
            }
            if action == "scene":
                self.server.current_scene = path  # type: ignore[attr-defined]
                self.server.edited_scene_name = Pathish(path).stem_title  # type: ignore[attr-defined]
                if path not in self.server.open_scenes:  # type: ignore[attr-defined]
                    self.server.open_scenes.append(path)  # type: ignore[attr-defined]
                result["opened"] = True
                result["scene"] = {"path": path}
            elif action == "script":
                if path not in self.server.open_scripts:  # type: ignore[attr-defined]
                    self.server.open_scripts.append(path)  # type: ignore[attr-defined]
                if params.get("grab_focus", True):
                    self.server.current_script = path  # type: ignore[attr-defined]
                result["opened"] = True
                result["script"] = {
                    "script": {"path": path, "class": "Script"},
                    "path": path,
                    "line": params.get("line", -1),
                    "column": params.get("column", 0),
                    "opened": True,
                    "script_editor": _fake_script_editor_status(self.server),
                }
            elif action in {"resource", "inspect"}:
                result["inspected"] = bool(entry.get("is_resource"))
                result["resource"] = {"path": path, "class": entry.get("resource_type", "Resource")}
            result["entry"] = _fake_editor_filesystem_entry(
                path,
                self.server.files,  # type: ignore[attr-defined]
                self.server.directories,  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted,  # type: ignore[attr-defined]
                self.server.editor_filesystem_selected_path,  # type: ignore[attr-defined]
            )
        elif method == "fs.write_text":
            self.server.directories.update(_fake_res_parent_dirs(params["path"]))  # type: ignore[attr-defined]
            self.server.editor_filesystem_deleted.discard(params["path"])  # type: ignore[attr-defined]
            self.server.files[params["path"]] = params["text"]  # type: ignore[attr-defined]
            result = {"path": params["path"], "bytes": len(params["text"].encode("utf-8"))}
        elif method == "fs.read_text":
            result = {"path": params["path"], "text": self.server.files.get(params["path"], "")}  # type: ignore[attr-defined]
        elif method == "fs.write_bytes":
            data = base64.b64decode(params["base64"])
            self.server.directories.update(_fake_res_parent_dirs(params["path"]))  # type: ignore[attr-defined]
            self.server.editor_filesystem_deleted.discard(params["path"])  # type: ignore[attr-defined]
            self.server.files[params["path"]] = data  # type: ignore[attr-defined]
            result = {"path": params["path"], "bytes": len(data)}
        elif method == "fs.read_bytes":
            data = self.server.files.get(params["path"], b"")  # type: ignore[attr-defined]
            if isinstance(data, str):
                data = data.encode("utf-8")
            result = {
                "path": params["path"],
                "base64": base64.b64encode(data).decode("ascii"),
                "bytes": len(data),
            }
        elif method == "fs.exists":
            is_file = params["path"] in self.server.files  # type: ignore[attr-defined]
            is_directory = params["path"] in self.server.directories  # type: ignore[attr-defined]
            result = {
                "path": params["path"],
                "exists": is_file or is_directory,
                "type": "file" if is_file else ("directory" if is_directory else "missing"),
            }
        elif method == "fs.info":
            result = _fake_editor_filesystem_entry(
                params["path"],
                self.server.files,  # type: ignore[attr-defined]
                self.server.directories,  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted,  # type: ignore[attr-defined]
                self.server.editor_filesystem_selected_path,  # type: ignore[attr-defined]
            )
        elif method == "fs.list":
            path = "res://" if params["path"] == "res://" else params["path"].rstrip("/")
            prefix = f"{path}/" if path != "res://" else "res://"
            files = sorted(
                file_path.removeprefix(prefix)
                for file_path in self.server.files  # type: ignore[attr-defined]
                if file_path.startswith(prefix) and "/" not in file_path.removeprefix(prefix)
            )
            directories = sorted(
                directory.removeprefix(prefix)
                for directory in self.server.directories  # type: ignore[attr-defined]
                if directory.startswith(prefix)
                and directory != path
                and "/" not in directory.removeprefix(prefix).strip("/")
            )
            result = {"path": params["path"], "files": files, "directories": directories}
        elif method == "fs.find":
            entries = _fake_editor_filesystem_entries(
                params["path"],
                self.server.files,  # type: ignore[attr-defined]
                self.server.directories,  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted,  # type: ignore[attr-defined]
                self.server.editor_filesystem_selected_path,  # type: ignore[attr-defined]
                recursive=bool(params.get("recursive", True)),
                include_dirs=bool(params.get("include_dirs", False)),
            )
            if params.get("name"):
                entries = [entry for entry in entries if entry["name"] == params["name"]]
            if params.get("name_contains"):
                entries = [entry for entry in entries if str(params["name_contains"]) in entry["name"]]
            if params.get("extension"):
                extension = str(params["extension"]).removeprefix(".")
                entries = [entry for entry in entries if entry.get("extension") == extension]
            if params.get("resource_type"):
                entries = [entry for entry in entries if entry.get("resource_type") == params["resource_type"]]
            result = {
                "path": params["path"],
                "count": len(entries),
                "entries": entries[: int(params.get("max_results", 500))],
            }
        elif method == "fs.grep":
            entries = _fake_editor_filesystem_entries(
                params["path"],
                self.server.files,  # type: ignore[attr-defined]
                self.server.directories,  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted,  # type: ignore[attr-defined]
                self.server.editor_filesystem_selected_path,  # type: ignore[attr-defined]
                recursive=bool(params.get("recursive", True)),
                include_dirs=False,
            )
            if params.get("name"):
                entries = [entry for entry in entries if entry["name"] == params["name"]]
            if params.get("name_contains"):
                entries = [entry for entry in entries if str(params["name_contains"]) in entry["name"]]
            if params.get("extension"):
                extension = str(params["extension"]).removeprefix(".")
                entries = [entry for entry in entries if entry.get("extension") == extension]
            if params.get("resource_type"):
                entries = [entry for entry in entries if entry.get("resource_type") == params["resource_type"]]
            query = str(params["query"])
            needle = query if params.get("case_sensitive", True) else query.lower()
            context_lines = int(params.get("context_lines", 0))
            max_results = int(params.get("max_results", 500))
            max_matches_per_file = int(params.get("max_matches_per_file", 20))
            matches: list[dict[str, Any]] = []
            files_checked = 0
            for entry in entries[: int(params.get("max_files", 500))]:
                path = entry["path"]
                if not params.get("include_binary", False) and not _fake_text_search_path(path):
                    continue
                value = self.server.files.get(path, "")  # type: ignore[attr-defined]
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                files_checked += 1
                file_matches = 0
                lines = str(value).split("\n")
                for line_index, line in enumerate(lines):
                    haystack = line if params.get("case_sensitive", True) else line.lower()
                    column = haystack.find(needle)
                    while column >= 0:
                        matches.append(
                            {
                                "path": path,
                                "line": line_index + 1,
                                "column": column,
                                "text": line,
                                "before": [
                                    {"line": index + 1, "text": lines[index]}
                                    for index in range(max(0, line_index - context_lines), line_index)
                                ],
                                "after": [
                                    {"line": index + 1, "text": lines[index]}
                                    for index in range(line_index + 1, min(len(lines), line_index + 1 + context_lines))
                                ],
                            }
                        )
                        file_matches += 1
                        if len(matches) >= max_results or file_matches >= max_matches_per_file:
                            break
                        column = haystack.find(needle, column + max(1, len(needle)))
                    if len(matches) >= max_results or file_matches >= max_matches_per_file:
                        break
                if len(matches) >= max_results:
                    break
            result = {
                "path": params["path"],
                "query": query,
                "case_sensitive": params.get("case_sensitive", True),
                "count": len(matches),
                "files_checked": files_checked,
                "matches": matches,
            }
        elif method == "fs.replace_text":
            path = params["path"]
            value = self.server.files.get(path, "")  # type: ignore[attr-defined]
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            old_text = str(params.get("old_text", params.get("search", "")))
            new_text = str(params.get("new_text", params.get("replace", "")))
            replacement = _fake_replace_text(
                str(value),
                old_text,
                new_text,
                case_sensitive=bool(params.get("case_sensitive", True)),
                max_preview=int(params.get("max_preview", 20)),
            )
            before_bytes = len(str(value).encode("utf-8"))
            after_bytes = len(str(replacement["text"]).encode("utf-8"))
            dry_run = bool(params.get("dry_run", False))
            if not dry_run:
                self.server.files[path] = str(replacement["text"])  # type: ignore[attr-defined]
                self.server.directories.update(_fake_res_parent_dirs(path))  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted.discard(path)  # type: ignore[attr-defined]
            result = {
                "path": path,
                "case_sensitive": params.get("case_sensitive", True),
                "dry_run": dry_run,
                "changed": str(replacement["text"]) != str(value),
                "match_count": replacement["match_count"],
                "replacements": replacement["replacements"],
                "bytes_before": before_bytes,
                "bytes_after": after_bytes,
                "file_before": {"path": path, "exists": True, "bytes": before_bytes},
                "file_after": {"path": path, "exists": True, "bytes": after_bytes},
                "edits": replacement["edits"],
            }
            if params.get("include_text", False):
                result["text"] = replacement["text"]
        elif method == "fs.replace_text_many":
            entries = _fake_editor_filesystem_entries(
                params["path"],
                self.server.files,  # type: ignore[attr-defined]
                self.server.directories,  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted,  # type: ignore[attr-defined]
                self.server.editor_filesystem_selected_path,  # type: ignore[attr-defined]
                recursive=bool(params.get("recursive", True)),
                include_dirs=False,
            )
            if params.get("name"):
                entries = [entry for entry in entries if entry["name"] == params["name"]]
            if params.get("name_contains"):
                entries = [entry for entry in entries if str(params["name_contains"]) in entry["name"]]
            if params.get("extension"):
                extension = str(params["extension"]).removeprefix(".")
                entries = [entry for entry in entries if entry.get("extension") == extension]
            if params.get("resource_type"):
                entries = [entry for entry in entries if entry.get("resource_type") == params["resource_type"]]
            old_text = str(params.get("old_text", params.get("search", "")))
            new_text = str(params.get("new_text", params.get("replace", "")))
            dry_run = bool(params.get("dry_run", True))
            changes: list[dict[str, Any]] = []
            files_checked = 0
            total_replacements = 0
            for entry in entries[: int(params.get("max_files", 500))]:
                path = entry["path"]
                if not params.get("include_binary", False) and not _fake_text_search_path(path):
                    continue
                value = self.server.files.get(path, "")  # type: ignore[attr-defined]
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                files_checked += 1
                replacement = _fake_replace_text(
                    str(value),
                    old_text,
                    new_text,
                    case_sensitive=bool(params.get("case_sensitive", True)),
                    max_preview=int(params.get("max_preview", 20)),
                )
                match_count = int(replacement["match_count"])
                if match_count <= 0:
                    continue
                total_replacements += match_count
                before_bytes = len(str(value).encode("utf-8"))
                after_bytes = len(str(replacement["text"]).encode("utf-8"))
                change = {
                    "path": path,
                    "changed": str(replacement["text"]) != str(value),
                    "match_count": match_count,
                    "replacements": match_count,
                    "bytes_before": before_bytes,
                    "bytes_after": after_bytes,
                    "file_before": {"path": path, "exists": True, "bytes": before_bytes},
                    "file_after": {"path": path, "exists": True, "bytes": after_bytes},
                    "edits": replacement["edits"],
                }
                if params.get("include_text", False):
                    change["text"] = replacement["text"]
                changes.append(change)
                if not dry_run:
                    self.server.files[path] = str(replacement["text"])  # type: ignore[attr-defined]
                    self.server.directories.update(_fake_res_parent_dirs(path))  # type: ignore[attr-defined]
                    self.server.editor_filesystem_deleted.discard(path)  # type: ignore[attr-defined]
            result = {
                "path": params["path"],
                "case_sensitive": params.get("case_sensitive", True),
                "dry_run": dry_run,
                "files_checked": files_checked,
                "changed_files": len(changes),
                "count": len(changes),
                "replacements": total_replacements,
                "changes": changes,
            }
        elif method == "fs.mkdir":
            directory_path = params["path"].rstrip("/")
            self.server.directories.add(directory_path)  # type: ignore[attr-defined]
            self.server.directories.update(_fake_res_parent_dirs(directory_path))  # type: ignore[attr-defined]
            self.server.editor_filesystem_deleted.discard(directory_path)  # type: ignore[attr-defined]
            result = {"path": params["path"]}
        elif method == "fs.copy":
            source = params["source"]
            destination = params["destination"]
            value = self.server.files[source]  # type: ignore[attr-defined]
            self.server.directories.update(_fake_res_parent_dirs(destination))  # type: ignore[attr-defined]
            self.server.editor_filesystem_deleted.discard(destination)  # type: ignore[attr-defined]
            self.server.files[destination] = value  # type: ignore[attr-defined]
            bytes_count = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
            result = {"source": source, "destination": destination, "type": "file", "bytes": bytes_count}
        elif method == "fs.move":
            source = params["source"]
            destination = params["destination"]
            self.server.directories.update(_fake_res_parent_dirs(destination))  # type: ignore[attr-defined]
            self.server.editor_filesystem_deleted.add(source.rstrip("/"))  # type: ignore[attr-defined]
            self.server.editor_filesystem_deleted.discard(destination.rstrip("/"))  # type: ignore[attr-defined]
            if source in self.server.files:  # type: ignore[attr-defined]
                value = self.server.files.pop(source)  # type: ignore[attr-defined]
                self.server.files[destination] = value  # type: ignore[attr-defined]
                bytes_count = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
                result = {"source": source, "destination": destination, "type": "file", "bytes": bytes_count}
            else:
                self.server.directories.discard(source.rstrip("/"))  # type: ignore[attr-defined]
                self.server.directories.add(destination.rstrip("/"))  # type: ignore[attr-defined]
                result = {"source": source, "destination": destination, "type": "directory", "bytes": -1}
        elif method == "fs.delete":
            self.server.files.pop(params["path"], None)  # type: ignore[attr-defined]
            self.server.directories.discard(params["path"].rstrip("/"))  # type: ignore[attr-defined]
            self.server.editor_filesystem_deleted.add(params["path"].rstrip("/"))  # type: ignore[attr-defined]
            result = {"path": params["path"], "deleted": True}
        elif method == "resource.files":
            raw_extensions = params.get("extensions", params.get("extension"))
            if isinstance(raw_extensions, str):
                extensions = [raw_extensions]
            elif isinstance(raw_extensions, list):
                extensions = [str(item) for item in raw_extensions]
            else:
                extensions = None
            result = _fake_resource_files(
                self.server.files,  # type: ignore[attr-defined]
                self.server.resources,  # type: ignore[attr-defined]
                self.server.resource_dependencies,  # type: ignore[attr-defined]
                path=str(params.get("path", "res://")),
                name=str(params.get("name", "")),
                name_contains=str(params.get("name_contains", "")),
                resource_name=str(params.get("resource_name", "")),
                class_name=str(params.get("class_name", params.get("class", params.get("type", params.get("type_hint", ""))))),
                extensions=extensions,
                include_dependencies=bool(params.get("include_dependencies", True)),
                include_properties=bool(params.get("include_properties", False)),
                max_results=int(params.get("max_results", 200)),
            )
        elif method == "resource.file.describe":
            result = _fake_resource_file_description(
                str(params["path"]),
                self.server.files,  # type: ignore[attr-defined]
                self.server.resources,  # type: ignore[attr-defined]
                self.server.resource_dependencies,  # type: ignore[attr-defined]
                include_dependencies=bool(params.get("include_dependencies", True)),
                include_properties=bool(params.get("include_properties", True)),
                include_resources=bool(params.get("include_resources", True)),
                include_source=bool(params.get("include_source", False)),
            )
        elif method == "resource.save":
            raw_properties = dict(params.get("properties", {}))
            readback_properties = _fake_resource_readback_properties(raw_properties)
            self.server.resources[params["path"]] = {**params, "properties": readback_properties}  # type: ignore[attr-defined]
            self.server.resource_dependencies[params["path"]] = _fake_resource_dependency_paths(raw_properties)  # type: ignore[attr-defined]
            self.server.editor_filesystem_deleted.discard(params["path"])  # type: ignore[attr-defined]
            self.server.files[params["path"]] = "[resource]\n"  # type: ignore[attr-defined]
            existing_paths = set(self.server.files.keys()) | set(self.server.resources.keys())  # type: ignore[attr-defined]
            result = {
                "path": params["path"],
                "class": params["class"],
                "resource_name": readback_properties.get("resource_name", ""),
                "properties": readback_properties,
                "dependency_state": _fake_dependency_state(
                    params["path"],
                    self.server.resource_dependencies[params["path"]],  # type: ignore[attr-defined]
                    existing_paths,
                ),
            }
        elif method == "resource.set_properties":
            resource = self.server.resources.setdefault(  # type: ignore[attr-defined]
                params["path"],
                {"path": params["path"], "class": "Resource", "properties": {}},
            )
            properties = resource.setdefault("properties", {})
            raw_properties = dict(params["properties"])
            readback_properties = _fake_resource_readback_properties(raw_properties)
            previous = {key: properties.get(key) for key in readback_properties}
            properties.update(readback_properties)
            dependencies = set(self.server.resource_dependencies.get(params["path"], []))  # type: ignore[attr-defined]
            dependencies.update(_fake_resource_dependency_paths(raw_properties))
            self.server.resource_dependencies[params["path"]] = sorted(dependencies)  # type: ignore[attr-defined]
            if params.get("save", True):
                self.server.files[params["path"]] = "[resource]\n"  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted.discard(params["path"])  # type: ignore[attr-defined]
            existing_paths = set(self.server.files.keys()) | set(self.server.resources.keys())  # type: ignore[attr-defined]
            result = {
                "path": params["path"],
                "class": resource.get("class", "Resource"),
                "resource_name": properties.get("resource_name", ""),
                "previous": previous,
                "properties": readback_properties,
                "saved": params.get("save", True),
            }
            if params.get("save", True):
                result["dependency_state"] = _fake_dependency_state(
                    params["path"],
                    self.server.resource_dependencies[params["path"]],  # type: ignore[attr-defined]
                    existing_paths,
                )
        elif method == "resource.duplicate":
            source = self.server.resources.get(params["source"], {"class": "Resource", "properties": {}})  # type: ignore[attr-defined]
            source_properties = dict(source.get("properties", {}))
            raw_properties = dict(params.get("properties", {}))
            readback_properties = _fake_resource_readback_properties(raw_properties)
            previous = {key: source_properties.get(key) for key in readback_properties}
            destination_properties = {**source_properties, **readback_properties}
            self.server.resources[params["destination"]] = {  # type: ignore[attr-defined]
                "path": params["destination"],
                "class": source.get("class", "Resource"),
                "properties": destination_properties,
            }
            dependencies = set(self.server.resource_dependencies.get(params["source"], []))  # type: ignore[attr-defined]
            dependencies.update(_fake_resource_dependency_paths(raw_properties))
            self.server.resource_dependencies[params["destination"]] = sorted(dependencies)  # type: ignore[attr-defined]
            self.server.files[params["destination"]] = "[resource]\n"  # type: ignore[attr-defined]
            self.server.directories.update(_fake_res_parent_dirs(params["destination"]))  # type: ignore[attr-defined]
            self.server.editor_filesystem_deleted.discard(params["destination"])  # type: ignore[attr-defined]
            existing_paths = set(self.server.files.keys()) | set(self.server.resources.keys())  # type: ignore[attr-defined]
            result = {
                "path": params["destination"],
                "source_path": params["source"],
                "destination": params["destination"],
                "class": source.get("class", "Resource"),
                "resource_name": destination_properties.get("resource_name", ""),
                "source": {
                    "path": params["source"],
                    "class": source.get("class", "Resource"),
                    "resource_name": source_properties.get("resource_name", ""),
                },
                "previous": previous,
                "properties": readback_properties,
                "deep": params.get("deep", True),
                "saved": True,
                "dependency_state": _fake_dependency_state(
                    params["destination"],
                    self.server.resource_dependencies[params["destination"]],  # type: ignore[attr-defined]
                    existing_paths,
                ),
            }
        elif method == "resource.inspect":
            resource = self.server.resources.get(params["path"], {})  # type: ignore[attr-defined]
            import_metadata = self.server.import_metadata.get(params["path"], {})  # type: ignore[attr-defined]
            path_exists = (
                params["path"] in self.server.files  # type: ignore[attr-defined]
                or params["path"] in self.server.resources  # type: ignore[attr-defined]
                or bool(import_metadata.get("resource_exists"))
            )
            class_name = resource.get("class", "")
            if not class_name and path_exists:
                if str(params["path"]).endswith((".tscn", ".scn")):
                    class_name = "PackedScene"
                elif str(params["path"]).endswith(".gd"):
                    class_name = "GDScript"
                else:
                    class_name = import_metadata.get("resource_type", "Resource")
            result = {
                "path": params["path"],
                "exists": path_exists,
                "class": class_name,
                "resource_name": resource.get("properties", {}).get("resource_name", ""),
            }
            if params.get("include_properties"):
                result["properties"] = resource.get("properties", {})
        elif method == "resource.class.describe":
            result = _fake_resource_class_describe(
                str(params.get("class", "Resource")),
                include_values=bool(params.get("include_values", True)),
                storage_only=bool(params.get("storage_only", False)),
                properties=[str(item) for item in params.get("properties", [])],
                name_contains=str(params.get("name_contains", "")),
            )
        elif method == "resource.classes":
            result = _fake_resource_classes(
                base_class=str(params.get("base_class", "Resource")),
                name_contains=str(params.get("name_contains", "")),
                include_abstract=bool(params.get("include_abstract", False)),
                include_property_counts=bool(params.get("include_property_counts", True)),
                max_results=int(params.get("max_results", 200)),
            )
        elif method == "node.classes":
            result = _fake_node_classes(
                base_class=str(params.get("base_class", "Node")),
                name_contains=str(params.get("name_contains", "")),
                include_abstract=bool(params.get("include_abstract", False)),
                include_property_counts=bool(params.get("include_property_counts", True)),
                max_results=int(params.get("max_results", 200)),
            )
        elif method == "node.class.describe":
            result = _fake_node_class_describe(
                str(params.get("class", "Node")),
                include_values=bool(params.get("include_values", True)),
                storage_only=bool(params.get("storage_only", False)),
                properties=[str(item) for item in params.get("properties", [])],
                name_contains=str(params.get("name_contains", "")),
                include_methods=bool(params.get("include_methods", True)),
                include_signals=bool(params.get("include_signals", True)),
                methods=[str(item) for item in params.get("methods", [])],
                signals=[str(item) for item in params.get("signals", [])],
                method_contains=str(params.get("method_contains", "")),
                signal_contains=str(params.get("signal_contains", "")),
                max_methods=int(params.get("max_methods", 200)),
                max_signals=int(params.get("max_signals", 200)),
            )
        elif method == "resource.dependencies":
            raw_dependencies = self.server.resource_dependencies.get(params["path"], [])  # type: ignore[attr-defined]
            existing_paths = set(self.server.files.keys()) | set(self.server.resources.keys())  # type: ignore[attr-defined]
            dependencies = [_fake_dependency_summary(str(raw), existing_paths) for raw in raw_dependencies]
            missing = [dependency for dependency in dependencies if dependency["checked"] and not dependency["exists"]]
            path_exists = params["path"] in existing_paths
            result = {
                "path": params["path"],
                "global_path": f"/fake/project/{params['path'].removeprefix('res://')}",
                "exists": path_exists,
                "file_exists": path_exists,
                "resource_exists": path_exists,
                "ok": path_exists and not missing,
                "dependencies": dependencies,
                "dependency_count": len(dependencies),
                "missing": missing,
                "missing_count": len(missing),
            }
        elif method == "resource.references":
            raw_extensions = params.get("extensions", params.get("extension"))
            if isinstance(raw_extensions, str):
                extensions = [raw_extensions]
            elif isinstance(raw_extensions, list):
                extensions = [str(item) for item in raw_extensions]
            else:
                extensions = None
            result = _fake_resource_references(
                self.server.files,  # type: ignore[attr-defined]
                self.server.resources,  # type: ignore[attr-defined]
                self.server.resource_dependencies,  # type: ignore[attr-defined]
                target_path=str(params.get("path", params.get("target_path", params.get("target", "")))),
                target_uid=str(params.get("uid", "")),
                search_path=str(params.get("search_path", "res://")),
                dependency_type=str(params.get("dependency_type", params.get("type", ""))),
                resource_type=str(params.get("resource_type", "")),
                exists=params.get("exists"),
                extensions=extensions,
                max_results=int(params.get("max_results", 200)),
            )
        elif method == "resource.move":
            source = str(params["source"])
            destination = str(params["destination"])
            raw_extensions = params.get("extensions", params.get("extension"))
            if isinstance(raw_extensions, str):
                extensions = [raw_extensions]
            elif isinstance(raw_extensions, list):
                extensions = [str(item) for item in raw_extensions]
            else:
                extensions = ["tscn", "tres"]
            dry_run = bool(params.get("dry_run", False))
            update_references = bool(params.get("update_references", True))
            max_reference_files = int(params.get("max_reference_files", params.get("max_results", 200)))
            references_before: dict[str, Any] = {}
            references_after: dict[str, Any] = {}
            remaining_source_references: dict[str, Any] = {}
            reference_updates: list[dict[str, Any]] = []
            unpatched_references: list[dict[str, Any]] = []
            total_replacements = 0
            if update_references:
                references_before = _fake_resource_references(
                    self.server.files,  # type: ignore[attr-defined]
                    self.server.resources,  # type: ignore[attr-defined]
                    self.server.resource_dependencies,  # type: ignore[attr-defined]
                    target_path=source,
                    search_path=str(params.get("search_path", "res://")),
                    extensions=extensions,
                    max_results=max_reference_files,
                )
                for reference in references_before.get("references", []):
                    reference_path = str(reference.get("path", ""))
                    value = self.server.files.get(reference_path, "")  # type: ignore[attr-defined]
                    if isinstance(value, bytes):
                        value = value.decode("utf-8", errors="replace")
                    replacement = _fake_replace_text(
                        str(value),
                        source,
                        destination,
                        case_sensitive=True,
                        max_preview=int(params.get("max_preview", 20)),
                    )
                    match_count = int(replacement["match_count"])
                    if match_count <= 0:
                        unpatched = dict(reference)
                        unpatched["reason"] = "path_text_not_found"
                        unpatched_references.append(unpatched)
                        continue
                    total_replacements += match_count
                    write_path = destination if reference_path == source else reference_path
                    before_bytes = len(str(value).encode("utf-8"))
                    after_text = str(replacement["text"])
                    after_bytes = len(after_text.encode("utf-8"))
                    change = {
                        "path": reference_path,
                        "write_path": write_path,
                        "changed": after_text != str(value),
                        "match_count": match_count,
                        "replacements": match_count,
                        "bytes_before": before_bytes,
                        "bytes_after": after_bytes,
                        "file_before": _fake_file_summary(reference_path, self.server.files),  # type: ignore[attr-defined]
                        "file_after": _fake_file_summary(write_path, self.server.files, exists=True, bytes_count=after_bytes),  # type: ignore[attr-defined]
                        "dependency": reference.get("dependency", {}),
                        "edits": replacement["edits"],
                    }
                    if params.get("include_text", False):
                        change["text"] = after_text
                    reference_updates.append({**change, "_text": after_text})
            source_before = _fake_file_summary(source, self.server.files)  # type: ignore[attr-defined]
            destination_before = _fake_file_summary(destination, self.server.files)  # type: ignore[attr-defined]
            destination_existed = bool(destination_before["exists"])
            destination_after = _fake_file_summary(
                destination,
                self.server.files,  # type: ignore[attr-defined]
                exists=True,
                bytes_count=int(source_before["bytes"]),
                modified_time=0 if dry_run else 100,
            )
            if not dry_run:
                value = self.server.files.pop(source)  # type: ignore[attr-defined]
                self.server.files[destination] = value  # type: ignore[attr-defined]
                self.server.directories.update(_fake_res_parent_dirs(destination))  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted.add(source.rstrip("/"))  # type: ignore[attr-defined]
                self.server.editor_filesystem_deleted.discard(destination.rstrip("/"))  # type: ignore[attr-defined]
                if source in self.server.resources:  # type: ignore[attr-defined]
                    resource = dict(self.server.resources.pop(source))  # type: ignore[attr-defined]
                    resource["path"] = destination
                    self.server.resources[destination] = resource  # type: ignore[attr-defined]
                if source in self.server.resource_dependencies:  # type: ignore[attr-defined]
                    self.server.resource_dependencies[destination] = self.server.resource_dependencies.pop(source)  # type: ignore[attr-defined]
                for change in reference_updates:
                    write_path = str(change.get("write_path", change.get("path", "")))
                    self.server.files[write_path] = str(change.get("_text", ""))  # type: ignore[attr-defined]
                    self.server.resource_dependencies[write_path] = [  # type: ignore[attr-defined]
                        str(raw).replace(source, destination)
                        for raw in self.server.resource_dependencies.get(write_path, [])  # type: ignore[attr-defined]
                    ]
                    change["file_after"] = _fake_file_summary(write_path, self.server.files)  # type: ignore[attr-defined]
                references_after = _fake_resource_references(
                    self.server.files,  # type: ignore[attr-defined]
                    self.server.resources,  # type: ignore[attr-defined]
                    self.server.resource_dependencies,  # type: ignore[attr-defined]
                    target_path=destination,
                    search_path=str(params.get("search_path", "res://")),
                    extensions=extensions,
                    max_results=max_reference_files,
                )
                remaining_source_references = _fake_resource_references(
                    self.server.files,  # type: ignore[attr-defined]
                    self.server.resources,  # type: ignore[attr-defined]
                    self.server.resource_dependencies,  # type: ignore[attr-defined]
                    target_path=source,
                    search_path=str(params.get("search_path", "res://")),
                    extensions=extensions,
                    max_results=max_reference_files,
                )
                destination_after = _fake_file_summary(destination, self.server.files)  # type: ignore[attr-defined]
            result = {
                "source": source,
                "destination": destination,
                "type": "file",
                "dry_run": dry_run,
                "moved": not dry_run,
                "update_references": update_references,
                "search_path": str(params.get("search_path", "res://")),
                "recursive": bool(params.get("recursive", True)),
                "include_hidden": bool(params.get("include_hidden", False)),
                "extensions": sorted(item.removeprefix(".").lower() for item in extensions),
                "overwrite": bool(params.get("overwrite", True)),
                "would_overwrite": destination_existed,
                "source_before": source_before,
                "destination_before": destination_before,
                "destination_after": destination_after,
                "bytes": destination_after["bytes"],
                "references_before": references_before,
                "references_after": references_after,
                "remaining_source_references": remaining_source_references,
                "reference_updates": [{key: value for key, value in change.items() if key != "_text"} for change in reference_updates],
                "changed_reference_files": len(reference_updates),
                "reference_replacements": total_replacements,
                "unpatched_references": unpatched_references,
                "unpatched_reference_count": len(unpatched_references),
                "max_reference_files": max_reference_files,
                "max_replacements_per_file": int(params.get("max_replacements_per_file", 100)),
                "max_total_replacements": int(params.get("max_total_replacements", 500)),
            }
        elif method == "resource.imports":
            raw_extensions = params.get("extensions", params.get("extension"))
            if isinstance(raw_extensions, str):
                extensions = [raw_extensions]
            elif isinstance(raw_extensions, list):
                extensions = [str(item) for item in raw_extensions]
            else:
                extensions = None
            result = _fake_resource_imports(
                self.server.files,  # type: ignore[attr-defined]
                self.server.import_metadata,  # type: ignore[attr-defined]
                path=str(params.get("path", "res://")),
                name=str(params.get("name", "")),
                name_contains=str(params.get("name_contains", "")),
                importer=str(params.get("importer", "")),
                resource_type=str(params.get("resource_type", params.get("type", ""))),
                extensions=extensions,
                generated_files_ready=params.get("generated_files_ready"),
                imported=params.get("imported"),
                ok=params.get("ok"),
                include_missing_metadata=bool(params.get("include_missing_metadata", True)),
                max_results=int(params.get("max_results", 200)),
            )
        elif method == "resource.import_metadata":
            result = _fake_import_metadata_summary(
                params["path"],
                self.server.files,  # type: ignore[attr-defined]
                self.server.import_metadata,  # type: ignore[attr-defined]
            )
        elif method == "resource.reimport":
            paths = params.get("paths") or [params["path"]]
            source_files = [_fake_file_summary(path, self.server.files) for path in paths]  # type: ignore[attr-defined]
            import_files = [
                _fake_file_summary(f"{path}.import", self.server.files, exists=path in self.server.import_metadata)  # type: ignore[attr-defined]
                for path in paths
            ]
            force_reimport_paths = [path for path in paths if path in self.server.import_metadata]  # type: ignore[attr-defined]
            for path in paths:
                if str(path).endswith(".png"):
                    dest_path = "res://.godot/imported/generated_pixel.png-fake.ctex"
                    source_state = _fake_file_summary(path, self.server.files)  # type: ignore[attr-defined]
                    import_state = _fake_file_summary(f"{path}.import", self.server.files, exists=True, bytes_count=256, modified_time=120)  # type: ignore[attr-defined]
                    generated_state = _fake_file_summary(dest_path, self.server.files, exists=True, bytes_count=128, modified_time=130)  # type: ignore[attr-defined]
                    self.server.import_metadata[path] = {  # type: ignore[attr-defined]
                        "path": path,
                        "global_path": f"/fake/project/{path.removeprefix('res://')}",
                        "source_exists": True,
                        "import_path": f"{path}.import",
                        "import_file": import_state,
                        "source_file_state": source_state,
                        "exists": True,
                        "imported": True,
                        "resource_exists": True,
                        "resource_type": "CompressedTexture2D",
                        "type": "CompressedTexture2D",
                        "importer": "texture",
                        "uid": "uid://fakegeneratedpixel",
                        "source_file": path,
                        "source_file_matches_path": True,
                        "dest_files": [dest_path],
                        "generated_files": [generated_state],
                        "generated_files_ready": True,
                        "generated_file_count": 1,
                        "missing_generated_files": [],
                        "missing_generated_file_count": 0,
                        "stale_generated_files": [],
                        "stale_generated_file_count": 0,
                        "import_file_stale": False,
                        "parse_error": 0,
                        "remap": {
                            "importer": "texture",
                            "type": "CompressedTexture2D",
                            "uid": "uid://fakegeneratedpixel",
                        },
                        "deps": {"source_file": path, "dest_files": [dest_path]},
                        "params": {"compress/mode": 0},
                        "sections": {
                            "remap": {
                                "importer": "texture",
                                "type": "CompressedTexture2D",
                                "uid": "uid://fakegeneratedpixel",
                            },
                            "deps": {"source_file": path, "dest_files": [dest_path]},
                            "params": {"compress/mode": 0},
                        },
                        "diagnostics": [],
                        "diagnostic_count": 0,
                        "error_count": 0,
                        "warning_count": 0,
                        "ok": True,
                    }
            result = {
                "paths": paths,
                "requested": True,
                "force": params.get("force", False),
                "force_reimport_paths": force_reimport_paths,
                "force_reimport_count": len(force_reimport_paths),
                "scan_required": bool(params.get("force", False)),
                "source_files": source_files,
                "import_files": import_files,
            }
        elif method == "project.get_setting":
            result = {"name": params["name"], "value": self.server.project_settings.get(params["name"])}  # type: ignore[attr-defined]
        elif method == "project.set_setting":
            self.server.project_settings[params["name"]] = params.get("value")  # type: ignore[attr-defined]
            result = {"name": params["name"], "saved": params.get("save", False)}
        elif method == "project.doctor":
            path = str(params.get("path", "res://"))
            max_results = int(params.get("max_results", 50))
            main_scene_path = str(self.server.project_settings.get("application/run/main_scene", ""))  # type: ignore[attr-defined]
            scene_files = _fake_scene_files(
                self.server.files,  # type: ignore[attr-defined]
                self.server.resource_dependencies,  # type: ignore[attr-defined]
                path=path,
                max_results=max_results,
            )
            script_classes = _fake_script_classes(
                self.server.files,  # type: ignore[attr-defined]
                path=path,
                include_anonymous=True,
                max_results=max_results,
            )
            resource_files = _fake_resource_files(
                self.server.files,  # type: ignore[attr-defined]
                self.server.resources,  # type: ignore[attr-defined]
                self.server.resource_dependencies,  # type: ignore[attr-defined]
                path=path,
                max_results=max_results,
            )
            resource_imports = _fake_resource_imports(
                self.server.files,  # type: ignore[attr-defined]
                self.server.import_metadata,  # type: ignore[attr-defined]
                path=path,
                max_results=max_results,
            )
            diagnostics: list[dict[str, Any]] = []
            if not main_scene_path:
                diagnostics.append(
                    {
                        "kind": "MAIN_SCENE_NOT_CONFIGURED",
                        "severity": "warning",
                        "message": "application/run/main_scene is not configured",
                    }
                )
            error_count = sum(1 for item in diagnostics if item.get("severity") == "error")
            warning_count = sum(1 for item in diagnostics if item.get("severity") == "warning")
            project_summary = {
                "path": path,
                "main_scene": {"path": main_scene_path, "exists": bool(main_scene_path)},
                "scene_files": scene_files,
                "script_classes": script_classes,
                "resource_files": resource_files,
                "resource_imports": resource_imports,
                "counts": {
                    "scenes": scene_files["total_matches"],
                    "scripts": script_classes["total_matches"],
                    "resources": resource_files["total_matches"],
                    "imports": resource_imports["total_matches"],
                    "diagnostics": len(diagnostics),
                    "errors": error_count,
                    "warnings": warning_count,
                },
                "diagnostics": diagnostics,
                "diagnostic_count": len(diagnostics),
                "error_count": error_count,
                "warning_count": warning_count,
                "ok": error_count == 0,
            }
            protocol = _fake_protocol_description(
                self.server,  # type: ignore[attr-defined]
                {
                    "include_methods": bool(params.get("include_protocol_methods", False)),
                    "include_domains": True,
                    "include_features": True,
                },
            )
            checks = [
                {
                    "name": "protocol_surface",
                    "status": "pass",
                    "ok": True,
                    "message": f"Protocol exposes {protocol['method_count']} RPC methods across {protocol['domain_count']} domains",
                    "evidence": {"method_count": protocol["method_count"], "domain_count": protocol["domain_count"]},
                },
                {
                    "name": "project_summary",
                    "status": "pass" if project_summary["ok"] else "fail",
                    "ok": bool(project_summary["ok"]),
                    "message": f"Project summary has {error_count} errors and {warning_count} warnings",
                    "evidence": {"error_count": error_count, "warning_count": warning_count},
                },
                {
                    "name": "main_scene",
                    "status": "pass" if main_scene_path else "warn",
                    "ok": True,
                    "message": "Main scene is configured and loadable" if main_scene_path else "Main scene is not configured",
                    "evidence": {"path": main_scene_path, "exists": bool(main_scene_path)},
                },
            ]
            fail_count = sum(1 for check in checks if check["status"] == "fail")
            warn_count = sum(1 for check in checks if check["status"] == "warn")
            result = {
                "path": path,
                "global_path": f"/fake/project/{path.removeprefix('res://')}",
                "ok": fail_count == 0,
                "ready": fail_count == 0,
                "status": "ready" if fail_count == 0 else "blocked",
                "check_count": len(checks),
                "fail_count": fail_count,
                "warning_count": warn_count,
                "checks": checks,
                "diagnostics": diagnostics,
                "diagnostic_count": len(diagnostics),
                "next_steps": ["Project is ready for editor authoring, runtime probing, trace recording, and validation."]
                if fail_count == 0
                else ["Fix project diagnostics before authoring."],
                "protocol": protocol,
                "engine": {
                    "godot": {"major": 4, "minor": 6, "patch": 2, "status": "stable", "string": "4.6.2.stable.fake"},
                    "editor": True,
                    "project_path": "/tmp/fake-godot-project/",
                    "server_port": self.server.server_port,  # type: ignore[attr-defined]
                },
                "editor_status": {"available": True},
                "project_summary": project_summary,
            }
        elif method == "project.summary":
            path = str(params.get("path", "res://"))
            max_results = int(params.get("max_results", 50))
            main_scene_path = str(self.server.project_settings.get("application/run/main_scene", ""))  # type: ignore[attr-defined]
            main_scene = {"path": main_scene_path, "exists": bool(main_scene_path)}
            autoloads = [
                {
                    "name": name.removeprefix("autoload/"),
                    "setting": name,
                    "path": str(value).removeprefix("*"),
                    "raw": value,
                    "singleton": str(value).startswith("*"),
                    "exists": True,
                    "resource_exists": True,
                }
                for name, value in self.server.project_settings.items()  # type: ignore[attr-defined]
                if name.startswith("autoload/")
            ]
            export_presets = {
                "path": "res://export_presets.cfg",
                "exists": bool(self.server.export_presets),  # type: ignore[attr-defined]
                "presets": list(self.server.export_presets),  # type: ignore[attr-defined]
                "count": len(self.server.export_presets),  # type: ignore[attr-defined]
            }
            input_actions = {
                "actions": [
                    {
                        "name": name,
                        "exists": True,
                        "pressed": float(self.server.input_action_states.get(name, 0.0)) > 0.0,  # type: ignore[attr-defined]
                        "strength": float(self.server.input_action_states.get(name, 0.0)),  # type: ignore[attr-defined]
                        "deadzone": entry["deadzone"],
                        "events": list(entry["events"]) if params.get("include_input_events", False) else [],
                        "event_count": len(entry["events"]),
                    }
                    for name, entry in self.server.input_actions.items()  # type: ignore[attr-defined]
                    if params.get("include_ui_actions", True) or not str(name).startswith("ui_")
                ],
            }
            input_actions["count"] = len(input_actions["actions"])
            scene_files = _fake_scene_files(
                self.server.files,  # type: ignore[attr-defined]
                self.server.resource_dependencies,  # type: ignore[attr-defined]
                path=path,
                max_results=max_results,
            )
            script_classes = _fake_script_classes(
                self.server.files,  # type: ignore[attr-defined]
                path=path,
                include_anonymous=True,
                max_results=max_results,
            )
            resource_files = _fake_resource_files(
                self.server.files,  # type: ignore[attr-defined]
                self.server.resources,  # type: ignore[attr-defined]
                self.server.resource_dependencies,  # type: ignore[attr-defined]
                path=path,
                max_results=max_results,
            )
            resource_imports = (
                _fake_resource_imports(
                    self.server.files,  # type: ignore[attr-defined]
                    self.server.import_metadata,  # type: ignore[attr-defined]
                    path=path,
                    max_results=max_results,
                )
                if params.get("include_imports", True)
                else {"imports": [], "count": 0, "total_matches": 0}
            )
            diagnostics: list[dict[str, Any]] = []
            if not main_scene_path:
                diagnostics.append(
                    {
                        "kind": "MAIN_SCENE_NOT_CONFIGURED",
                        "severity": "warning",
                        "message": "application/run/main_scene is not configured",
                    }
                )
            error_count = sum(1 for item in diagnostics if item.get("severity") == "error")
            warning_count = sum(1 for item in diagnostics if item.get("severity") == "warning")
            result = {
                "path": path,
                "global_path": f"/fake/project/{path.removeprefix('res://')}",
                "max_results": max_results,
                "main_scene": main_scene,
                "autoloads": {"autoloads": autoloads, "count": len(autoloads)},
                "export_presets": export_presets,
                "input_actions": input_actions,
                "scene_files": scene_files,
                "script_classes": script_classes,
                "resource_files": resource_files,
                "resource_imports": resource_imports,
                "counts": {
                    "scenes": scene_files["total_matches"],
                    "scripts": script_classes["total_matches"],
                    "resources": resource_files["total_matches"],
                    "imports": resource_imports["total_matches"],
                    "autoloads": len(autoloads),
                    "export_presets": export_presets["count"],
                    "input_actions": input_actions["count"],
                    "diagnostics": len(diagnostics),
                    "errors": error_count,
                    "warnings": warning_count,
                },
                "diagnostics": diagnostics,
                "diagnostic_count": len(diagnostics),
                "error_count": error_count,
                "warning_count": warning_count,
                "ok": error_count == 0,
            }
        elif method == "project.export_presets":
            result = {
                "path": "res://export_presets.cfg",
                "exists": bool(self.server.export_presets),  # type: ignore[attr-defined]
                "presets": list(self.server.export_presets),  # type: ignore[attr-defined]
                "count": len(self.server.export_presets),  # type: ignore[attr-defined]
            }
        elif method == "project.set_export_preset":
            presets = self.server.export_presets  # type: ignore[attr-defined]
            index = params.get("index")
            if index is None:
                for existing in presets:
                    if existing["name"] == params["name"]:
                        index = existing["index"]
                        break
            if index is None:
                index = len(presets)
            previous = next((preset for preset in presets if preset["index"] == index), None)
            preset = {
                "index": index,
                "name": params["name"],
                "platform": params["platform"],
                "runnable": params.get("runnable", True),
                "dedicated_server": params.get("dedicated_server", False),
                "custom_features": params.get("custom_features", ""),
                "export_filter": params.get("export_filter", "all_resources"),
                "include_filter": params.get("include_filter", ""),
                "exclude_filter": params.get("exclude_filter", ""),
                "export_path": params.get("export_path", ""),
                "encryption_include_filters": params.get("encryption_include_filters", ""),
                "encryption_exclude_filters": params.get("encryption_exclude_filters", ""),
                "encrypt_pck": params.get("encrypt_pck", False),
                "encrypt_directory": params.get("encrypt_directory", False),
                "script_export_mode": params.get("script_export_mode", 2),
                "options": params.get("options", {}),
                "previous": previous,
                "saved": True,
            }
            if previous is None:
                presets.append(preset)
            else:
                presets[presets.index(previous)] = preset
            result = preset
        elif method == "project.main_scene":
            path = self.server.project_settings.get("application/run/main_scene", "")  # type: ignore[attr-defined]
            result = {"path": path, "exists": bool(path)}
        elif method == "project.set_main_scene":
            self.server.project_settings["application/run/main_scene"] = params["path"]  # type: ignore[attr-defined]
            result = {"path": params["path"], "exists": True, "saved": params.get("save", False)}
        elif method == "project.autoloads":
            autoloads = [
                {
                    "name": name.removeprefix("autoload/"),
                    "setting": name,
                    "path": str(value).removeprefix("*"),
                    "raw": value,
                    "singleton": str(value).startswith("*"),
                    "exists": True,
                    "resource_exists": True,
                }
                for name, value in self.server.project_settings.items()  # type: ignore[attr-defined]
                if name.startswith("autoload/")
            ]
            result = {"autoloads": autoloads, "count": len(autoloads)}
        elif method == "project.add_autoload":
            setting = f"autoload/{params['name']}"
            value = f"{'*' if params.get('singleton', True) else ''}{params['path']}"
            previous = self.server.project_settings.get(setting)  # type: ignore[attr-defined]
            self.server.project_settings[setting] = value  # type: ignore[attr-defined]
            result = {
                "name": params["name"],
                "setting": setting,
                "path": params["path"],
                "raw": value,
                "singleton": params.get("singleton", True),
                "exists": True,
                "resource_exists": True,
                "previous": None
                if previous is None
                else {
                    "name": params["name"],
                    "setting": setting,
                    "path": str(previous).removeprefix("*"),
                    "raw": previous,
                    "singleton": str(previous).startswith("*"),
                    "exists": True,
                    "resource_exists": True,
                },
                "saved": params.get("save", False),
            }
        elif method == "project.remove_autoload":
            setting = f"autoload/{params['name']}"
            previous = self.server.project_settings.pop(setting, None)  # type: ignore[attr-defined]
            result = {
                "name": params["name"],
                "exists": False,
                "removed": previous is not None,
                "previous": None
                if previous is None
                else {
                    "name": params["name"],
                    "setting": setting,
                    "path": str(previous).removeprefix("*"),
                    "raw": previous,
                    "singleton": str(previous).startswith("*"),
                    "exists": True,
                    "resource_exists": True,
                },
                "saved": params.get("save", False) if previous is not None else False,
            }
        else:
            result = {"ok": True}
        if method not in {"trace.start", "trace.stop", "trace.events", "trace.clear"} and self.server.trace_enabled:  # type: ignore[attr-defined]
            if method == "node.click":
                self.server.trace_events.append(  # type: ignore[attr-defined]
                    {"type": "node.click", "data": {"path": "/root/Main/CounterButton", "strategy": "pressed_signal"}}
                )
            self.server.trace_events.append(  # type: ignore[attr-defined]
                {
                    "type": "rpc",
                    "data": {
                        "method": method,
                        "ok": True,
                        "duration_ms": 0,
                    },
                }
            )
        self._json({"jsonrpc": "2.0", "id": payload.get("id"), "result": result})

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FakeGodotServer(HTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), FakeGodotHandler)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.signal_watches: list[str] = []
        self.signal_events: list[dict[str, Any]] = []
        self.signal_connections: list[dict[str, Any]] = []
        self.current_scene = "res://scenes/main.tscn"
        self.files: dict[str, str | bytes] = {}
        self.directories: set[str] = {"res://", "res://assets", "res://scenes", "res://scripts"}
        self.editor_filesystem_deleted: set[str] = set()
        self.editor_filesystem_selected_path = ""
        self.resources: dict[str, dict[str, Any]] = {}
        self.resource_dependencies: dict[str, list[str]] = {}
        self.import_metadata: dict[str, dict[str, Any]] = {}
        self.export_presets: list[dict[str, Any]] = []
        self.selected_nodes: list[dict[str, Any]] = []
        self.open_scenes = ["res://scenes/main.tscn"]
        self.edited_scene_name = "Main"
        self.main_screen_name = "2D"
        self.bottom_panel_hidden = False
        self.open_scripts: list[str] = []
        self.current_script = ""
        self.playing = False
        self.playing_scene = ""
        self.project_settings = {
            "application/config/name": "Fake Godot",
            "application/run/main_scene": "res://scenes/main.tscn",
        }
        self.node_groups: dict[str, set[str]] = {}
        self.node_properties: dict[str, dict[str, Any]] = {}
        self.node_metadata: dict[str, dict[str, Any]] = {}
        self.created_nodes: set[str] = set()
        self.deleted_nodes: set[str] = set()
        self.node_summaries: dict[str, dict[str, Any]] = {}
        self.node_indices: dict[str, int] = {}
        self.undo_stack: list[dict[str, Any]] = []
        self.redo_stack: list[dict[str, Any]] = []
        self.input_actions: dict[str, dict[str, Any]] = {
            "ui_accept": {"deadzone": 0.5, "events": [{"type": "key", "key": "Enter"}]}
        }
        self.input_action_states: dict[str, float] = {}
        self.trace_enabled = False
        self.trace_events: list[dict[str, Any]] = []
        self.trace_max_events = 1000
        self.process_frames = 0
        self.physics_frames = 0
        self.runtime_counter = 0
        self.animation_states: dict[str, dict[str, Any]] = {}
        self.viewport_width = 720
        self.viewport_height = 450
        self.dialog_visible = False
        self.focused_selector = ""
        self.input_text = ""
        self.disabled_selectors: set[str] = set()
        self.hidden_selectors: set[str] = set()
        self.checked_selectors: set[str] = set()
        self.selected_options: dict[str, str] = {}
        self.range_values: dict[str, float] = {}
        self.selected_tabs: dict[str, str] = {}
        self.selected_menu_items: dict[str, str] = {}
        self.menu_items = [
            {
                "index": 0,
                "id": 10,
                "text": "Open",
                "metadata": {"action": "open"},
                "disabled": False,
                "separator": False,
                "checkable": False,
                "radio_checkable": False,
                "checked": False,
            },
            {
                "index": 1,
                "id": 20,
                "text": "Save",
                "metadata": {"action": "save"},
                "disabled": False,
                "separator": False,
                "checkable": False,
                "radio_checkable": False,
                "checked": False,
            },
            {
                "index": 2,
                "id": 30,
                "text": "Snap",
                "metadata": {"action": "snap"},
                "disabled": False,
                "separator": False,
                "checkable": True,
                "radio_checkable": False,
                "checked": False,
            },
        ]
        self.selected_items: dict[str, Any] = {}
        self.selected_tree_items: dict[str, Any] = {}

    def inspector_state(self, target: str) -> dict[str, Any]:
        return self.node_properties.setdefault(target, {"text": "Clicked 1", "visible": True, "disabled": False})

    def viewport_info(self) -> dict[str, Any]:
        return {
            "display_server": "fake",
            "window_size": {"width": self.viewport_width, "height": self.viewport_height},
            "visible_rect": {"x": 0, "y": 0, "width": self.viewport_width, "height": self.viewport_height},
            "mouse_position": {"x": 0, "y": 0},
        }

    def dialog_summary(self) -> dict[str, Any]:
        return {
            "path": "/root/Main/ConfirmDialog",
            "node": {"name": "ConfirmDialog", "path": "/root/Main/ConfirmDialog", "class": "ConfirmationDialog"},
            "title": "Confirm Action",
            "text": "Run the agent action?",
            "visible": self.dialog_visible,
            "exclusive": False,
            "ok_button": {"text": "OK", "disabled": False, "visible": True},
            "cancel_button": {"text": "Cancel", "disabled": False, "visible": True},
        }

    def animation_state(self, path: str) -> dict[str, Any]:
        if path not in self.animation_states:
            self.animation_states[path] = {
                "animations": {
                    "fade_in": {
                        "length": 1.0,
                        "loop_mode": 0,
                        "tracks": [
                            {
                                "index": 0,
                                "type": 0,
                                "path": "AnimatedLabel:modulate:a",
                                "enabled": True,
                                "key_count": 2,
                            }
                        ],
                    }
                },
                "current_animation": "",
                "assigned_animation": "fade_in",
                "is_playing": False,
                "position": 0.0,
                "speed_scale": 1.0,
                "playback_active": True,
            }
        return self.animation_states[path]

    def animation_summary(self, path: str, *, include_tracks: bool = False) -> dict[str, Any]:
        state = self.animation_state(path)
        animations = []
        for name, animation in state["animations"].items():
            entry = {
                "name": name,
                "length": animation["length"],
                "loop_mode": animation["loop_mode"],
                "track_count": len(animation["tracks"]),
            }
            if include_tracks:
                entry["tracks"] = list(animation["tracks"])
            animations.append(entry)
        current = state["current_animation"] or state["assigned_animation"]
        return {
            "node": {"name": path.rsplit("/", 1)[-1], "path": path, "class": "AnimationPlayer"},
            "animations": animations,
            "animation_count": len(animations),
            "current_animation": state["current_animation"],
            "assigned_animation": state["assigned_animation"],
            "is_playing": state["is_playing"],
            "position": state["position"],
            "length": state["animations"][current]["length"],
            "speed_scale": state["speed_scale"],
            "playback_active": state["playback_active"],
            "autoplay": "",
            "root_node": "..",
        }

    def physics_collision(self, *, position_x: float = 640.0, position_y: float = 420.0) -> dict[str, Any]:
        return {
            "position": {"$type": "Vector2", "x": position_x, "y": position_y},
            "normal": {"$type": "Vector2", "x": -1.0, "y": 0.0},
            "shape": 0,
            "collider_id": 42,
            "name": "PhysicsTarget",
            "class": "StaticBody2D",
            "path": "/root/Main/PhysicsTarget",
            "groups": ["physics_fixture"],
            "metadata": {"test_id": "physics-target"},
            "collider": {
                "name": "PhysicsTarget",
                "class": "StaticBody2D",
                "path": "/root/Main/PhysicsTarget",
                "groups": ["physics_fixture"],
            },
        }

    def physics3d_collision(
        self,
        *,
        position_x: float = 1.0,
        position_y: float = 2.0,
        position_z: float = 3.0,
    ) -> dict[str, Any]:
        return {
            "position": {"$type": "Vector3", "x": position_x, "y": position_y, "z": position_z},
            "normal": {"$type": "Vector3", "x": -1.0, "y": 0.0, "z": 0.0},
            "shape": 0,
            "collider_id": 43,
            "face_index": -1,
            "name": "PhysicsTarget3D",
            "class": "StaticBody3D",
            "path": "/root/Main/PhysicsTarget3D",
            "groups": ["physics_fixture_3d"],
            "metadata": {"test_id": "physics-target-3d"},
            "collider": {
                "name": "PhysicsTarget3D",
                "class": "StaticBody3D",
                "path": "/root/Main/PhysicsTarget3D",
                "groups": ["physics_fixture_3d"],
            },
        }

    def camera3d_ray(self, screen_x: float, screen_y: float, *, max_distance: float = 1000.0) -> dict[str, Any]:
        return {
            "camera": {
                "name": "AutomationCamera3D",
                "class": "Camera3D",
                "path": "/root/Main/AutomationCamera3D",
                "groups": [],
                "owner": "/root/Main",
                "child_count": 0,
            },
            "screen_position": {"$type": "Vector2", "x": screen_x, "y": screen_y},
            "origin": {"$type": "Vector3", "x": 0.0, "y": 0.0, "z": 10.0},
            "direction": {"$type": "Vector3", "x": 0.0, "y": 0.0, "z": -1.0},
            "to": {"$type": "Vector3", "x": 0.0, "y": 0.0, "z": 10.0 - max_distance},
            "max_distance": max_distance,
        }


class ClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = FakeGodotServer()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = GodotClient("127.0.0.1", self.server.server_port)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def test_health(self) -> None:
        self.assertTrue(self.client.health()["ok"])

    def test_protocol_describe_lists_capabilities(self) -> None:
        protocol = self.client.protocol_describe()
        self.assertEqual(protocol["server"], "godot-playwright")
        self.assertEqual(protocol["transport"]["jsonrpc"], "2.0")
        self.assertGreaterEqual(protocol["method_count"], 100)
        methods = {entry["method"]: entry for entry in protocol["methods"]}
        self.assertIn("protocol.describe", methods)
        self.assertEqual(methods["protocol.describe"]["python_helper"], "protocol_describe")
        self.assertIn("editor.filesystem.open", methods)
        self.assertIn("resource.move", methods)
        domains = {entry["name"]: entry for entry in protocol["domains"]}
        self.assertGreaterEqual(domains["resource"]["count"], 10)
        self.assertIn("resource_safe_move", protocol["features"])
        compact = self.client.protocol_describe(include_methods=False, include_domains=False, include_features=False)
        self.assertNotIn("methods", compact)
        self.assertNotIn("domains", compact)
        self.assertNotIn("features", compact)
        self.assertEqual(compact["method_count"], protocol["method_count"])

    def test_engine_expectations_poll_info(self) -> None:
        info = self.client.engine_info()
        self.assertEqual(info["godot"]["major"], 4)
        waited = self.client.wait_for_engine_info({"editor": True}, timeout=0.1, interval=0.001)
        self.assertTrue(waited["editor"])

        engine = expect_engine(self.client)
        engine.to_be_available(timeout=0.1)
        engine.to_be_editor(timeout=0.1)
        engine.to_have_godot_version(major=4, minor=6, status="stable", string_contains="4.6", timeout=0.1)
        engine.to_have_project_path("fake-godot-project", timeout=0.1)
        engine.to_have_server_port(self.server.server_port, timeout=0.1)
        engine.to_match_info({"godot": {"major": 4}, "editor": True}, timeout=0.1)
        with self.assertRaisesRegex(AssertionError, "Expected Godot version"):
            engine.to_have_godot_version(major=3, timeout=0.01, interval=0.001)

    def test_runtime_clock_waits(self) -> None:
        clock = self.client.clock()
        self.assertIn("process_frames", clock)
        process_after = self.client.wait_for_process_frames(2, timeout=0.2, interval=0.001)
        self.assertGreaterEqual(process_after["process_frames"], clock["process_frames"] + 2)
        physics_start = process_after["physics_frames"]
        physics_after = self.client.wait_for_physics_frames(1, timeout=0.2, interval=0.001)
        self.assertGreaterEqual(physics_after["physics_frames"], physics_start + 1)
        idle_after = self.client.wait_for_idle(frames=1, timeout=0.2, interval=0.001)
        self.assertGreaterEqual(idle_after["process_frames"], physics_after["process_frames"] + 1)
        timeout_after = self.client.wait_for_timeout(1)
        self.assertIn("uptime_ms", timeout_after)
        clock_calls = [method for method, _params in self.server.calls if method == "runtime.clock"]
        self.assertGreaterEqual(len(clock_calls), 5)

    def test_animation_helpers_call_rpc(self) -> None:
        player = self.client.locator("#AutomationAnimation")
        described = player.animation_describe(include_tracks=True)
        self.assertEqual(described["node"]["class"], "AnimationPlayer")
        self.assertEqual(described["animations"][0]["name"], "fade_in")
        self.assertEqual(described["animations"][0]["tracks"][0]["path"], "AnimatedLabel:modulate:a")
        matched_animation = expect(player).to_have_animation(
            "fade_in",
            length=1.0,
            track_count=1,
            track={"path": "AnimatedLabel:modulate:a", "key_count": 2},
            timeout=0.1,
        )
        self.assertEqual(matched_animation["name"], "fade_in")
        expect(player).not_to_have_animation("missing", timeout=0.1)
        with self.assertRaisesRegex(AssertionError, "Expected '#AutomationAnimation' to have animation 'missing'"):
            expect(player).to_have_animation("missing", timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "Expected '#AutomationAnimation' not to have animation 'fade_in'"):
            expect(player).not_to_have_animation("fade_in", timeout=0.01, interval=0.001)

        played = player.play_animation("fade_in")
        self.assertTrue(played["is_playing"])
        self.assertEqual(played["current_animation"], "fade_in")
        expect(player).to_be_playing_animation("fade_in", position=0.0, speed_scale=1.0, timeout=0.1)
        seeked = player.seek_animation(0.4)
        self.assertEqual(seeked["position"], 0.4)
        expect(player).to_be_playing_animation("fade_in", position=0.4, timeout=0.1)
        advanced = self.client.animation_advance("#AutomationAnimation", 0.25)
        self.assertEqual(advanced["position"], 0.65)
        paused = self.client.animation_pause("#AutomationAnimation")
        self.assertFalse(paused["is_playing"])
        expect(player).not_to_be_playing_animation("fade_in", timeout=0.1)
        stopped = player.stop_animation()
        self.assertFalse(stopped["is_playing"])
        self.assertEqual(stopped["position"], 0.0)

        methods = [method for method, _params in self.server.calls]
        self.assertIn("animation.describe", methods)
        self.assertIn("animation.play", methods)
        self.assertIn("animation.seek", methods)
        self.assertIn("animation.advance", methods)
        self.assertIn("animation.pause", methods)
        self.assertIn("animation.stop", methods)

    def test_physics2d_helpers_call_rpc(self) -> None:
        point = self.client.physics2d_point(640, 420, collision_mask=4)
        self.assertEqual(point["count"], 1)
        self.assertEqual(point["collisions"][0]["name"], "PhysicsTarget")
        empty_point = self.client.physics2d_point(10, 10)
        self.assertEqual(empty_point["count"], 0)

        ray = self.client.physics2d_ray(560, 420, 720, 420, collision_mask=4)
        self.assertTrue(ray["hit"])
        self.assertEqual(ray["collision"]["class"], "StaticBody2D")
        missed_ray = self.client.physics2d_ray(560, 360, 720, 360)
        self.assertFalse(missed_ray["hit"])

        physics = expect_physics2d(self.client)
        point_collision = physics.to_have_point_collision(
            640,
            420,
            name="PhysicsTarget",
            class_name="StaticBody2D",
            groups=["physics_fixture"],
            metadata={"test_id": "physics-target"},
            collision_mask=4,
            timeout=0.1,
        )
        self.assertEqual(point_collision["path"], "/root/Main/PhysicsTarget")
        physics.not_to_have_point_collision(10, 10, name="PhysicsTarget", timeout=0.1)
        ray_collision = physics.to_have_ray_collision(
            560,
            420,
            720,
            420,
            path="/root/Main/PhysicsTarget",
            collision_mask=4,
            timeout=0.1,
        )
        self.assertEqual(ray_collision["name"], "PhysicsTarget")
        physics.not_to_have_ray_collision(560, 360, 720, 360, name="PhysicsTarget", timeout=0.1)

        with self.assertRaisesRegex(AssertionError, "Expected 2D physics point"):
            physics.to_have_point_collision(10, 10, name="PhysicsTarget", timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "Expected 2D physics ray"):
            physics.to_have_ray_collision(560, 360, 720, 360, name="PhysicsTarget", timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "not to collide"):
            physics.not_to_have_point_collision(640, 420, name="PhysicsTarget", timeout=0.01, interval=0.001)

        methods = [method for method, _params in self.server.calls]
        self.assertIn("physics2d.point", methods)
        self.assertIn("physics2d.ray", methods)

    def test_physics3d_helpers_call_rpc(self) -> None:
        point = self.client.physics3d_point(1, 2, 3, collision_mask=8)
        self.assertEqual(point["count"], 1)
        self.assertEqual(point["collisions"][0]["name"], "PhysicsTarget3D")
        empty_point = self.client.physics3d_point(9, 2, 3)
        self.assertEqual(empty_point["count"], 0)

        ray = self.client.physics3d_ray(-4, 2, 3, 4, 2, 3, collision_mask=8)
        self.assertTrue(ray["hit"])
        self.assertEqual(ray["collision"]["class"], "StaticBody3D")
        missed_ray = self.client.physics3d_ray(-4, 4, 3, 4, 4, 3)
        self.assertFalse(missed_ray["hit"])

        physics = expect_physics3d(self.client)
        point_collision = physics.to_have_point_collision(
            1,
            2,
            3,
            name="PhysicsTarget3D",
            class_name="StaticBody3D",
            groups=["physics_fixture_3d"],
            metadata={"test_id": "physics-target-3d"},
            collision_mask=8,
            timeout=0.1,
        )
        self.assertEqual(point_collision["path"], "/root/Main/PhysicsTarget3D")
        physics.not_to_have_point_collision(9, 2, 3, name="PhysicsTarget3D", timeout=0.1)
        ray_collision = physics.to_have_ray_collision(
            -4,
            2,
            3,
            4,
            2,
            3,
            path="/root/Main/PhysicsTarget3D",
            collision_mask=8,
            timeout=0.1,
        )
        self.assertEqual(ray_collision["name"], "PhysicsTarget3D")
        physics.not_to_have_ray_collision(-4, 4, 3, 4, 4, 3, name="PhysicsTarget3D", timeout=0.1)

        with self.assertRaisesRegex(AssertionError, "Expected 3D physics point"):
            physics.to_have_point_collision(9, 2, 3, name="PhysicsTarget3D", timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "Expected 3D physics ray"):
            physics.to_have_ray_collision(-4, 4, 3, 4, 4, 3, name="PhysicsTarget3D", timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "not to collide"):
            physics.not_to_have_point_collision(1, 2, 3, name="PhysicsTarget3D", timeout=0.01, interval=0.001)

        methods = [method for method, _params in self.server.calls]
        self.assertIn("physics3d.point", methods)
        self.assertIn("physics3d.ray", methods)

    def test_camera3d_helpers_call_rpc(self) -> None:
        ray = self.client.camera3d_ray(360, 225, camera="#AutomationCamera3D", max_distance=50)
        self.assertEqual(ray["camera"]["name"], "AutomationCamera3D")
        self.assertEqual(ray["screen_position"], {"$type": "Vector2", "x": 360.0, "y": 225.0})
        self.assertEqual(ray["direction"]["z"], -1.0)
        self.assertEqual(ray["to"]["z"], -40.0)

        pick = self.client.camera3d_pick(360, 225, camera="#AutomationCamera3D", collision_mask=8)
        self.assertTrue(pick["hit"])
        self.assertEqual(pick["collision"]["name"], "PhysicsTarget3D")
        miss = self.client.camera3d_pick(360, 225, camera="#AutomationCamera3D", collision_mask=16)
        self.assertFalse(miss["hit"])

        camera = self.client.locator("#AutomationCamera3D")
        locator_ray = camera.camera3d_ray(360, 225, max_distance=25)
        self.assertEqual(locator_ray["camera"]["name"], "AutomationCamera3D")
        self.assertEqual(locator_ray["to"]["z"], -15.0)
        locator_pick = camera.pick_3d(360, 225, collision_mask=8)
        self.assertTrue(locator_pick["hit"])
        self.assertEqual(locator_pick["collision"]["name"], "PhysicsTarget3D")
        hovered = camera.hover_3d(360, 225, name="PhysicsTarget3D", collision_mask=8, timeout=0.1)
        self.assertEqual(hovered["collision"]["name"], "PhysicsTarget3D")
        method, params = self.server.calls[-1]
        self.assertEqual(method, "input.mouse")
        self.assertEqual(params["type"], "move")
        self.assertEqual(params["x"], 360)
        clicked = camera.click_3d(360, 225, name="PhysicsTarget3D", collision_mask=8, timeout=0.1)
        self.assertEqual(clicked["collision"]["name"], "PhysicsTarget3D")
        method, params = self.server.calls[-1]
        self.assertEqual(method, "input.mouse")
        self.assertEqual(params["type"], "click")
        dragged = camera.drag_3d(360, 225, 368, 225, name="PhysicsTarget3D", collision_mask=8, steps=2, timeout=0.1)
        self.assertEqual(dragged["collision"]["name"], "PhysicsTarget3D")
        drag_calls = [(method, params) for method, params in self.server.calls if method == "input.mouse"][-5:]
        self.assertEqual([params["type"] for _method, params in drag_calls], ["move", "down", "move", "move", "up"])
        self.assertEqual(drag_calls[2][1]["button_mask"], 1)
        self.assertEqual(drag_calls[-1][1]["x"], 368)
        self.assertEqual(drag_calls[-1][1]["y"], 225)

        physics = expect_physics3d(self.client)
        picked = physics.to_pick_camera_collision(
            360,
            225,
            camera="#AutomationCamera3D",
            name="PhysicsTarget3D",
            class_name="StaticBody3D",
            groups=["physics_fixture_3d"],
            metadata={"test_id": "physics-target-3d"},
            collision_mask=8,
            timeout=0.1,
        )
        self.assertEqual(picked["path"], "/root/Main/PhysicsTarget3D")
        locator_picked = expect(camera).to_pick_camera_collision(
            360,
            225,
            name="PhysicsTarget3D",
            class_name="StaticBody3D",
            groups=["physics_fixture_3d"],
            metadata={"test_id": "physics-target-3d"},
            collision_mask=8,
            timeout=0.1,
        )
        self.assertEqual(locator_picked["path"], "/root/Main/PhysicsTarget3D")
        expect(camera).not_to_pick_camera_collision(
            360,
            225,
            name="PhysicsTarget3D",
            collision_mask=16,
            timeout=0.1,
        )
        physics.not_to_pick_camera_collision(
            360,
            225,
            camera="#AutomationCamera3D",
            name="PhysicsTarget3D",
            collision_mask=16,
            timeout=0.1,
        )

        with self.assertRaisesRegex(AssertionError, "Expected 3D camera pick"):
            physics.to_pick_camera_collision(
                0,
                0,
                camera="#AutomationCamera3D",
                name="PhysicsTarget3D",
                collision_mask=8,
                timeout=0.01,
                interval=0.001,
            )
        with self.assertRaisesRegex(AssertionError, "not to collide"):
            physics.not_to_pick_camera_collision(
                360,
                225,
                camera="#AutomationCamera3D",
                name="PhysicsTarget3D",
                collision_mask=8,
                timeout=0.01,
                interval=0.001,
            )
        with self.assertRaisesRegex(AssertionError, "Expected 3D camera pick"):
            camera.click_3d(0, 0, name="PhysicsTarget3D", collision_mask=8, timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "Expected 3D camera pick"):
            camera.drag_3d(0, 0, 8, 0, name="PhysicsTarget3D", collision_mask=8, timeout=0.01, interval=0.001)

        methods = [method for method, _params in self.server.calls]
        self.assertIn("camera3d.ray", methods)
        self.assertIn("camera3d.pick", methods)
        pick_params = [params for method, params in self.server.calls if method == "camera3d.pick"]
        self.assertTrue(any(params.get("camera") == "#AutomationCamera3D" for params in pick_params))
        self.assertTrue(any(params.get("root") == "edited" for params in pick_params))

    def test_viewport_helpers(self) -> None:
        info = self.client.viewport_info()
        self.assertEqual(info["window_size"], {"width": 720, "height": 450})
        resized = self.client.set_viewport_size(900, 700)
        self.assertEqual(resized["window_size"], {"width": 900, "height": 700})
        self.assertEqual(resized["visible_rect"], {"x": 0, "y": 0, "width": 900, "height": 700})
        self.assertEqual(self.server.calls[-1], ("viewport.set_size", {"width": 900, "height": 700}))
        waited = self.client.wait_for_viewport_size(900, 700, timeout=0.1)
        self.assertEqual(waited["window_size"], {"width": 900, "height": 700})
        viewport = expect_viewport(self.client)
        viewport.to_have_size(900, 700, timeout=0.1)
        viewport.not_to_have_size(720, 450, timeout=0.1)
        viewport.to_have_display_server("fake", timeout=0.1)
        viewport.to_have_mouse_position(0, 0, timeout=0.1)
        with tempfile.TemporaryDirectory() as tmpdir:
            screenshot_path = Path(tmpdir) / "viewport.png"
            screenshot = self.client.wait_for_screenshot(
                screenshot_path,
                width=900,
                height=700,
                timeout=0.1,
            )
            self.assertEqual(screenshot["width"], 900)
            self.assertTrue(screenshot_path.is_file())
            expected = viewport.to_have_screenshot(
                screenshot_path,
                min_width=900,
                min_height=700,
                timeout=0.1,
            )
            self.assertEqual(expected["global_path"], str(screenshot_path))
            with self.assertRaisesRegex(AssertionError, "Expected viewport screenshot"):
                viewport.to_have_screenshot(
                    screenshot_path,
                    width=901,
                    timeout=0.01,
                    interval=0.001,
                )

    def test_locator_expect_property(self) -> None:
        locator = self.client.locator("#CounterButton")
        expect(locator).to_exist(timeout=0.1)
        expect(locator).to_have_property("text", "Clicked 1", timeout=0.1)

    def test_locator_count_range_expectations(self) -> None:
        buttons = self.client.locator(".button")
        self.assertEqual(buttons.count(), 2)
        self.assertEqual(buttons.wait_for_count(2, timeout=0.1), 2)
        self.assertEqual(buttons.wait_for_count(min_count=1, max_count=3, timeout=0.1), 2)
        self.assertEqual(expect(buttons).to_have_count(2, timeout=0.1), 2)
        self.assertEqual(expect(buttons).to_have_count_at_least(2, timeout=0.1), 2)
        self.assertEqual(expect(buttons).to_have_count_at_most(2, timeout=0.1), 2)
        self.assertEqual(expect(buttons).to_have_count_between(1, 3, timeout=0.1), 2)
        self.assertEqual(expect(buttons).not_to_be_empty(timeout=0.1), 2)

        missing = self.client.locator("#Missing")
        self.assertEqual(expect(missing).to_be_empty(timeout=0.1), 0)
        self.assertEqual(expect(missing).not_to_have_count(1, timeout=0.1), 0)
        with self.assertRaisesRegex(ValueError, "required"):
            buttons.wait_for_count(timeout=0.1)
        with self.assertRaisesRegex(ValueError, "not both"):
            buttons.wait_for_count(2, min_count=1, timeout=0.1)
        with self.assertRaisesRegex(ValueError, "min_count"):
            buttons.wait_for_count(min_count=3, max_count=1, timeout=0.1)
        with self.assertRaisesRegex(AssertionError, "at most 1"):
            expect(buttons).to_have_count_at_most(1, timeout=0.01, interval=0.001)

    def test_locator_collection_text_expectations(self) -> None:
        buttons = self.client.locator(".button")
        self.assertEqual(buttons.all_text_contents(), ["Clicked 1", "Next Scene"])
        self.assertEqual(buttons.text_contents(), ["Clicked 1", "Next Scene"])
        self.assertEqual(buttons.wait_for_texts(["Clicked 1", "Next Scene"], timeout=0.1), ["Clicked 1", "Next Scene"])
        self.assertEqual(
            buttons.wait_for_texts(["Clicked", "Scene"], contains=True, timeout=0.1),
            ["Clicked 1", "Next Scene"],
        )
        self.assertEqual(expect(buttons).to_have_texts(["Clicked 1", "Next Scene"], timeout=0.1), ["Clicked 1", "Next Scene"])
        self.assertEqual(expect(buttons).to_contain_texts(["Clicked", "Scene"], timeout=0.1), ["Clicked 1", "Next Scene"])
        self.assertEqual(expect(buttons).not_to_have_texts(["Clicked 2", "Next Scene"], timeout=0.1), ["Clicked 1", "Next Scene"])
        with self.assertRaisesRegex(AssertionError, "text contents to equal"):
            expect(buttons).to_have_texts(["Clicked 1"], timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "text contents not to equal"):
            expect(buttons).not_to_have_texts(["Clicked 1", "Next Scene"], timeout=0.01, interval=0.001)

    def test_locator_generic_state_expectations(self) -> None:
        locator = self.client.locator("#CounterButton")
        matched = locator.wait_for_states({"enabled": True, "focusable": True, "receives_input": True}, timeout=0.1)
        self.assertTrue(matched["actionable"])
        self.assertTrue(expect(locator).to_have_state("focusable", True, timeout=0.1)["focusable"])
        self.assertFalse(expect(locator).not_to_have_state("editable", True, timeout=0.1)["editable"])
        self.assertTrue(expect(locator).to_match_state({"enabled": True, "actionable": True}, timeout=0.1)["enabled"])
        self.assertTrue(expect(locator).not_to_match_state({"editable": True}, timeout=0.1)["enabled"])
        self.assertTrue(expect(locator).to_be_focusable(timeout=0.1)["focusable"])
        self.assertTrue(expect(locator).to_receive_input(timeout=0.1)["receives_input"])
        with self.assertRaisesRegex(ValueError, "expected"):
            locator.wait_for_states({}, timeout=0.1)
        with self.assertRaisesRegex(ValueError, "unexpected"):
            locator.wait_for_states_not({}, timeout=0.1)
        with self.assertRaisesRegex(AssertionError, "state to include"):
            expect(locator).to_match_state({"editable": True}, timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "state not to include"):
            expect(locator).not_to_match_state({"enabled": True}, timeout=0.01, interval=0.001)

    def test_locator_richer_expectations(self) -> None:
        locator = self.client.locator("#CounterButton")
        expect(locator).to_have_text("Clicked 1", timeout=0.1)
        expect(locator).not_to_have_text("Clicked 2", timeout=0.1)
        expect(locator).not_to_have_property("text", "Clicked 2", timeout=0.1)
        self.assertEqual(locator.values(["text", "visible"]), {"text": "Clicked 1", "visible": True})
        self.assertEqual(locator.get_properties("text"), {"text": "Clicked 1"})
        self.assertTrue(locator.has_method("get_meta"))
        self.assertTrue(locator.has_signal("pressed"))
        expect(locator).to_have_method("get_meta", timeout=0.1)
        expect(locator).not_to_have_method("missing_method", timeout=0.1)
        expect(locator).to_have_signal("pressed", timeout=0.1)
        expect(locator).not_to_have_signal("missing_signal", timeout=0.1)
        self.assertEqual(
            expect(locator).to_match_node(
                {"name": "CounterButton", "parent": "/root/Main", "index": 0, "child_count": 0},
                timeout=0.1,
            )["path"],
            "/root/Main/CounterButton",
        )
        self.assertEqual(expect(locator).to_have_parent("edited", timeout=0.1)["parent"], "/root/Main")
        self.assertEqual(expect(locator).to_have_index(0, timeout=0.1)["index"], 0)
        self.assertEqual(expect(locator).to_have_child_count(0, timeout=0.1)["child_count"], 0)
        self.assertEqual(expect(locator).not_to_match_node({"name": "Other"}, timeout=0.1)["name"], "CounterButton")
        self.assertEqual(expect(locator).not_to_have_parent("#GeneratedPanel", timeout=0.1)["parent"], "/root/Main")
        self.assertEqual(expect(locator).not_to_have_index(1, timeout=0.1)["index"], 0)
        self.assertEqual(expect(locator).not_to_have_child_count(1, timeout=0.1)["child_count"], 0)
        with self.assertRaisesRegex(ValueError, "expected"):
            expect(locator).to_match_node({}, timeout=0.1)
        with self.assertRaisesRegex(ValueError, "unexpected"):
            expect(locator).not_to_match_node({}, timeout=0.1)
        with self.assertRaisesRegex(GodotPlaywrightError, "Timed out waiting for node"):
            expect(locator).to_have_index(2, timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "node summary not to include"):
            expect(locator).not_to_match_node({"name": "CounterButton"}, timeout=0.01, interval=0.001)
        snapshot = locator.snapshot(max_depth=1, include_properties=True)
        self.assertEqual(snapshot["name"], "CounterButton")
        self.assertEqual(snapshot["properties"]["text"], "Clicked 1")
        self.assertEqual(locator.snapshot_texts(max_depth=1), ["Clicked 1"])
        expect(locator).to_contain_node(name="CounterButton", class_name="Button", timeout=0.1)
        expect(locator).to_contain_node(properties={"text": "Clicked 1"}, timeout=0.1)
        expect(locator).not_to_contain_node(name="MissingChild", timeout=0.1)
        expect(locator).to_contain_text("Clicked 1", timeout=0.1)
        expect(locator).not_to_contain_text("Clicked 2", timeout=0.1)
        locator.set_properties({"tooltip_text": "Batch tooltip", "disabled": False})
        self.assertEqual(
            locator.values(("tooltip_text", "disabled")),
            {"tooltip_text": "Batch tooltip", "disabled": False},
        )
        expect(locator).to_have_properties({"tooltip_text": "Batch tooltip", "disabled": False}, timeout=0.1)
        expect(locator).not_to_have_properties({"tooltip_text": "Other"}, timeout=0.1)
        all_result = self.client.locator("role=button").set_all_properties(
            {"tooltip_text": "All buttons"},
            undo=False,
        )
        self.assertEqual(all_result["count"], 2)
        expect(self.client.locator("role=button")).to_have_all_properties(
            {"tooltip_text": "All buttons"},
            timeout=0.1,
        )
        expect(self.client.locator("role=button")).not_to_have_all_properties(
            {"tooltip_text": "Other"},
            timeout=0.1,
        )
        self.assertEqual(locator.metadata("test_id"), {"test_id": "counter-button"})
        locator.set_meta("agent_tag", "counter")
        self.assertEqual(locator.get_meta("agent_tag"), "counter")
        locator.set_metadata({"generated": True, "owner": "agent"})
        expect(locator).to_have_meta("agent_tag", "counter", timeout=0.1)
        expect(locator).to_have_metadata({"generated": True, "owner": "agent"}, timeout=0.1)
        expect(locator).not_to_have_metadata({"owner": "designer"}, timeout=0.1)
        locator.remove_meta("agent_tag")
        expect(locator).not_to_have_meta("agent_tag", timeout=0.1)
        expect(locator).to_be_visible(timeout=0.1)
        self.assertEqual(locator.wait_for(state="visible", timeout=0.1)["visible_in_tree"], True)
        self.server.hidden_selectors.add("#CounterButton")
        expect(locator).not_to_be_visible(timeout=0.1)
        expect(locator).to_be_hidden(timeout=0.1)
        self.assertEqual(locator.wait_for(state="hidden", timeout=0.1)["visible_in_tree"], False)
        self.server.hidden_selectors.remove("#CounterButton")
        expect(locator).to_be_visible(timeout=0.1)
        expect(locator).to_be_enabled(timeout=0.1)
        expect(locator).not_to_be_disabled(timeout=0.1)
        expect(locator).to_be_actionable(timeout=0.1)
        expect(locator).not_to_be_editable(timeout=0.1)
        expect(locator).not_to_be_focused(timeout=0.1)
        expect(locator).to_have_count(1, timeout=0.1)
        expect(locator).not_to_have_count(2, timeout=0.1)
        self.assertTrue(locator.is_enabled())
        self.assertFalse(locator.is_editable())
        self.server.disabled_selectors.add("#CounterButton")
        expect(locator).to_be_disabled(timeout=0.1)
        expect(locator).not_to_be_enabled(timeout=0.1)
        expect(locator).not_to_be_actionable(timeout=0.1)
        self.assertFalse(locator.is_actionable())
        self.server.disabled_selectors.remove("#CounterButton")
        expect(locator).to_be_enabled(timeout=0.1)

        name_input = self.client.locator("#NameInput")
        expect(name_input).to_be_editable(timeout=0.1)
        expect(name_input).to_have_value("", timeout=0.1)
        expect(name_input).not_to_have_value("Ada", timeout=0.1)
        name_input.focus()
        expect(name_input).to_be_focused(timeout=0.1)
        name_input.fill("Ada")
        expect(name_input).to_have_value("Ada", timeout=0.1)

        checkbox = self.client.locator("#AcceptTerms")
        expect(checkbox).not_to_be_checked(timeout=0.1)
        checkbox.check(timeout=0.1)
        expect(checkbox).to_be_checked(timeout=0.1)
        set_checked_calls = [(method, params) for method, params in self.server.calls if method == "node.set_checked"]
        self.assertEqual(set_checked_calls[-1][1]["checked"], True)
        checkbox.uncheck(timeout=0.1)
        expect(checkbox).not_to_be_checked(timeout=0.1)
        set_checked_calls = [(method, params) for method, params in self.server.calls if method == "node.set_checked"]
        self.assertEqual(set_checked_calls[-1][1]["checked"], False)
        checkbox.set_checked(True, timeout=0.1)
        expect(checkbox).to_be_checked(timeout=0.1)

        theme = self.client.locator("#ThemeSelect")
        expect(theme).to_have_value("Arcade", timeout=0.1)
        selected = theme.select_option("Story", timeout=0.1)
        self.assertEqual(selected["selected"]["text"], "Story")
        expect(theme).to_have_value("Story", timeout=0.1)
        selected_by_index = theme.select_option(2, timeout=0.1)
        self.assertEqual(selected_by_index["selected"]["text"], "Simulation")
        selected_by_dict = theme.select_option({"text": "Arcade"}, timeout=0.1)
        self.assertEqual(selected_by_dict["selected"]["text"], "Arcade")
        select_calls = [(method, params) for method, params in self.server.calls if method == "node.select_option"]
        self.assertEqual(select_calls[-1][1]["option"], {"text": "Arcade"})

        volume = self.client.locator("#VolumeSlider")
        expect(volume).to_have_value(25.0, timeout=0.1)
        value_result = volume.set_value(75, timeout=0.1)
        self.assertEqual(value_result["value"], 75.0)
        expect(volume).to_have_value(75.0, timeout=0.1)
        set_value_calls = [(method, params) for method, params in self.server.calls if method == "node.set_value"]
        self.assertEqual(set_value_calls[-1][1]["value"], 75)

        tabs = self.client.locator("#ModeTabs")
        expect(tabs).to_have_value("General", timeout=0.1)
        selected_tab = tabs.select_tab("Advanced", timeout=0.1)
        self.assertEqual(selected_tab["selected"]["text"], "Advanced")
        expect(tabs).to_have_value("Advanced", timeout=0.1)
        selected_tab_by_index = tabs.select_tab(2, timeout=0.1)
        self.assertEqual(selected_tab_by_index["selected"]["text"], "Telemetry")
        selected_tab_by_dict = tabs.select_tab({"title": "General"}, timeout=0.1)
        self.assertEqual(selected_tab_by_dict["selected"]["text"], "General")
        select_tab_calls = [(method, params) for method, params in self.server.calls if method == "node.select_tab"]
        self.assertEqual(select_tab_calls[-1][1]["tab"], {"title": "General"})

        action_menu = self.client.locator("#ActionMenu")
        menu_items = action_menu.menu_items(timeout=0.1)
        self.assertEqual([item["text"] for item in menu_items], ["Open", "Save", "Snap"])
        selected_menu_item = action_menu.select_menu_item({"metadata": {"action": "save"}}, timeout=0.1)
        self.assertEqual(selected_menu_item["selected"]["text"], "Save")
        selected_check_item = action_menu.select_menu_item("Snap", checked=True, timeout=0.1)
        self.assertEqual(selected_check_item["selected"]["checked"], True)
        select_menu_calls = [(method, params) for method, params in self.server.calls if method == "node.select_menu_item"]
        self.assertEqual(select_menu_calls[-1][1]["item"], "Snap")
        self.assertEqual(select_menu_calls[-1][1]["checked"], True)

        inventory = self.client.locator("#InventoryList")
        expect(inventory).to_have_value("Potion", timeout=0.1)
        selected_item = inventory.select_item("Elixir", timeout=0.1)
        self.assertEqual(selected_item["selected"]["value"], "Elixir")
        expect(inventory).to_have_value("Elixir", timeout=0.1)
        selected_item_by_index = inventory.select_item(2, timeout=0.1)
        self.assertEqual(selected_item_by_index["selected"]["value"], "Key")
        selected_item_by_dict = inventory.select_item({"metadata": {"kind": "key"}}, timeout=0.1)
        self.assertEqual(selected_item_by_dict["selected"]["value"], "Key")
        select_item_calls = [(method, params) for method, params in self.server.calls if method == "node.select_item"]
        self.assertEqual(select_item_calls[-1][1]["item"], {"metadata": {"kind": "key"}})

        quest_tree = self.client.locator("#QuestTree")
        expect(quest_tree).to_have_value("Root", timeout=0.1)
        selected_tree_item = quest_tree.select_tree_item("Forest", timeout=0.1)
        self.assertEqual(selected_tree_item["selected"]["value"], "Forest")
        expect(quest_tree).to_have_value("Forest", timeout=0.1)
        selected_tree_item_by_path = quest_tree.select_tree_item({"path": ["Cave", "Boss"]}, timeout=0.1)
        self.assertEqual(selected_tree_item_by_path["selected"]["value"], "Boss")
        selected_tree_item_by_meta = quest_tree.select_tree_item({"metadata": {"quest": "boss"}}, timeout=0.1)
        self.assertEqual(selected_tree_item_by_meta["selected"]["value"], "Boss")
        select_tree_item_calls = [
            (method, params) for method, params in self.server.calls if method == "node.select_tree_item"
        ]
        self.assertEqual(select_tree_item_calls[-1][1]["item"], {"metadata": {"quest": "boss"}})

        runtime_value = self.client.evaluate("root.get('name') + suffix", suffix="!")
        self.assertEqual(runtime_value["expression"], "root.get('name') + suffix")
        self.assertEqual(runtime_value["variables"], {"suffix": "!"})
        self.assertEqual(runtime_value["root"], "edited")
        self.assertTrue(self.client.wait_for_function("ready", timeout=0.1))
        self.assertTrue(self.client.wait_for_function("counter >= target", target=3, timeout=0.2, interval=0.001))
        runtime_calls = [(method, params) for method, params in self.server.calls if method == "runtime.evaluate"]
        self.assertEqual(runtime_calls[-1][1]["variables"], {"target": 3})

        evaluated = locator.evaluate('node.get("text") + suffix', {"prefix": "ignored"}, suffix="!")
        self.assertEqual(evaluated["expression"], 'node.get("text") + suffix')
        self.assertEqual(evaluated["variables"], {"prefix": "ignored", "suffix": "!"})
        self.assertEqual(self.server.calls[-1][0], "node.evaluate")
        self.assertEqual(self.server.calls[-1][1]["selector"], "#CounterButton")
        self.assertTrue(locator.wait_for_function('node.get("text") == expected', expected="Clicked 1", timeout=0.1))
        self.assertEqual(locator.wait_for_expression('node.get("text")', "Clicked 1", timeout=0.1), "Clicked 1")
        expect(locator).to_match_expression('node.get("text")', "Clicked 1", timeout=0.1)
        expect(locator).to_match_expression(
            'node.get("text") == expected',
            variables={"expected": "Clicked 1"},
            timeout=0.1,
        )
        expect(locator).not_to_match_expression('node.get("text")', "Clicked 2", timeout=0.1)

        evaluated_all = self.client.locator("role=button").evaluate_all("count + offset", offset=10, limit=2)
        self.assertEqual(evaluated_all["expression"], "count + offset")
        self.assertEqual(evaluated_all["variables"], {"offset": 10})
        self.assertEqual(evaluated_all["limit"], 2)
        self.assertEqual(self.server.calls[-1][0], "node.evaluate_all")
        self.assertEqual(self.server.calls[-1][1]["selector"], "role=button")

        call_all_results = self.client.locator("role=button").call_all("get_meta", "test_id", "", limit=2)
        self.assertEqual([entry["node"]["name"] for entry in call_all_results], ["CounterButton", "NextSceneButton"])
        self.assertEqual(call_all_results[0]["value"], "counter-button")
        self.assertEqual(self.server.calls[-1][0], "node.call_all")
        self.assertEqual(self.server.calls[-1][1]["method"], "get_meta")
        self.assertEqual(self.server.calls[-1][1]["limit"], 2)
        call_all_values = self.client.locator("role=button").call_all_values("get_meta", "test_id", "", limit=1)
        self.assertEqual(call_all_values, ["counter-button"])

        missing = self.client.get_by_test_id("missing")
        self.assertIsNone(missing.wait_for(state="detached", timeout=0.1))
        expect(missing).not_to_exist(timeout=0.1)
        expect(missing).to_be_detached(timeout=0.1)
        expect(missing).not_to_be_visible(timeout=0.1)
        with self.assertRaisesRegex(ValueError, "state must be one of"):
            locator.wait_for(state="gone")

        self.assertTrue(self.client.locator("text=Clicked 1").exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], "text=Clicked 1")
        self.assertTrue(self.client.locator({"type": "Button", "text": "Clicked 1"}).exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], {"type": "Button", "text": "Clicked 1"})
        self.assertTrue(self.client.get_by_role("button", name="Clicked 1").exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], {"role": "button", "role_name": "Clicked 1"})
        self.assertTrue(self.client.get_by_role("textbox", name_contains="Nam").exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], {"role": "textbox", "name_contains": "Nam"})
        self.assertTrue(self.client.get_by_test_id("counter-button").exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], {"test_id": "counter-button"})
        self.assertTrue(self.client.get_by_test_id("counter", key="automation_id").exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], {"metadata": {"automation_id": "counter"}})

    def test_scoped_and_indexed_locators_call_rpc(self) -> None:
        main = self.client.locator("#Main")
        scoped_button = main.get_by_role("button", name="Clicked 1")
        self.assertTrue(scoped_button.exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], {"role": "button", "role_name": "Clicked 1"})
        self.assertEqual(self.server.calls[-1][1]["root"], {"selector": "#Main", "root": "edited"})

        scoped_title = main.get_by_text("Godot Playwright")
        self.assertTrue(scoped_title.exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], {"text": "Godot Playwright"})
        self.assertEqual(self.server.calls[-1][1]["root"], {"selector": "#Main", "root": "edited"})

        scoped_name = main.get_by_placeholder("Nam", exact=False)
        self.assertTrue(scoped_name.exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], {"placeholder_contains": "Nam"})

        scoped_test_id = main.get_by_test_id("counter-button")
        self.assertTrue(scoped_test_id.exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], {"test_id": "counter-button"})
        self.assertEqual(self.server.calls[-1][1]["root"], {"selector": "#Main", "root": "edited"})

        role_and_test_id = main.locator("role=button").and_(main.get_by_test_id("counter-button"))
        self.assertTrue(role_and_test_id.exists())
        self.assertEqual(
            self.server.calls[-1][1]["selector"],
            {"all": ["role=button", {"test_id": "counter-button"}]},
        )
        self.assertEqual(self.server.calls[-1][1]["root"], {"selector": "#Main", "root": "edited"})

        text_or_test_id = main.get_by_text("Clicked 1").or_(main.get_by_test_id("next-scene"))
        self.assertTrue(text_or_test_id.exists())
        self.assertEqual(
            self.server.calls[-1][1]["selector"],
            {"any": [{"text": "Clicked 1"}, {"test_id": "next-scene"}]},
        )
        self.assertEqual(self.server.calls[-1][1]["root"], {"selector": "#Main", "root": "edited"})

        filtered = main.locator("role=button").filter(
            has_text="Clicked",
            has_not_text="Next",
            has=main.get_by_test_id("counter-button"),
            has_not={"test_id": "missing"},
        )
        self.assertTrue(filtered.exists())
        self.assertEqual(
            self.server.calls[-1][1]["selector"],
            {
                "base": "role=button",
                "has_text": "Clicked",
                "has_not_text": "Next",
                "has": {"test_id": "counter-button"},
                "has_not": {"test_id": "missing"},
            },
        )
        self.assertEqual(self.server.calls[-1][1]["root"], {"selector": "#Main", "root": "edited"})

        buttons = self.client.locator(".button")
        self.assertEqual(buttons.count(), 2)
        second = buttons.nth(1, timeout=0.1)
        second.click(timeout=0.1)
        self.assertEqual(self.server.calls[-1][0], "node.click")
        self.assertEqual(self.server.calls[-1][1]["selector"], {"path": "/root/Main/NextSceneButton"})
        self.assertEqual([locator.selector for locator in buttons.all()], [
            {"path": "/root/Main/CounterButton"},
            {"path": "/root/Main/NextSceneButton"},
        ])

    def test_locator_click_uses_node_click_rpc(self) -> None:
        self.client.locator("#CounterButton").click()
        self.assertEqual(self.server.calls[-1][0], "node.click")

    def test_locator_dialog_helpers_call_rpc(self) -> None:
        show_button = self.client.locator("#ShowConfirmButton")
        dialog = self.client.locator("#ConfirmDialog")
        show_button.click()
        self.assertTrue(dialog.is_visible())
        summary = dialog.dialog()
        self.assertEqual(summary["title"], "Confirm Action")
        self.assertEqual(summary["text"], "Run the agent action?")
        accepted = dialog.accept_dialog(timeout=0.1)
        self.assertFalse(accepted["visible"])
        self.server.dialog_visible = True
        dismissed = dialog.dismiss_dialog(timeout=0.1)
        self.assertFalse(dismissed["visible"])
        methods = [method for method, _params in self.server.calls]
        self.assertIn("node.dialog", methods)
        self.assertIn("node.accept_dialog", methods)
        self.assertIn("node.dismiss_dialog", methods)

    def test_locator_wait_for_signal_wraps_action(self) -> None:
        event = self.client.locator("#CounterButton").wait_for_signal(
            "pressed",
            timeout=0.2,
            action=lambda: self.client.locator("#CounterButton").click(),
        )
        self.assertEqual(event["signal"], "pressed")
        methods = [method for method, _params in self.server.calls]
        self.assertIn("signal.watch", methods)
        self.assertIn("signal.unwatch", methods)

    def test_client_signal_wait_helpers_watch_and_filter_events(self) -> None:
        event = self.client.wait_for_signal(
            "#CounterButton",
            "pressed",
            timeout=0.2,
            action=lambda: self.client.locator("#CounterButton").click(),
        )
        self.assertEqual(event["signal"], "pressed")
        self.assertEqual(event["path"], "/root/Main/CounterButton")

        watch = self.client.signal_watch("#CounterButton", "pressed")
        self.client.locator("#CounterButton").click()
        matched = self.client.wait_for_signal_event(
            watch_id=watch["watch_id"],
            signal="pressed",
            path="#CounterButton",
            predicate=lambda signal_event: signal_event["path"].endswith("CounterButton"),
            timeout=0.2,
        )
        self.assertEqual(matched["watch_id"], watch["watch_id"])
        self.assertEqual(self.client.signal_events(watch_id=watch["watch_id"]), [])
        self.client.signal_unwatch(watch["watch_id"])

        methods = [method for method, _params in self.server.calls]
        self.assertIn("signal.events", methods)
        self.assertIn("signal.clear", methods)

    def test_signal_expectations_watch_and_count_events(self) -> None:
        temporary = expect_signal(self.client, "#CounterButton", "pressed")
        event = temporary.to_have_event(
            action=lambda: self.client.locator("#CounterButton").click(),
            path="#CounterButton",
            fields={"args": []},
            timeout=0.2,
        )
        self.assertEqual(event["signal"], "pressed")
        self.assertIsNone(temporary.watch_id)

        signal_expect = expect_signal(self.client, "#CounterButton", "pressed").watch()
        self.client.locator("#CounterButton").click()
        self.client.locator("#CounterButton").click()
        self.assertEqual(self.client.signal_count(watch_id=signal_expect.watch_id, signal="pressed"), 2)
        events = signal_expect.to_have_event_count(2, timeout=0.1)
        self.assertEqual(len(events), 2)
        matched = signal_expect.to_have_event(
            path="#CounterButton",
            fields={"signal": "pressed", "args": []},
            predicate=lambda signal_event: signal_event["path"].endswith("CounterButton"),
            clear=False,
            timeout=0.1,
        )
        self.assertEqual(matched["watch_id"], signal_expect.watch_id)
        signal_expect.not_to_have_event("missing", timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "Expected signal events not to contain"):
            signal_expect.not_to_have_event("pressed", timeout=0.01, interval=0.001)
        signal_expect.clear()
        self.assertEqual(signal_expect.to_be_empty(timeout=0.1), [])
        signal_expect.close()
        self.assertIsNone(signal_expect.watch_id)

    def test_signal_event_sequence_expectations(self) -> None:
        watch = self.client.signal_watch("#CounterButton", "pressed")
        watch_id = str(watch["watch_id"])
        self.server.signal_events.extend(  # type: ignore[attr-defined]
            [
                {
                    "watch_id": watch_id,
                    "signal": "button_down",
                    "path": "/root/Main/CounterButton",
                    "args": [],
                },
                {
                    "watch_id": "other-watch",
                    "signal": "pressed",
                    "path": "/root/Main/OtherButton",
                    "args": [],
                },
                {
                    "watch_id": watch_id,
                    "signal": "pressed",
                    "path": "/root/Main/CounterButton",
                    "args": ["left"],
                },
            ]
        )

        matched = self.client.wait_for_signal_sequence(
            [
                "button_down",
                {"signal": "pressed", "path": "#CounterButton", "args": ["left"]},
            ],
            watch_id=watch_id,
            timeout=0.1,
        )
        self.assertEqual([event["signal"] for event in matched], ["button_down", "pressed"])

        expect_matched = expect_signal(self.client, watch_id=watch_id).to_have_event_sequence(
            [
                {"signal": "button_down", "fields": {"args": []}},
                {"signal": "pressed", "path": "#CounterButton", "fields": {"args": ["left"]}},
            ],
            timeout=0.1,
        )
        self.assertEqual(expect_matched[-1]["args"], ["left"])
        with self.assertRaisesRegex(AssertionError, "Expected signal event sequence"):
            expect_signal(self.client, watch_id=watch_id).to_have_event_sequence(
                ["pressed", "button_down"],
                timeout=0.01,
                interval=0.001,
            )

        self.client.wait_for_signal_sequence(["button_down", "pressed"], watch_id=watch_id, clear=True, timeout=0.1)
        self.assertEqual(self.client.signal_events(watch_id=watch_id), [])
        self.client.signal_unwatch(watch_id)

    def test_locator_input_helpers_call_rpc(self) -> None:
        button = self.client.locator("#CounterButton")
        name_input = self.client.locator("#NameInput")
        button.focus()
        name_input.fill("Ada")
        name_input.press("Enter")
        name_input.press("S", ctrl=True)
        name_input.type("x")
        self.client.press("Ctrl+S")
        self.client.key_down("F4", modifiers=["Shift"])
        self.client.key_up("F4", modifiers=["Shift"])
        methods = [method for method, _params in self.server.calls]
        self.assertIn("node.focus", methods)
        self.assertIn("node.fill", methods)
        self.assertIn("input.key", methods)
        self.assertIn("input.text", methods)
        key_calls = [(method, params) for method, params in self.server.calls if method == "input.key"]
        self.assertEqual(key_calls[-4][1]["key"], "Ctrl+S")
        self.assertEqual(key_calls[-2][1]["key"], "F4")
        self.assertEqual(key_calls[-2][1]["modifiers"], ["Shift"])

    def test_locator_mouse_helpers_call_input_mouse(self) -> None:
        locator = self.client.locator("#CounterButton")
        locator.hover()
        method, params = self.server.calls[-1]
        self.assertEqual(method, "input.mouse")
        self.assertEqual(params["type"], "move")
        self.assertEqual(params["x"], 60.0)
        self.assertEqual(params["y"], 45.0)

        locator.scroll(delta_y=120)
        method, params = self.server.calls[-1]
        self.assertEqual(method, "input.mouse")
        self.assertEqual(params["type"], "wheel")
        self.assertEqual(params["delta_y"], 120)

    def test_locator_geometry_helpers(self) -> None:
        locator = self.client.locator("#CounterButton")
        expected_bounds = {"rect": {"x": 10.0, "y": 20.0, "width": 100.0, "height": 50.0}}
        self.assertEqual(locator.bounds(), expected_bounds)
        self.assertEqual(locator.center(), (60.0, 45.0))
        self.assertEqual(
            locator.wait_for_bounds(x=10.0, y=20.0, width=100.0, height=50.0, timeout=0.1),
            expected_bounds,
        )
        self.assertEqual(locator.wait_for_bounds(expected_bounds, timeout=0.1), expected_bounds)
        self.assertEqual(locator.wait_for_position(10.0, 20.0, timeout=0.1), expected_bounds)
        self.assertEqual(locator.wait_for_size(100.0, 50.0, timeout=0.1), expected_bounds)
        self.assertEqual(locator.wait_for_center(60.0, 45.0, timeout=0.1), (60.0, 45.0))

        locator_expect = expect(locator)
        self.assertEqual(locator_expect.to_have_bounds(expected_bounds, timeout=0.1), expected_bounds)
        self.assertEqual(
            locator_expect.to_have_bounds(
                x=10.0,
                y=20.0,
                width=100.0,
                height=50.0,
                tolerance=0.01,
                timeout=0.1,
            ),
            expected_bounds,
        )
        self.assertEqual(locator_expect.to_have_position(10.0, 20.0, timeout=0.1), expected_bounds)
        self.assertEqual(locator_expect.to_have_size(100.0, 50.0, timeout=0.1), expected_bounds)
        self.assertEqual(locator_expect.to_have_center(60.0, 45.0, timeout=0.1), (60.0, 45.0))
        within = locator_expect.to_be_within_viewport(timeout=0.1)
        self.assertEqual(within["bounds"], expected_bounds)
        self.assertEqual(within["viewport"]["window_size"], {"width": 720, "height": 450})

        point = self.client.locator("#PointMarker")
        self.assertEqual(point.center(), (24.0, 36.0))
        self.assertEqual(expect(point).to_have_position(24.0, 36.0, timeout=0.1), {"point": {"x": 24.0, "y": 36.0}})
        with self.assertRaisesRegex(AssertionError, "Expected '#PointMarker' bounds"):
            expect(point).to_have_size(1.0, 1.0, timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "within viewport"):
            self.server.viewport_width = 50
            expect(locator).to_be_within_viewport(timeout=0.01, interval=0.001)

    def test_locator_drag_to_uses_mouse_sequence(self) -> None:
        self.client.locator("#CounterButton").drag_to("#DropTarget", steps=2)
        mouse_calls = [(method, params) for method, params in self.server.calls if method == "input.mouse"]
        self.assertEqual([params["type"] for _method, params in mouse_calls], ["move", "down", "move", "move", "up"])
        self.assertEqual(mouse_calls[2][1]["button_mask"], 1)
        self.assertEqual(mouse_calls[-1][1]["x"], 250.0)
        self.assertEqual(mouse_calls[-1][1]["y"], 45.0)

    def test_locator_touch_helpers_call_input_touch(self) -> None:
        locator = self.client.locator("#CounterButton")
        locator.tap(index=2)
        method, params = self.server.calls[-1]
        self.assertEqual(method, "input.touch")
        self.assertEqual(params["type"], "tap")
        self.assertEqual(params["index"], 2)
        self.assertEqual(params["x"], 60.0)
        self.assertEqual(params["y"], 45.0)

        locator.touch_drag_to("#DropTarget", steps=2)
        touch_calls = [(method, params) for method, params in self.server.calls if method == "input.touch"]
        self.assertEqual([params["type"] for _method, params in touch_calls[-4:]], ["down", "drag", "drag", "up"])
        self.assertEqual(touch_calls[-1][1]["x"], 250.0)
        self.assertEqual(touch_calls[-1][1]["y"], 45.0)

    def test_joypad_helpers_call_input_joypad(self) -> None:
        self.client.joypad_press("a")
        self.client.joypad_axis("left_x", 0.75, device=1)

        joypad_calls = [(method, params) for method, params in self.server.calls if method == "input.joypad"]
        self.assertEqual([params["type"] for _method, params in joypad_calls], ["down", "up", "axis"])
        self.assertEqual(joypad_calls[0][1]["button"], "a")
        self.assertTrue(joypad_calls[0][1]["pressed"])
        self.assertEqual(joypad_calls[1][1]["button"], "a")
        self.assertFalse(joypad_calls[1][1]["pressed"])
        self.assertEqual(joypad_calls[2][1]["axis"], "left_x")
        self.assertEqual(joypad_calls[2][1]["value"], 0.75)
        self.assertEqual(joypad_calls[2][1]["device"], 1)

    def test_input_map_helpers_call_rpc(self) -> None:
        key_event = self.client.input_key_event("J", shift=True)
        self.assertEqual(key_event, {"type": "key", "key": "J", "shift": True})

        configured = self.client.bind_action_key(
            "agent_jump",
            "J",
            replace=True,
            deadzone=0.2,
            shift=True,
            timeout=0.1,
        )
        self.assertTrue(configured["created"])
        self.assertTrue(configured["replaced"])
        self.assertEqual(configured["deadzone"], 0.2)
        self.assertEqual(configured["events"], [{"type": "key", "key": "J", "shift": True}])
        self.assertEqual(configured["action_state"]["event_count"], 1)
        self.assertEqual(configured["action_state"]["deadzone"], 0.2)

        self.client.bind_action_mouse_button("agent_fire", "left", timeout=0.1)
        self.client.bind_action_joypad_button("agent_confirm", "a")
        self.client.bind_action_joypad_axis("agent_move_x", "left_x", -1.0)
        replaced_events = self.client.input_action_set_events(
            "agent_fire",
            self.client.input_mouse_button_event("right"),
            timeout=0.1,
        )
        self.assertEqual(replaced_events["action_state"]["events"][0]["button"], "right")
        no_wait_config = self.client.input_action_configure(
            "agent_no_wait",
            events=[self.client.input_key_event("N")],
            wait=False,
        )
        self.assertNotIn("action_state", no_wait_config)

        actions = self.client.input_actions(include_ui=False, prefix="agent_")
        self.assertEqual(actions["count"], 5)
        self.assertEqual(self.client.input_action_describe("agent_jump")["event_count"], 1)
        matched_action = expect_project(self.client).to_have_input_action(
            "agent_jump",
            event_count=1,
            deadzone=0.2,
            timeout=0.1,
        )
        self.assertEqual(matched_action["name"], "agent_jump")
        matched_key_event = expect_project(self.client).to_have_input_action_event(
            "agent_jump",
            event_type="key",
            key="J",
            modifiers={"shift": True},
            timeout=0.1,
        )
        self.assertEqual(matched_key_event["key"], "J")
        expect_project(self.client).not_to_have_input_action_event(
            "agent_jump",
            event_type="key",
            key="K",
            timeout=0.1,
        )
        matched_mouse_event = expect_project(self.client).to_have_input_action_event(
            "agent_fire",
            event_type="mouse_button",
            button="right",
            timeout=0.1,
        )
        self.assertEqual(matched_mouse_event["button"], "right")
        matched_joy_event = expect_project(self.client).to_have_input_action_event(
            "agent_confirm",
            event_type="joypad_button",
            button="a",
            device=-1,
            timeout=0.1,
        )
        self.assertEqual(matched_joy_event["button"], "a")
        matched_axis_event = expect_project(self.client).to_have_input_action_event(
            "agent_move_x",
            event_type="joypad_axis",
            axis="left_x",
            value=-1.0,
            device=-1,
            timeout=0.1,
        )
        self.assertEqual(matched_axis_event["axis"], "left_x")
        with self.assertRaisesRegex(AssertionError, "Expected input action 'agent_jump'.*event_count=2"):
            expect_project(self.client).to_have_input_action(
                "agent_jump",
                event_count=2,
                timeout=0.01,
                interval=0.001,
            )
        with self.assertRaisesRegex(AssertionError, "Expected input action 'agent_jump' to have event.*key='K'"):
            expect_project(self.client).to_have_input_action_event(
                "agent_jump",
                event_type="key",
                key="K",
                timeout=0.01,
                interval=0.001,
            )
        with self.assertRaisesRegex(AssertionError, "Expected input action 'agent_jump' not to have event"):
            expect_project(self.client).not_to_have_input_action_event(
                "agent_jump",
                event_type="key",
                key="J",
                timeout=0.01,
                interval=0.001,
            )

        down = self.client.action_down("agent_jump", strength=0.75, timeout=0.1)
        self.assertEqual(down["action"], "agent_jump")
        self.assertTrue(down["pressed"])
        self.assertEqual(down["strength"], 0.75)
        self.assertTrue(down["pressed_state"]["pressed"])
        self.assertEqual(down["pressed_state"]["strength"], 0.75)
        pressed_state = self.client.wait_for_input_action(
            "agent_jump",
            pressed=True,
            min_strength=0.7,
            timeout=0.1,
        )
        self.assertTrue(pressed_state["pressed"])
        self.assertEqual(pressed_state["strength"], 0.75)
        expect_project(self.client).to_have_input_action_pressed(
            "agent_jump",
            min_strength=0.7,
            timeout=0.1,
        )
        expect_project(self.client).to_have_input_action_strength(
            "agent_jump",
            strength=0.75,
            timeout=0.1,
        )
        up = self.client.action_up("agent_jump", timeout=0.1)
        self.assertEqual(up["action"], "agent_jump")
        self.assertFalse(up["pressed"])
        self.assertEqual(up["strength"], 0.0)
        self.assertFalse(up["pressed_state"]["pressed"])
        self.assertEqual(up["pressed_state"]["strength"], 0.0)
        self.client.wait_for_input_action("agent_jump", pressed=False, strength=0.0, timeout=0.1)
        expect_project(self.client).not_to_have_input_action_pressed("agent_jump", timeout=0.1)
        pressed_once = self.client.press_action("agent_jump", strength=0.5, frames=1, timeout=0.1)
        self.assertTrue(pressed_once["down"]["pressed"])
        self.assertTrue(pressed_once["down"]["pressed_state"]["pressed"])
        self.assertFalse(pressed_once["up"]["pressed"])
        self.assertFalse(pressed_once["up"]["pressed_state"]["pressed"])
        expect_project(self.client).not_to_have_input_action_pressed("agent_jump", timeout=0.1)
        fire_and_forget_action = self.client.input_action("agent_jump", True, wait=False)
        self.assertNotIn("pressed_state", fire_and_forget_action)
        self.client.action_up("agent_jump", timeout=0.1)
        with self.assertRaisesRegex(AssertionError, "Expected input action 'agent_jump' to be pressed"):
            expect_project(self.client).to_have_input_action_pressed(
                "agent_jump",
                timeout=0.01,
                interval=0.001,
            )

        cleared = self.client.input_action_erase("agent_jump", events_only=True, timeout=0.1)
        self.assertEqual(cleared["event_count"], 0)
        self.assertEqual(cleared["action_state"]["event_count"], 0)
        erased = self.client.input_action_erase("agent_jump", timeout=0.1)
        self.assertTrue(erased["erased"])
        self.assertFalse(erased["action_state"]["exists"])
        self.assertFalse(self.client.input_action_describe("agent_jump")["exists"])
        expect_project(self.client).not_to_have_input_action("agent_jump", timeout=0.1)
        no_wait_erase = self.client.input_action_erase("agent_no_wait", wait=False)
        self.assertNotIn("action_state", no_wait_erase)

        methods = [method for method, _params in self.server.calls]
        self.assertIn("input.actions", methods)
        self.assertIn("input.action.describe", methods)
        self.assertIn("input.action.configure", methods)
        self.assertIn("input.action", methods)
        self.assertIn("input.action.erase", methods)

    def test_scene_navigation_helpers_call_rpc(self) -> None:
        self.server.files["res://scenes/main.tscn"] = (
            "[gd_scene format=3]\n\n"
            "[ext_resource type=\"Script\" path=\"res://scripts/main.gd\" id=\"1_main\"]\n\n"
            "[node name=\"Main\" type=\"Control\"]\n"
            "script = ExtResource(\"1_main\")\n"
            "[node name=\"CounterButton\" type=\"Button\" parent=\".\"]\n"
            "[connection signal=\"pressed\" from=\"CounterButton\" to=\".\" method=\"_on_counter_pressed\"]\n"
        )
        self.server.files["res://scripts/main.gd"] = "extends Control\n"
        self.server.resource_dependencies["res://scenes/main.tscn"] = ["res://scripts/main.gd::Script"]
        scene_files = self.client.scene_files(
            "res://scenes",
            name="main.tscn",
            root_class="Control",
            include_nodes=True,
            max_results=10,
        )
        self.assertEqual(scene_files["count"], 1)
        self.assertEqual(scene_files["scenes"][0]["path"], "res://scenes/main.tscn")
        self.assertEqual(scene_files["scenes"][0]["root_name"], "Main")
        self.assertEqual(scene_files["scenes"][0]["root_class"], "Control")
        self.assertEqual(scene_files["scenes"][0]["node_count"], 2)
        self.assertEqual(scene_files["scenes"][0]["dependency_count"], 1)
        self.assertTrue(scene_files["scenes"][0]["ok"])
        listed_scene = expect_project_scene(self.client, "res://scenes/main.tscn").to_be_listed(
            root_class="Control",
            timeout=0.1,
        )
        self.assertEqual(listed_scene["root_name"], "Main")
        self.assertEqual(
            expect_project_scene(self.client, "res://scenes/main.tscn").to_have_root(
                name="Main",
                class_name="Control",
                timeout=0.1,
            )["node_count"],
            2,
        )
        expect_project_scene(self.client, "res://scenes/main.tscn").to_have_no_missing_dependencies(timeout=0.1)
        scene_description = self.client.scene_file_describe("res://scenes/main.tscn", include_properties=True)
        self.assertEqual(scene_description["root_name"], "Main")
        self.assertEqual(scene_description["ext_resources"][0]["path"], "res://scripts/main.gd")
        self.assertEqual(scene_description["connections"][0]["method"], "_on_counter_pressed")
        self.assertEqual(scene_description["nodes"][0]["script"], "res://scripts/main.gd")
        self.assertEqual(
            expect_project_scene(self.client, "res://scenes/main.tscn").to_have_node(
                name="Main",
                class_name="Control",
                script="res://scripts/main.gd",
                timeout=0.1,
            )["path"],
            "/Main",
        )
        self.assertEqual(
            expect_project_scene(self.client, "res://scenes/main.tscn").to_have_connection(
                "pressed",
                from_node="CounterButton",
                to=".",
                method="_on_counter_pressed",
                timeout=0.1,
            )["line"],
            8,
        )
        expect_runtime_scene(self.client).to_have_path("res://scenes/main.tscn", timeout=0.1)
        expect_runtime_scene(self.client).to_have_name("Main", timeout=0.1)
        expect_runtime_scene(self.client).to_match_info({"name": "Main"}, timeout=0.1)
        scene = self.client.change_scene("res://scenes/secondary.tscn", timeout=0.1)
        self.assertEqual(scene["scene_file_path"], "res://scenes/secondary.tscn")
        self.assertEqual(self.client.current_scene()["scene_file_path"], "res://scenes/secondary.tscn")
        self.assertEqual(self.client.wait_for_scene(name="Secondary", timeout=0.1)["name"], "Secondary")
        self.assertEqual(self.client.wait_for_scene_not("res://scenes/main.tscn", timeout=0.1)["name"], "Secondary")
        runtime_scene = expect_runtime_scene(self.client)
        runtime_scene.to_have_path("res://scenes/secondary.tscn", timeout=0.1)
        runtime_scene.not_to_have_path("res://scenes/main.tscn", timeout=0.1)
        runtime_scene.to_have_name("Secondary", timeout=0.1)
        runtime_scene.not_to_have_name("Main", timeout=0.1)
        runtime_scene.to_match_info({"scene_file_path": "res://scenes/secondary.tscn", "name": "Secondary"}, timeout=0.1)
        with self.assertRaisesRegex(ValueError, "path or name"):
            self.client.wait_for_scene_not(timeout=0.1)
        with self.assertRaisesRegex(AssertionError, "Expected current scene path"):
            runtime_scene.to_have_path("res://scenes/main.tscn", timeout=0.01, interval=0.001)
        methods = [method for method, _params in self.server.calls]
        self.assertIn("scene.files", methods)
        self.assertIn("scene.file.describe", methods)
        self.assertIn("scene.change", methods)

    def test_locator_authoring_wrappers_call_rpc(self) -> None:
        panel = self.client.locator("#GeneratedPanel")
        child = panel.create_child("Label", name="ChildLabel", undo_action="Create child")
        self.assertEqual(child["path"], "/root/Main/GeneratedPanel/ChildLabel")
        self.assertEqual(child["class"], "Label")
        self.assertEqual(child["node_state"]["path"], "/root/Main/GeneratedPanel/ChildLabel")
        self.assertEqual(child["node_state"]["class"], "Label")
        created_child = self.client.locator({"path": "/root/Main/GeneratedPanel/ChildLabel"}, root="root")
        self.assertEqual(expect(created_child).to_have_parent(panel, timeout=0.1)["parent"], "/root/Main/GeneratedPanel")
        self.assertEqual(expect(created_child).to_match_node({"class": "Label"}, timeout=0.1)["class"], "Label")
        create_call = next(params for method, params in reversed(self.server.calls) if method == "node.create")
        self.assertEqual(
            create_call,
            {
                "parent": "#GeneratedPanel",
                "root": "edited",
                "class": "Label",
                "name": "ChildLabel",
                "owner_scene": True,
                "undo_action": "Create child",
            },
        )

        instance = panel.instantiate_scene("res://scenes/badge.tscn", name="BadgeFromLocator", index=1)
        self.assertEqual(instance["path"], "/root/Main/GeneratedPanel/BadgeFromLocator")
        self.assertEqual(instance["source_scene"], "res://scenes/badge.tscn")
        self.assertEqual(instance["node_state"]["index"], 1)
        instantiate_call = next(params for method, params in reversed(self.server.calls) if method == "node.instantiate_scene")
        self.assertEqual(instantiate_call["parent"], "#GeneratedPanel")
        self.assertEqual(instantiate_call["index"], 1)

        grouped = panel.add_group("agent_panel", persistent=False)
        self.assertTrue(grouped["added"])
        self.assertIn("agent_panel", grouped["groups_state"]["groups"])
        self.assertEqual(panel.groups(), ["agent_panel"])
        self.assertEqual(panel.group_info()["count"], 1)
        removed = panel.remove_group("agent_panel")
        self.assertTrue(removed["removed"])
        self.assertEqual(removed["groups_state"]["groups"], [])
        self.assertEqual(panel.groups(), [])

        child_locator = self.client.locator("#ChildLabel")
        reparented = child_locator.reparent(panel, index=0)
        self.assertEqual(reparented["new_parent"], "/root/Main/GeneratedPanel")
        self.assertEqual(reparented["node_state"]["parent"], "/root/Main/GeneratedPanel")
        reparent_call = next(params for method, params in reversed(self.server.calls) if method == "node.reparent")
        self.assertEqual(reparent_call["parent"], "#GeneratedPanel")
        moved = child_locator.move(2)
        self.assertEqual(moved["index"], 2)
        self.assertEqual(moved["node_state"]["index"], 2)
        moved_child = self.client.locator({"path": moved["path"]}, root="root")
        self.assertEqual(expect(moved_child).to_have_index(2, timeout=0.1)["index"], 2)
        duplicate = child_locator.duplicate(parent=panel, name="ChildLabelCopy", index=1, flags=15)
        self.assertEqual(duplicate["path"], "/root/Main/GeneratedPanel/ChildLabelCopy")
        self.assertEqual(duplicate["node_state"]["index"], 1)
        duplicated_child = self.client.locator({"path": duplicate["path"]}, root="root")
        self.assertEqual(expect(duplicated_child).to_have_parent(panel, timeout=0.1)["parent"], "/root/Main/GeneratedPanel")
        self.assertEqual(expect(duplicated_child).to_have_index(1, timeout=0.1)["index"], 1)
        duplicate_call = next(params for method, params in reversed(self.server.calls) if method == "node.duplicate")
        self.assertEqual(duplicate_call["parent"], "#GeneratedPanel")
        self.assertEqual(duplicate_call["flags"], 15)

        attached = child_locator.attach_script("res://scripts/generated/child_label.gd", inspect=True, reload=False)
        self.assertEqual(attached["script"]["path"], "res://scripts/generated/child_label.gd")
        self.assertEqual(attached["script_state"]["path"], "res://scripts/generated/child_label.gd")
        attach_call = next(params for method, params in reversed(self.server.calls) if method == "node.attach_script")
        self.assertFalse(attach_call["reload"])
        expect(child_locator).to_have_script("res://scripts/generated/child_label.gd", timeout=0.1)
        detached = child_locator.detach_script(inspect=True)
        self.assertIsNone(detached["script"])
        self.assertEqual(detached["script_state"]["state"], "detached")
        detach_call = next(params for method, params in reversed(self.server.calls) if method == "node.detach_script")
        self.assertTrue(detach_call["inspect"])
        deleted = child_locator.delete()
        self.assertEqual(deleted["deleted"], "/root/Main/ChildLabel")
        self.assertEqual(deleted["node_state"]["state"], "detached")

    def test_filesystem_helpers_call_rpc(self) -> None:
        created_directory = self.client.fs_mkdir("res://scripts/generated")
        self.assertEqual(created_directory["directory"]["type"], "directory")
        self.assertTrue(created_directory["editor_filesystem"]["is_directory"])
        directory = self.client.wait_for_directory("res://scripts/generated", timeout=0.1)
        self.assertEqual(directory["type"], "directory")
        expect_filesystem(self.client, "res://scripts/generated").to_be_directory(timeout=0.1)
        written_text = self.client.fs_write_text("res://scripts/generated/agent_tool.gd", "extends Node\n")
        self.assertEqual(written_text["file"]["type"], "file")
        self.assertEqual(written_text["text"], "extends Node\n")
        self.assertTrue(written_text["editor_filesystem"]["is_file"])
        file_state = self.client.wait_for_file("res://scripts/generated/agent_tool.gd", timeout=0.1)
        self.assertEqual(file_state["type"], "file")
        self.assertEqual(self.client.fs_read_text("res://scripts/generated/agent_tool.gd"), "extends Node\n")
        info = self.client.fs_info("res://scripts/generated/agent_tool.gd")
        self.assertEqual(info["type"], "file")
        self.assertEqual(info["extension"], "gd")
        self.assertEqual(info["bytes"], len("extends Node\n".encode("utf-8")))
        self.client.wait_for_files(["res://scripts/generated/agent_tool.gd"], timeout=0.1)
        expect_filesystem(self.client, "res://scripts/generated/agent_tool.gd").to_exist(timeout=0.1)
        expect_filesystem(self.client, "res://scripts/generated/agent_tool.gd").to_be_file(timeout=0.1)
        expect_filesystem(self.client, "res://scripts/generated/agent_tool.gd").to_have_text("extends Node", timeout=0.1)
        expect_filesystem(self.client, "res://scripts/generated/agent_tool.gd").not_to_have_text("class_name AgentTool", timeout=0.1)
        copied = self.client.fs_copy(
            "res://scripts/generated/agent_tool.gd",
            "res://scripts/generated/agent_tool_copy.gd",
            timeout=0.1,
        )
        self.assertEqual(copied["destination_state"]["type"], "file")
        self.assertEqual(copied["source_state"]["type"], "file")
        self.assertTrue(copied["editor_destination"]["is_file"])
        self.assertTrue(copied["editor_source"]["is_file"])
        self.assertEqual(self.client.fs_read_text("res://scripts/generated/agent_tool_copy.gd"), "extends Node\n")
        fire_and_forget_copy = self.client.fs_copy(
            "res://scripts/generated/agent_tool.gd",
            "res://scripts/generated/agent_tool_no_wait.gd",
            wait=False,
        )
        self.assertNotIn("destination_state", fire_and_forget_copy)
        moved = self.client.fs_move(
            "res://scripts/generated/agent_tool_copy.gd",
            "res://scripts/generated/agent_tool_moved.gd",
            timeout=0.1,
        )
        self.assertEqual(moved["source_missing"]["type"], "missing")
        self.assertEqual(moved["destination_state"]["type"], "file")
        self.assertFalse(moved["editor_source"]["exists"])
        self.assertTrue(moved["editor_destination"]["is_file"])
        self.assertEqual(self.client.fs_read_text("res://scripts/generated/agent_tool_moved.gd"), "extends Node\n")
        binary_data = b"\x89PNG\r\n\x1a\nagent-bytes"
        written_binary = self.client.fs_write_bytes("res://assets/generated_pixel.png", binary_data)
        self.assertEqual(written_binary["bytes"], len(binary_data))
        self.assertEqual(written_binary["file"]["type"], "file")
        self.assertTrue(written_binary["editor_filesystem"]["is_file"])
        self.assertEqual(self.client.fs_read_bytes("res://assets/generated_pixel.png"), binary_data)
        self.assertTrue(self.client.fs_exists("res://scripts/generated/agent_tool.gd")["exists"])
        listing = self.client.fs_list("res://scripts/generated")
        self.assertIn("agent_tool.gd", listing["files"])
        self.assertIn("agent_tool_moved.gd", listing["files"])
        found_scripts = self.client.fs_find(
            "res://scripts",
            extension="gd",
            name_contains="agent_tool",
            max_results=10,
        )
        self.assertEqual(found_scripts["count"], 3)
        self.assertEqual(
            sorted(entry["path"] for entry in found_scripts["entries"]),
            [
                "res://scripts/generated/agent_tool.gd",
                "res://scripts/generated/agent_tool_moved.gd",
                "res://scripts/generated/agent_tool_no_wait.gd",
            ],
        )
        grep_scripts = self.client.fs_grep(
            "node",
            "res://scripts",
            case_sensitive=False,
            extension="gd",
            name_contains="agent_tool",
            context_lines=1,
            max_results=5,
        )
        self.assertEqual(grep_scripts["count"], 3)
        self.assertEqual(grep_scripts["matches"][0]["line"], 1)
        self.assertEqual(grep_scripts["matches"][0]["column"], 8)
        self.assertEqual(grep_scripts["matches"][0]["text"], "extends Node")
        self.assertEqual(grep_scripts["matches"][0]["after"][0]["line"], 2)
        replaced_text = self.client.fs_replace_text(
            "res://scripts/generated/agent_tool.gd",
            "extends Node",
            "extends Control",
            timeout=0.1,
        )
        self.assertEqual(replaced_text["match_count"], 1)
        self.assertEqual(replaced_text["replacements"], 1)
        self.assertEqual(replaced_text["bytes_before"], len("extends Node\n".encode("utf-8")))
        self.assertEqual(replaced_text["text"], "extends Control\n")
        self.assertEqual(replaced_text["edits"][0]["line"], 1)
        self.assertEqual(replaced_text["edits"][0]["column"], 0)
        self.assertEqual(replaced_text["edits"][0]["before"]["text"], "extends Node")
        self.assertEqual(replaced_text["edits"][0]["after"]["text"], "extends Control")
        self.assertEqual(replaced_text["file"]["type"], "file")
        self.assertTrue(replaced_text["editor_filesystem"]["is_file"])
        self.assertEqual(self.client.fs_read_text("res://scripts/generated/agent_tool.gd"), "extends Control\n")
        dry_run_replace = self.client.fs_replace_text(
            "res://scripts/generated/agent_tool.gd",
            "extends Control",
            "extends Node",
            dry_run=True,
            timeout=0.1,
        )
        self.assertTrue(dry_run_replace["dry_run"])
        self.assertEqual(dry_run_replace["match_count"], 1)
        self.assertEqual(dry_run_replace["text"], "extends Node\n")
        self.assertEqual(self.client.fs_read_text("res://scripts/generated/agent_tool.gd"), "extends Control\n")
        bulk_preview = self.client.fs_replace_text_many(
            "extends Node",
            "extends Node2D",
            "res://scripts",
            extension="gd",
            name_contains="agent_tool",
            expected_files=2,
            expected_replacements=2,
            max_total_replacements=5,
        )
        self.assertTrue(bulk_preview["dry_run"])
        self.assertEqual(bulk_preview["changed_files"], 2)
        self.assertEqual(bulk_preview["replacements"], 2)
        self.assertEqual(
            sorted(change["path"] for change in bulk_preview["changes"]),
            [
                "res://scripts/generated/agent_tool_moved.gd",
                "res://scripts/generated/agent_tool_no_wait.gd",
            ],
        )
        self.assertEqual(self.client.fs_read_text("res://scripts/generated/agent_tool_moved.gd"), "extends Node\n")
        bulk_commit = self.client.fs_replace_text_many(
            "extends Node",
            "extends Node2D",
            "res://scripts",
            extension="gd",
            name_contains="agent_tool",
            expected_files=2,
            expected_replacements=2,
            dry_run=False,
            max_total_replacements=5,
            timeout=0.1,
        )
        self.assertFalse(bulk_commit["dry_run"])
        self.assertEqual(bulk_commit["changed_files"], 2)
        self.assertEqual(bulk_commit["replacements"], 2)
        self.assertEqual(bulk_commit["changes"][0]["file"]["type"], "file")
        self.assertTrue(bulk_commit["changes"][0]["editor_filesystem"]["is_file"])
        self.assertEqual(self.client.fs_read_text("res://scripts/generated/agent_tool_moved.gd"), "extends Node2D\n")
        self.assertEqual(self.client.fs_read_text("res://scripts/generated/agent_tool_no_wait.gd"), "extends Node2D\n")
        found_with_dirs = self.client.fs_find("res://scripts", include_dirs=True, recursive=False)
        self.assertIn("res://scripts/generated", [entry["path"] for entry in found_with_dirs["entries"]])
        deleted = self.client.fs_delete("res://scripts/generated/agent_tool.gd")
        self.assertEqual(deleted["missing"]["type"], "missing")
        self.assertFalse(deleted["editor_filesystem"]["exists"])
        self.client.wait_for_fs_path("res://scripts/generated/agent_tool.gd", state="missing", timeout=0.1)
        self.client.wait_for_editor_filesystem_missing("res://scripts/generated/agent_tool.gd", timeout=0.1)
        expect_filesystem(self.client, "res://scripts/generated/agent_tool.gd").not_to_exist(timeout=0.1)
        expect_filesystem(self.client, "res://scripts/generated/agent_tool.gd").not_to_be_indexed(timeout=0.1)
        methods = [method for method, _params in self.server.calls]
        self.assertIn("fs.write_text", methods)
        self.assertIn("fs.read_text", methods)
        self.assertIn("fs.write_bytes", methods)
        self.assertIn("fs.read_bytes", methods)
        self.assertIn("fs.exists", methods)
        self.assertIn("fs.info", methods)
        self.assertIn("fs.find", methods)
        self.assertIn("fs.grep", methods)
        self.assertIn("fs.replace_text", methods)
        self.assertIn("fs.replace_text_many", methods)
        self.assertIn("fs.copy", methods)
        self.assertIn("fs.move", methods)

    def test_resource_helpers_call_rpc(self) -> None:
        saved = self.client.resource_save(
            "res://data/agent_resource.tres",
            properties={"resource_name": "AgentResource"},
        )
        self.assertEqual(saved["resource_name"], "AgentResource")
        self.assertEqual(saved["file"]["type"], "file")
        self.assertEqual(saved["resource"]["properties"]["resource_name"], "AgentResource")
        self.assertTrue(saved["editor_filesystem"]["is_file"])
        resource_files = self.client.resource_files(
            "res://data",
            name="agent_resource.tres",
            class_name="Resource",
            resource_name="AgentResource",
            max_results=10,
        )
        self.assertEqual(resource_files["count"], 1)
        self.assertEqual(resource_files["resources"][0]["path"], "res://data/agent_resource.tres")
        self.assertEqual(resource_files["resources"][0]["class"], "Resource")
        self.assertEqual(resource_files["resources"][0]["resource_name"], "AgentResource")
        self.assertTrue(resource_files["resources"][0]["ok"])
        listed_resource = expect_resource(self.client, "res://data/agent_resource.tres").to_be_listed(
            class_name="Resource",
            resource_name="AgentResource",
            timeout=0.1,
        )
        self.assertEqual(listed_resource["name"], "agent_resource.tres")
        resource_script_path = "res://scripts/resource_logic.gd"
        text_resource_path = "res://data/text_agent_resource.tres"
        self.server.files[resource_script_path] = "extends Resource\n"
        self.server.files[text_resource_path] = (
            '[gd_resource type="Resource" script_class="AgentData" load_steps=3 format=3 uid="uid://agentdata"]\n'
            '[ext_resource type="Script" path="res://scripts/resource_logic.gd" id="1_script"]\n'
            '[sub_resource type="Gradient" id="Gradient_inline"]\n'
            'resource_name = "InlineGradient"\n'
            "\n"
            "[resource]\n"
            'resource_name = "TextAgentResource"\n'
            'script = ExtResource("1_script")\n'
            'inline = SubResource("Gradient_inline")\n'
        )
        self.server.resource_dependencies[text_resource_path] = ["uid://script123::res://scripts/resource_logic.gd::Script"]
        resource_description = self.client.resource_file_describe(text_resource_path, include_source=True)
        self.assertEqual(resource_description["root_class"], "Resource")
        self.assertEqual(resource_description["script_class"], "AgentData")
        self.assertEqual(resource_description["resource_uid"], "uid://agentdata")
        self.assertEqual(resource_description["properties"]["resource_name"], "TextAgentResource")
        self.assertEqual(resource_description["root"]["script"], resource_script_path)
        self.assertEqual(resource_description["ext_resources"][0]["path"], resource_script_path)
        self.assertEqual(resource_description["sub_resources"][0]["properties"]["resource_name"], "InlineGradient")
        self.assertIn("TextAgentResource", resource_description["source"])
        self.assertEqual(resource_description["dependencies"][0]["path"], resource_script_path)
        expect_resource(self.client, text_resource_path).to_have_file_property(
            "resource_name",
            "TextAgentResource",
            timeout=0.1,
        )
        listed_ext_resource = expect_resource(self.client, text_resource_path).to_have_file_ext_resource(
            path=resource_script_path,
            resource_type="Script",
            exists=True,
            timeout=0.1,
        )
        self.assertEqual(listed_ext_resource["id"], "1_script")
        class_list = self.client.resource_classes(name_contains="Gradient", max_results=10)
        class_names = {entry["class"] for entry in class_list["classes"]}
        self.assertIn("Gradient", class_names)
        self.assertIn("GradientTexture1D", class_names)
        self.assertFalse(class_list["truncated"])
        listed_gradient_texture = expect_resource_class(self.client, "GradientTexture1D").to_be_listed(timeout=0.1)
        self.assertEqual(listed_gradient_texture["class"], "GradientTexture1D")
        resource_schema = self.client.resource_class_describe("GradientTexture1D", properties=["gradient"], storage_only=True)
        self.assertTrue(resource_schema["is_resource"])
        self.assertEqual(resource_schema["properties"][0]["name"], "gradient")
        self.assertEqual(resource_schema["properties"][0]["hint_string"], "Gradient")
        self.assertEqual(self.client.resource_schema("Resource", properties=["resource_name"])["values"]["resource_name"], "")
        expect_resource_class(self.client, "GradientTexture1D").to_be_resource(timeout=0.1)
        gradient_property = expect_resource_class(self.client, "GradientTexture1D").to_have_property(
            "gradient",
            type_name="Object",
            storage=True,
            editor_visible=True,
            timeout=0.1,
        )
        self.assertEqual(gradient_property["hint_string"], "Gradient")
        inspected = self.client.resource_inspect(
            "res://data/agent_resource.tres",
            include_properties=True,
            properties=["resource_name"],
        )
        self.assertEqual(inspected["properties"]["resource_name"], "AgentResource")
        waited_resource = self.client.wait_for_resource(
            "res://data/agent_resource.tres",
            class_name="Resource",
            properties={"resource_name": "AgentResource"},
            timeout=0.1,
        )
        self.assertEqual(waited_resource["class"], "Resource")
        expect_resource(self.client, "res://data/agent_resource.tres").to_exist(timeout=0.1)
        expect_resource(self.client, "res://data/agent_resource.tres").to_have_class("Resource", timeout=0.1)
        expect_resource(self.client, "res://data/agent_resource.tres").to_have_property(
            "resource_name",
            "AgentResource",
            timeout=0.1,
        )
        expect_resource(self.client, "res://data/agent_resource.tres").to_have_properties(
            {"resource_name": "AgentResource"},
            timeout=0.1,
        )
        updated = self.client.resource_set_properties(
            "res://data/agent_resource.tres",
            {"resource_name": "UpdatedAgentResource"},
            timeout=0.1,
        )
        self.assertEqual(updated["previous"]["resource_name"], "AgentResource")
        self.assertEqual(updated["properties"]["resource_name"], "UpdatedAgentResource")
        self.assertEqual(updated["resource"]["properties"]["resource_name"], "UpdatedAgentResource")
        self.assertEqual(updated["file"]["type"], "file")
        self.assertTrue(updated["editor_filesystem"]["is_file"])
        expect_resource(self.client, "res://data/agent_resource.tres").to_have_property(
            "resource_name",
            "UpdatedAgentResource",
            timeout=0.1,
        )
        variant = self.client.resource_duplicate(
            "res://data/agent_resource.tres",
            "res://data/agent_resource_variant.tres",
            properties={"resource_name": "VariantAgentResource"},
            timeout=0.1,
        )
        self.assertEqual(variant["source_path"], "res://data/agent_resource.tres")
        self.assertEqual(variant["destination"], "res://data/agent_resource_variant.tres")
        self.assertEqual(variant["previous"]["resource_name"], "UpdatedAgentResource")
        self.assertEqual(variant["properties"]["resource_name"], "VariantAgentResource")
        self.assertEqual(variant["resource"]["properties"]["resource_name"], "VariantAgentResource")
        self.assertEqual(variant["source_resource"]["properties"]["resource_name"], "UpdatedAgentResource")
        self.assertEqual(variant["file"]["type"], "file")
        self.assertTrue(variant["editor_filesystem"]["is_file"])
        expect_resource(self.client, "res://data/agent_resource_variant.tres").to_have_property(
            "resource_name",
            "VariantAgentResource",
            timeout=0.1,
        )
        gradient = self.client.resource_save(
            "res://data/agent_gradient.tres",
            class_name="Gradient",
            properties={"resource_name": "AgentGradient"},
            timeout=0.1,
        )
        self.assertEqual(gradient["class"], "Gradient")
        graph = self.client.resource_save(
            "res://data/agent_gradient_texture.tres",
            class_name="GradientTexture1D",
            properties={
                "resource_name": "AgentGradientTexture",
                "gradient": {
                    "$type": "ResourceRef",
                    "path": "res://data/agent_gradient.tres",
                    "class": "Gradient",
                },
            },
            timeout=0.1,
        )
        self.assertEqual(graph["resource"]["properties"]["gradient"]["path"], "res://data/agent_gradient.tres")
        self.assertEqual(graph["dependency_state"]["dependency_count"], 1)
        self.assertEqual(graph["dependency_state"]["dependencies"][0]["path"], "res://data/agent_gradient.tres")
        expect_resource(self.client, "res://data/agent_gradient_texture.tres").to_have_dependency(
            "res://data/agent_gradient.tres",
            timeout=0.1,
        )
        nested = self.client.resource_set_properties(
            "res://data/agent_gradient_texture.tres",
            {
                "gradient": {
                    "$type": "SubResource",
                    "class": "Gradient",
                    "resource_name": "InlineGradient",
                }
            },
            timeout=0.1,
        )
        self.assertEqual(nested["resource"]["properties"]["gradient"]["class"], "Gradient")
        self.assertEqual(nested["resource"]["properties"]["gradient"]["resource_name"], "InlineGradient")
        scene_path = "res://scenes/main.tscn"
        script_path = "res://scripts/main.gd"
        self.server.files[scene_path] = "[gd_scene format=3]\n"
        self.server.files[script_path] = "extends Node\n"
        self.server.resource_dependencies[scene_path] = [
            "uid://script123::res://scripts/main.gd::Script",
            "res://data/missing_resource.tres::Resource",
        ]
        dependencies = self.client.resource_dependencies(scene_path)
        self.assertFalse(dependencies["ok"])
        self.assertEqual(dependencies["dependency_count"], 2)
        self.assertEqual(dependencies["missing_count"], 1)
        self.assertEqual(dependencies["dependencies"][0]["path"], script_path)
        matched_dependency = expect_resource(self.client, scene_path).to_have_dependency(
            script_path,
            dependency_type="Script",
            exists=True,
            timeout=0.1,
        )
        self.assertEqual(matched_dependency["path"], script_path)
        references = self.client.resource_references(
            script_path,
            search_path="res://scenes",
            dependency_type="Script",
            exists=True,
            max_results=10,
        )
        self.assertEqual(references["count"], 1)
        self.assertEqual(references["references"][0]["path"], scene_path)
        self.assertEqual(references["references"][0]["dependency"]["path"], script_path)
        referencing_scene = expect_resource(self.client, script_path).to_be_referenced_by(
            scene_path,
            search_path="res://scenes",
            dependency_type="Script",
            exists=True,
            timeout=0.1,
        )
        self.assertEqual(referencing_scene["path"], scene_path)
        move_source = "res://data/move_source.tres"
        move_destination = "res://data/moved/move_source.tres"
        move_reference = "res://data/uses_move_source.tres"
        self.server.files[move_source] = '[resource]\nresource_name = "MoveSource"\n'
        self.server.files[move_reference] = (
            '[gd_resource type="Resource" format=3]\n'
            '[ext_resource type="Resource" path="res://data/move_source.tres" id="1_move_source"]\n'
            "[resource]\n"
        )
        self.server.resource_dependencies[move_reference] = ["res://data/move_source.tres::Resource"]
        move_preview = self.client.resource_move(
            move_source,
            move_destination,
            search_path="res://data",
            extensions="tres",
            expected_reference_files=1,
            expected_replacements=1,
            dry_run=True,
            timeout=0.1,
        )
        self.assertTrue(move_preview["dry_run"])
        self.assertFalse(move_preview["moved"])
        self.assertEqual(move_preview["references_before"]["count"], 1)
        self.assertEqual(move_preview["changed_reference_files"], 1)
        self.assertEqual(move_preview["reference_replacements"], 1)
        self.assertIn(move_destination, move_preview["reference_updates"][0]["text"])
        self.assertIn(move_source, self.client.fs_read_text(move_reference))
        moved_resource = self.client.resource_move(
            move_source,
            move_destination,
            search_path="res://data",
            extensions="tres",
            expected_reference_files=1,
            expected_replacements=1,
            dry_run=False,
            timeout=0.1,
        )
        self.assertFalse(moved_resource["dry_run"])
        self.assertTrue(moved_resource["moved"])
        self.assertEqual(moved_resource["source_missing"]["type"], "missing")
        self.assertEqual(moved_resource["destination_state"]["type"], "file")
        self.assertEqual(moved_resource["references_after"]["count"], 1)
        self.assertEqual(moved_resource["remaining_source_references"]["count"], 0)
        self.assertIn(move_destination, self.client.fs_read_text(move_reference))
        self.assertNotIn(move_source, self.client.fs_read_text(move_reference))
        moved_reference = expect_resource(self.client, move_destination).to_be_referenced_by(
            move_reference,
            search_path="res://data",
            resource_type="Resource",
            exists=True,
            timeout=0.1,
        )
        self.assertEqual(moved_reference["path"], move_reference)
        with self.assertRaisesRegex(AssertionError, "missing_resource"):
            expect_resource(self.client, scene_path).to_have_no_missing_dependencies(
                timeout=0.01,
                interval=0.001,
            )
        expect_resource(self.client, script_path).to_have_no_missing_dependencies(timeout=0.1)
        expect_resource(self.client, "res://data/missing_resource.tres").not_to_exist(timeout=0.1)
        reimported = self.client.resource_reimport("res://data/agent_resource.tres")
        self.assertTrue(reimported["requested"])
        self.assertTrue(reimported["editor_filesystem"]["is_file"])
        self.assertEqual(reimported["import_count"], 0)
        reimported_project_files = self.client.resource_reimport([scene_path, script_path], timeout=0.1)
        self.assertEqual(reimported_project_files["paths"], [scene_path, script_path])
        self.assertEqual(reimported_project_files["editor_filesystem_states"][scene_path]["kind"], "file")
        self.assertEqual(reimported_project_files["editor_filesystem_states"][script_path]["kind"], "file")
        png_path = "res://assets/generated_pixel.png"
        self.client.fs_write_bytes(png_path, b"\x89PNG\r\n\x1a\nagent-bytes")
        reimported_png = self.client.resource_reimport(png_path, force=True)
        self.assertEqual(reimported_png["paths"], [png_path])
        self.assertTrue(reimported_png["force"])
        self.assertTrue(reimported_png["source_files"][0]["exists"])
        self.assertEqual(reimported_png["import_files"][0]["path"], f"{png_path}.import")
        self.assertTrue(reimported_png["editor_filesystem"]["is_file"])
        self.assertEqual(reimported_png["import_count"], 1)
        self.assertEqual(reimported_png["imports"][0]["resource_type"], "CompressedTexture2D")
        self.assertTrue(reimported_png["imports"][0]["ok"])
        self.assertEqual(reimported_png["imports"][0]["diagnostic_count"], 0)
        self.assertEqual(reimported_png["imports"][0]["generated_file_count"], 1)
        self.assertEqual(reimported_png["imports"][0]["missing_generated_file_count"], 0)
        self.assertEqual(reimported_png["imports"][0]["stale_generated_file_count"], 0)
        no_wait_reimport = self.client.resource_reimport(png_path, wait=False)
        self.assertNotIn("editor_filesystem", no_wait_reimport)
        self.assertNotIn("imports", no_wait_reimport)
        imported = self.client.resource_import_metadata(png_path)
        self.assertTrue(imported["exists"])
        self.assertEqual(imported["importer"], "texture")
        self.assertEqual(imported["source_file"], png_path)
        self.assertTrue(imported["source_file_state"]["exists"])
        self.assertTrue(imported["source_file_matches_path"])
        self.assertTrue(imported["generated_files_ready"])
        waited = self.client.wait_for_import(
            png_path,
            importer="texture",
            resource_type="CompressedTexture2D",
            generated_files_ready=True,
            timeout=0.2,
        )
        self.assertEqual(waited["resource_type"], "CompressedTexture2D")
        import_list = self.client.resource_imports(
            "res://assets",
            importer="texture",
            generated_files_ready=True,
            max_results=10,
        )
        self.assertEqual(import_list["count"], 1)
        self.assertEqual(import_list["imports"][0]["path"], png_path)
        self.assertTrue(import_list["imports"][0]["generated_files_ready"])
        expect_resource(self.client, png_path).to_be_imported(
            importer="texture",
            resource_type="CompressedTexture2D",
            generated_files_ready=True,
            timeout=0.1,
        )
        listed_import = expect_resource(self.client, png_path).to_be_import_listed(
            importer="texture",
            resource_type="CompressedTexture2D",
            generated_files_ready=True,
            timeout=0.1,
        )
        self.assertEqual(listed_import["path"], png_path)
        broken_png = "res://assets/broken_pixel.png"
        self.server.import_metadata[broken_png] = {
            "path": broken_png,
            "import_path": f"{broken_png}.import",
            "exists": True,
            "imported": False,
            "resource_exists": False,
            "resource_type": "CompressedTexture2D",
            "type": "CompressedTexture2D",
            "importer": "texture",
            "generated_files": [
                {"path": "res://.godot/imported/broken_pixel.png-fake.ctex", "exists": False}
            ],
            "generated_files_ready": False,
            "diagnostics": [
                {
                    "kind": "GENERATED_IMPORT_FILE_MISSING",
                    "severity": "error",
                    "path": "res://.godot/imported/broken_pixel.png-fake.ctex",
                }
            ],
            "diagnostic_count": 1,
            "error_count": 1,
            "warning_count": 0,
            "ok": False,
        }
        with self.assertRaisesRegex(GodotPlaywrightError, "GENERATED_IMPORT_FILE_MISSING"):
            self.client.wait_for_import(broken_png, timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "GENERATED_IMPORT_FILE_MISSING"):
            expect_resource(self.client, broken_png).to_be_imported(timeout=0.01, interval=0.001)
        methods = [method for method, _params in self.server.calls]
        self.assertIn("resource.save", methods)
        self.assertIn("resource.files", methods)
        self.assertIn("resource.file.describe", methods)
        self.assertIn("resource.inspect", methods)
        self.assertIn("resource.set_properties", methods)
        self.assertIn("resource.duplicate", methods)
        self.assertIn("resource.dependencies", methods)
        self.assertIn("resource.references", methods)
        self.assertIn("resource.move", methods)
        self.assertIn("resource.imports", methods)
        self.assertIn("resource.import_metadata", methods)

    def test_editor_authoring_helpers_call_rpc(self) -> None:
        new_scene = self.client.editor_new_scene(class_name="Control", name="AgentScene")
        self.assertEqual(new_scene["name"], "AgentScene")
        self.assertEqual(new_scene["class"], "Control")
        self.assertEqual(new_scene["editor_status"]["edited_scene_name"], "AgentScene")
        scene_new_calls = [call for call in self.server.calls if call[0] == "scene.new"]
        self.assertEqual(scene_new_calls[-1], ("scene.new", {"class": "Control", "name": "AgentScene", "close_existing": True}))

        node_class_list = self.client.node_classes(base_class="Control", name_contains="Label", max_results=10)
        node_class_names = {entry["class"] for entry in node_class_list["classes"]}
        self.assertIn("Label", node_class_names)
        self.assertFalse(node_class_list["truncated"])
        listed_label = expect_node_class(self.client, "Label").to_be_listed(base_class="Control", timeout=0.1)
        self.assertEqual(listed_label["class"], "Label")
        self.assertTrue(expect_node_class(self.client, "Label").to_be_instantiable(base_class="Control", timeout=0.1)["is_node"])
        label_schema = self.client.node_class_describe(
            "Label",
            properties=["text"],
            methods=["set_text"],
            storage_only=True,
        )
        self.assertTrue(label_schema["is_node"])
        self.assertEqual(label_schema["properties"][0]["name"], "text")
        self.assertEqual(label_schema["methods"][0]["name"], "set_text")
        self.assertEqual(label_schema["methods"][0]["arg_count"], 1)
        self.assertEqual(label_schema["methods"][0]["args"][0]["type_name"], "String")
        button_signal_schema = self.client.node_class_describe(
            "Button",
            signals=["pressed"],
            include_methods=False,
            include_values=False,
        )
        self.assertEqual(button_signal_schema["signals"][0]["name"], "pressed")
        self.assertEqual(button_signal_schema["signals"][0]["arg_count"], 0)
        self.assertEqual(self.client.node_schema("Label", properties=["text"])["values"]["text"], "")
        expect_node_class(self.client, "Label").to_be_node(timeout=0.1)
        label_text_property = expect_node_class(self.client, "Label").to_have_property(
            "text",
            type_name="String",
            storage=True,
            editor_visible=True,
            timeout=0.1,
        )
        self.assertEqual(label_text_property["type_name"], "String")
        self.assertEqual(expect_node_class(self.client, "Label").to_have_method("get_meta", timeout=0.1)["name"], "get_meta")
        self.assertEqual(expect_node_class(self.client, "Button").to_have_signal("pressed", timeout=0.1)["name"], "pressed")

        created = self.client.create_node("edited", "Label", name="StatusLabel")
        self.assertEqual(created["name"], "StatusLabel")
        self.assertEqual(created["class"], "Label")
        self.assertTrue(self.client.editor_history()["can_undo"])
        expect_editor(self.client).to_have_undo(timeout=0.1)
        expect_editor(self.client).not_to_have_redo(timeout=0.1)
        expect_editor(self.client).to_match_history({"available": True, "can_undo": True}, timeout=0.1)
        self.assertTrue(self.client.wait_for_editor_history({"can_undo": True}, timeout=0.1)["can_undo"])
        self.client.locator("#StatusLabel").set("text", "undoable text", undo_action="Set status text")
        self.assertEqual(self.client.locator("#StatusLabel").get("text"), "undoable text")
        waited_property = self.client.wait_for_node_property("#StatusLabel", "text", "undoable text", timeout=0.1)
        self.assertEqual(waited_property, "undoable text")
        undone_property = self.client.editor_undo()
        self.assertTrue(undone_property["changed"])
        self.assertTrue(undone_property["history_state"]["can_redo"])
        self.assertEqual(self.client.locator("#StatusLabel").get("text"), "Clicked 1")
        expect_editor(self.client).to_have_redo(timeout=0.1)
        redone_property = self.client.editor_redo()
        self.assertTrue(redone_property["changed"])
        self.assertFalse(redone_property["history_state"]["can_redo"])
        self.assertEqual(self.client.locator("#StatusLabel").get("text"), "undoable text")
        expect_editor(self.client).not_to_have_redo(timeout=0.1)
        self.client.locator("#StatusLabel").set_properties(
            {"text": "batch text", "visible": False},
            undo_action="Set status properties",
        )
        batch_state = self.client.wait_for_node_properties(
            "#StatusLabel",
            {"text": "batch text", "visible": False},
            timeout=0.1,
        )
        self.assertEqual(batch_state, {"text": "batch text", "visible": False})
        expect(self.client.locator("#StatusLabel")).to_have_properties(
            {"text": "batch text", "visible": False},
            timeout=0.1,
        )
        undone_batch = self.client.editor_undo()
        self.assertTrue(undone_batch["changed"])
        self.assertTrue(undone_batch["history_state"]["can_redo"])
        expect(self.client.locator("#StatusLabel")).to_have_properties(
            {"text": "undoable text", "visible": True},
            timeout=0.1,
        )
        redone_batch = self.client.editor_redo()
        self.assertTrue(redone_batch["changed"])
        self.assertFalse(redone_batch["history_state"]["can_redo"])
        expect(self.client.locator("#StatusLabel")).to_have_properties(
            {"text": "batch text", "visible": False},
            timeout=0.1,
        )
        expect_editor(self.client).not_to_have_redo(timeout=0.1)
        self.client.locator("#StatusLabel").set("text", "no wait undoable", undo_action="No wait undo")
        fire_and_forget_undo = self.client.editor_undo(wait=False)
        self.assertNotIn("history_state", fire_and_forget_undo)
        restored_no_wait = self.client.editor_redo(timeout=0.1)
        self.assertIn("history_state", restored_no_wait)
        set_result = self.client.set_node_property("#StatusLabel", "text", "direct text", undo=False, timeout=0.1)
        self.assertEqual(set_result["property_state"]["value"], "direct text")
        self.assertEqual(self.client.locator("#StatusLabel").get("text"), "direct text")
        set_many = self.client.set_node_properties(
            "#StatusLabel",
            {"text": "direct batch", "visible": True},
            undo=False,
            timeout=0.1,
        )
        self.assertEqual(set_many["properties_state"], {"text": "direct batch", "visible": True})
        no_wait = self.client.set_node_property("#StatusLabel", "text", "no wait text", undo=False, wait=False)
        self.assertNotIn("property_state", no_wait)
        status_label = self.client.locator("#StatusLabel")
        status_label.set_metadata(
            {"test_id": "status-label", "agent_tag": "generated"},
            undo_action="Set status metadata",
        )
        expect(status_label).to_have_metadata(
            {"test_id": "status-label", "agent_tag": "generated"},
            timeout=0.1,
        )
        undone_metadata = self.client.editor_undo()
        self.assertTrue(undone_metadata["changed"])
        self.assertTrue(undone_metadata["history_state"]["can_redo"])
        expect(status_label).not_to_have_meta("agent_tag", timeout=0.1)
        redone_metadata = self.client.editor_redo()
        self.assertTrue(redone_metadata["changed"])
        self.assertFalse(redone_metadata["history_state"]["can_redo"])
        expect(status_label).to_have_meta("agent_tag", "generated", timeout=0.1)
        status_label.remove_meta("agent_tag", undo_action="Remove status metadata")
        expect(status_label).not_to_have_meta("agent_tag", timeout=0.1)
        undone_remove_metadata = self.client.editor_undo()
        self.assertTrue(undone_remove_metadata["changed"])
        self.assertTrue(undone_remove_metadata["history_state"]["can_redo"])
        expect(status_label).to_have_meta("agent_tag", "generated", timeout=0.1)
        direct_metadata = self.client.set_node_metadata(
            "#StatusLabel",
            {"agent_direct": "ready"},
            undo=False,
            timeout=0.1,
        )
        self.assertEqual(direct_metadata["metadata_state"]["agent_direct"], "ready")
        self.assertEqual(
            self.client.wait_for_node_meta("#StatusLabel", "agent_direct", "ready", timeout=0.1),
            "ready",
        )
        self.assertEqual(
            self.client.wait_for_node_metadata("#StatusLabel", {"agent_direct": "ready"}, timeout=0.1),
            {"agent_direct": "ready"},
        )
        removed_metadata = self.client.remove_node_metadata(
            "#StatusLabel",
            "agent_direct",
            undo=False,
            timeout=0.1,
        )
        self.assertEqual(removed_metadata["metadata_state"], {})
        self.assertEqual(
            self.client.wait_for_node_meta("#StatusLabel", "agent_direct", state="missing", timeout=0.1),
            {},
        )
        fire_and_forget_metadata = self.client.set_node_metadata(
            "#StatusLabel",
            {"fire_and_forget": True},
            undo=False,
            wait=False,
        )
        self.assertNotIn("metadata_state", fire_and_forget_metadata)
        created_without_undo = self.client.create_node("edited", "Node", name="NoUndoNode", undo=False)
        self.assertEqual(created_without_undo["name"], "NoUndoNode")
        self.assertFalse(any(action.get("path", "").endswith("/NoUndoNode") for action in self.server.undo_stack))
        grouped = self.client.add_node_group("#StatusLabel", "agent_generated")
        self.assertTrue(grouped["added"])
        self.assertIn("agent_generated", grouped["groups"])
        self.assertIn("agent_generated", grouped["groups_state"]["groups"])
        self.assertEqual(self.client.node_groups("#StatusLabel")["groups"], ["agent_generated"])
        self.assertIn(
            "agent_generated",
            self.client.wait_for_node_group("#StatusLabel", "agent_generated", timeout=0.1)["groups"],
        )
        expect(self.client.locator("#StatusLabel")).to_have_group("agent_generated", timeout=0.1)
        expect(self.client.locator("#StatusLabel")).not_to_have_group("missing_group", timeout=0.1)
        with self.assertRaisesRegex(AssertionError, "groups=.*agent_generated"):
            expect(self.client.locator("#StatusLabel")).to_have_group(
                "missing_group",
                timeout=0.01,
                interval=0.001,
            )
        self.assertEqual(self.client.get_by_group("agent_generated").selector, {"group": "agent_generated"})
        temporary_group = self.client.add_node_group("#StatusLabel", "temporary_generated", persistent=False)
        self.assertFalse(temporary_group["persistent"])
        self.assertIn("temporary_generated", temporary_group["groups_state"]["groups"])
        removed_group = self.client.remove_node_group("#StatusLabel", "temporary_generated")
        self.assertTrue(removed_group["removed"])
        self.assertNotIn("temporary_generated", removed_group["groups"])
        self.assertNotIn("temporary_generated", removed_group["groups_state"]["groups"])
        self.assertNotIn(
            "temporary_generated",
            self.client.wait_for_node_group(
                "#StatusLabel",
                "temporary_generated",
                state="missing",
                timeout=0.1,
            )["groups"],
        )
        fire_and_forget_group = self.client.add_node_group("#StatusLabel", "fire_and_forget_group", wait=False)
        self.assertNotIn("groups_state", fire_and_forget_group)

        container = self.client.create_node("edited", "VBoxContainer", name="GeneratedPanel")
        self.assertEqual(container["name"], "GeneratedPanel")
        self.assertEqual(container["node_state"]["class"], "VBoxContainer")
        tree = self.client.create_node_tree(
            [
                {
                    "class": "PanelContainer",
                    "name": "AgentHud",
                    "groups": ["agent_ui"],
                    "metadata": {"test_id": "agent-hud"},
                    "children": [
                        {
                            "class": "Label",
                            "name": "AgentTitle",
                            "properties": {"text": "Agent Ready"},
                            "metadata": {"test_id": "agent-title"},
                        },
                        {
                            "class": "Button",
                            "name": "AgentAction",
                            "properties": {"text": "Run"},
                            "groups": ["agent_action"],
                            "script": "res://scripts/generated/status_label.gd",
                        },
                    ],
                }
            ],
            parent="#GeneratedPanel",
            timeout=0.1,
        )
        self.assertEqual(tree["count"], 3)
        self.assertEqual(tree["nodes"][0]["path"], "/root/Main/GeneratedPanel/AgentHud")
        self.assertEqual(tree["nodes"][0]["metadata_state"]["test_id"], "agent-hud")
        self.assertIn("agent_ui", tree["nodes"][0]["group_states"])
        self.assertEqual(tree["nodes"][1]["properties_state"]["text"], "Agent Ready")
        self.assertEqual(tree["nodes"][1]["metadata_state"]["test_id"], "agent-title")
        self.assertEqual(tree["nodes"][2]["properties_state"]["text"], "Run")
        self.assertEqual(tree["nodes"][2]["script_state"]["path"], "res://scripts/generated/status_label.gd")
        expect(self.client.locator({"path": "/root/Main/GeneratedPanel/AgentHud"}, root="root")).to_have_group(
            "agent_ui",
            timeout=0.1,
        )
        expect(self.client.locator({"path": "/root/Main/GeneratedPanel/AgentHud/AgentTitle"}, root="root")).to_have_property(
            "text",
            "Agent Ready",
            timeout=0.1,
        )
        instance = self.client.instantiate_scene(
            "res://scenes/badge.tscn",
            parent="#GeneratedPanel",
            name="BadgeInstance",
        )
        self.assertEqual(instance["name"], "BadgeInstance")
        self.assertEqual(instance["source_scene"], "res://scenes/badge.tscn")
        self.assertEqual(instance["path"], "/root/Main/GeneratedPanel/BadgeInstance")
        self.assertEqual(instance["node_state"]["path"], "/root/Main/GeneratedPanel/BadgeInstance")
        reparented = self.client.reparent_node("#StatusLabel", "#GeneratedPanel", index=0)
        self.assertEqual(reparented["path"], "/root/Main/GeneratedPanel/StatusLabel")
        self.assertEqual(reparented["new_parent"], "/root/Main/GeneratedPanel")
        self.assertEqual(reparented["node_state"]["parent"], "/root/Main/GeneratedPanel")
        moved = self.client.move_node("#StatusLabel", 0)
        self.assertEqual(moved["index"], 0)
        self.assertEqual(moved["node_state"]["index"], 0)
        duplicate = self.client.duplicate_node("#StatusLabel", parent="#GeneratedPanel", name="StatusLabelCopy")
        self.assertEqual(duplicate["name"], "StatusLabelCopy")
        self.assertEqual(duplicate["source"]["name"], "StatusLabel")
        self.assertEqual(duplicate["node_state"]["path"], "/root/Main/GeneratedPanel/StatusLabelCopy")
        waited_node = self.client.wait_for_node(
            {"path": "/root/Main/GeneratedPanel/StatusLabelCopy"},
            root="root",
            expected={"name": "StatusLabelCopy"},
            timeout=0.1,
        )
        self.assertEqual(waited_node["name"], "StatusLabelCopy")
        fire_and_forget_duplicate = self.client.duplicate_node(
            "#StatusLabel",
            parent="#GeneratedPanel",
            name="NoWaitCopy",
            wait=False,
        )
        self.assertNotIn("node_state", fire_and_forget_duplicate)
        attached = self.client.attach_script("#StatusLabel", "res://scripts/generated/status_label.gd", inspect=True)
        self.assertEqual(attached["script"]["path"], "res://scripts/generated/status_label.gd")
        self.assertEqual(attached["script_state"]["path"], "res://scripts/generated/status_label.gd")
        waited_node_script = self.client.wait_for_node_script(
            "#StatusLabel",
            path="res://scripts/generated/status_label.gd",
            timeout=0.1,
        )
        self.assertEqual(waited_node_script["script"]["path"], "res://scripts/generated/status_label.gd")
        expect(self.client.locator("#StatusLabel")).to_have_script("res://scripts/generated/status_label.gd", timeout=0.1)
        expect(self.client.locator("#StatusLabel")).not_to_have_script("res://scripts/generated/other.gd", timeout=0.1)
        with self.assertRaisesRegex(AssertionError, "script=.*status_label.gd"):
            expect(self.client.locator("#StatusLabel")).to_have_script(
                "res://scripts/generated/other.gd",
                timeout=0.01,
                interval=0.001,
            )
        signal_button = self.client.create_node("#GeneratedPanel", "Button", name="SignalButton")
        self.assertEqual(signal_button["name"], "SignalButton")
        signal_receiver = self.client.create_node("#GeneratedPanel", "Node", name="SignalReceiver")
        self.assertEqual(signal_receiver["name"], "SignalReceiver")
        self.assertEqual(self.client.signal_connections("#SignalButton", signal="pressed")["count"], 0)
        connected_signal = self.client.signal_connect(
            "#SignalButton",
            "pressed",
            target="#SignalReceiver",
            method="on_signal_button_pressed",
            validate_method=False,
        )
        self.assertTrue(connected_signal["connected"])
        self.assertEqual(connected_signal["connection"]["target_path"], "/root/Main/SignalReceiver")
        self.assertEqual(connected_signal["connection"]["method"], "on_signal_button_pressed")
        self.assertTrue(connected_signal["connection"]["persistent"])
        self.assertEqual(connected_signal["connection_state"]["connection"]["method"], "on_signal_button_pressed")
        waited_connection = self.client.wait_for_signal_connection(
            "#SignalButton",
            "pressed",
            target="#SignalReceiver",
            method="on_signal_button_pressed",
            persistent=True,
            timeout=0.1,
        )
        self.assertEqual(waited_connection["connection"]["target_path"], "/root/Main/SignalReceiver")
        matched_connection = expect(self.client.locator("#SignalButton")).to_have_signal_connection(
            "pressed",
            target="#SignalReceiver",
            method="on_signal_button_pressed",
            persistent=True,
            timeout=0.1,
        )
        self.assertEqual(matched_connection["method"], "on_signal_button_pressed")
        expect(self.client.locator("#SignalButton")).not_to_have_signal_connection(
            "pressed",
            target="#SignalReceiver",
            method="missing_handler",
            timeout=0.1,
        )
        with self.assertRaisesRegex(AssertionError, "connections=.*on_signal_button_pressed"):
            expect(self.client.locator("#SignalButton")).to_have_signal_connection(
                "pressed",
                target="#SignalReceiver",
                method="missing_handler",
                timeout=0.01,
                interval=0.001,
            )
        duplicate_signal = self.client.locator("#SignalButton").connect_signal(
            "pressed",
            target="#SignalReceiver",
            method="on_signal_button_pressed",
            validate_method=False,
        )
        self.assertFalse(duplicate_signal["connected"])
        self.assertTrue(duplicate_signal["already_connected"])
        self.assertEqual(duplicate_signal["connection_state"]["state"], "connected")
        signal_connections = self.client.locator("#SignalButton").signal_connections("pressed")
        self.assertEqual(signal_connections["count"], 1)
        disconnected_signal = self.client.signal_disconnect(
            "#SignalButton",
            "pressed",
            target="#SignalReceiver",
            method="on_signal_button_pressed",
        )
        self.assertTrue(disconnected_signal["removed"])
        self.assertEqual(disconnected_signal["connections"], [])
        self.assertEqual(disconnected_signal["connection_state"]["state"], "disconnected")
        self.assertEqual(
            self.client.wait_for_signal_connection(
                "#SignalButton",
                "pressed",
                target="#SignalReceiver",
                method="on_signal_button_pressed",
                state="disconnected",
                timeout=0.1,
            )["connection"],
            None,
        )
        expect(self.client.locator("#SignalButton")).not_to_have_signal_connection(
            "pressed",
            target="#SignalReceiver",
            method="on_signal_button_pressed",
            timeout=0.1,
        )
        fire_and_forget_signal = self.client.locator("#SignalButton").connect_signal(
            "pressed",
            target="#SignalReceiver",
            method="on_signal_button_pressed",
            validate_method=False,
            wait=False,
        )
        self.assertNotIn("connection_state", fire_and_forget_signal)
        saved_branch = self.client.locator("#GeneratedPanel").save_as_scene("res://scenes/generated_panel.tscn")
        self.assertTrue(saved_branch["saved"])
        self.assertEqual(saved_branch["path"], "res://scenes/generated_panel.tscn")
        self.assertEqual(saved_branch["source"]["name"], "GeneratedPanel")
        detached = self.client.detach_script("#StatusLabel")
        self.assertIsNone(detached["script"])
        self.assertEqual(detached["previous_script"]["path"], "res://scripts/generated/status_label.gd")
        self.assertEqual(detached["script_state"]["state"], "detached")
        self.assertEqual(self.client.wait_for_node_script("#StatusLabel", state="detached", timeout=0.1)["path"], "")
        expect(self.client.locator("#StatusLabel")).not_to_have_script(timeout=0.1)
        fire_and_forget_attach = self.client.attach_script(
            "#StatusLabel",
            "res://scripts/generated/status_label.gd",
            wait=False,
        )
        self.assertNotIn("script_state", fire_and_forget_attach)

        deleted = self.client.delete_node("#StatusLabel")
        self.assertEqual(deleted["deleted"], "/root/Main/StatusLabel")
        self.assertEqual(deleted["node_state"]["state"], "detached")
        self.assertEqual(
            self.client.wait_for_node({"path": "/root/Main/StatusLabel"}, state="detached", root="root", timeout=0.1)[
                "state"
            ],
            "detached",
        )
        fire_and_forget_delete = self.client.delete_node("#SignalReceiver", wait=False)
        self.assertNotIn("node_state", fire_and_forget_delete)

        opened_status = self.client.editor_open_scene("res://scenes/secondary.tscn", timeout=0.1)
        self.assertEqual(opened_status["path"], "res://scenes/secondary.tscn")
        self.assertEqual(opened_status["edited_scene_file_path"], "res://scenes/secondary.tscn")
        self.assertEqual(opened_status["edited_scene_name"], "Secondary")
        self.assertEqual(opened_status["editor_status"]["edited_scene_file_path"], "res://scenes/secondary.tscn")
        fire_and_forget_open = self.client.editor_open_scene("res://scenes/main.tscn", wait=False)
        self.assertEqual(fire_and_forget_open["path"], "res://scenes/main.tscn")
        self.assertNotIn("editor_status", fire_and_forget_open)

        saved = self.client.editor_save_scene("res://scenes/generated_by_agent.tscn")
        self.assertTrue(saved["saved"])
        self.assertEqual(saved["path"], "res://scenes/generated_by_agent.tscn")
        self.assertEqual(saved["editor_status"]["edited_scene_file_path"], "res://scenes/generated_by_agent.tscn")
        self.assertEqual(saved["file"]["type"], "file")
        self.assertTrue(saved["editor_filesystem"]["is_file"])

        self.assertEqual(self.client.project_get_setting("application/config/name"), "Fake Godot")
        changed = self.client.project_set_setting("application/config/name", "Agent Project", save=True)
        self.assertTrue(changed["saved"])
        self.assertEqual(changed["setting"]["value"], "Agent Project")
        self.assertEqual(self.client.project_get_setting("application/config/name"), "Agent Project")
        self.assertEqual(self.client.wait_for_project_setting("application/config/name", "Agent Project", timeout=0.1), "Agent Project")
        self.assertEqual(self.client.project_export_presets()["count"], 0)
        preset = self.client.project_set_export_preset(
            "Agent Linux",
            "Linux",
            export_path="build/agent_linux.x86_64",
            options={"binary_format/embed_pck": False},
        )
        self.assertEqual(preset["index"], 0)
        self.assertEqual(preset["platform"], "Linux")
        self.assertFalse(preset["options"]["binary_format/embed_pck"])
        self.assertEqual(preset["preset_state"]["export_path"], "build/agent_linux.x86_64")
        updated_preset = self.client.project_set_export_preset(
            "Agent Linux",
            "Linux",
            export_path="build/agent_linux_v2.x86_64",
            runnable=False,
            options={"binary_format/embed_pck": False},
        )
        self.assertEqual(updated_preset["index"], 0)
        self.assertFalse(updated_preset["runnable"])
        self.assertEqual(updated_preset["preset_state"]["export_path"], "build/agent_linux_v2.x86_64")
        waited_preset = self.client.wait_for_export_preset(
            "Agent Linux",
            platform="Linux",
            export_path="build/agent_linux_v2.x86_64",
            runnable=False,
            options={"binary_format/embed_pck": False},
            timeout=0.1,
        )
        self.assertEqual(waited_preset["name"], "Agent Linux")
        presets = self.client.project_export_presets()
        self.assertEqual(presets["count"], 1)
        self.assertEqual(presets["presets"][0]["export_path"], "build/agent_linux_v2.x86_64")
        matched_preset = expect_project(self.client).to_have_export_preset(
            "Agent Linux",
            platform="Linux",
            export_path="build/agent_linux_v2.x86_64",
            runnable=False,
            options={"binary_format/embed_pck": False},
            fields={"script_export_mode": 2},
            timeout=0.1,
        )
        self.assertEqual(matched_preset["name"], "Agent Linux")
        with self.assertRaisesRegex(AssertionError, "options=.*binary_format/embed_pck"):
            expect_project(self.client).to_have_export_preset(
                "Agent Linux",
                options={"binary_format/embed_pck": True},
                timeout=0.01,
                interval=0.001,
            )
        with self.assertRaisesRegex(AssertionError, "Expected export preset 'Agent Linux'.*runnable=True"):
            expect_project(self.client).to_have_export_preset(
                "Agent Linux",
                runnable=True,
                timeout=0.01,
                interval=0.001,
            )
        expect_project(self.client).not_to_have_export_preset("Missing Preset", timeout=0.1)
        self.assertEqual(self.client.project_main_scene()["path"], "res://scenes/main.tscn")
        main_scene = self.client.project_set_main_scene("res://scenes/generated_by_agent.tscn", save=True)
        self.assertEqual(main_scene["path"], "res://scenes/generated_by_agent.tscn")
        self.assertTrue(main_scene["saved"])
        self.assertEqual(main_scene["main_scene"]["path"], "res://scenes/generated_by_agent.tscn")
        self.assertEqual(
            self.client.wait_for_project_main_scene("res://scenes/generated_by_agent.tscn", timeout=0.1)["path"],
            "res://scenes/generated_by_agent.tscn",
        )
        expect_project(self.client).to_have_main_scene("res://scenes/generated_by_agent.tscn", timeout=0.1)
        expect_project(self.client).not_to_have_main_scene("res://scenes/main.tscn", timeout=0.1)
        autoload = self.client.project_add_autoload(
            "AgentState",
            "res://scripts/generated/agent_state.gd",
            save=True,
            require_exists=False,
        )
        self.assertEqual(autoload["name"], "AgentState")
        self.assertEqual(autoload["raw"], "*res://scripts/generated/agent_state.gd")
        self.assertEqual(autoload["autoload_state"]["path"], "res://scripts/generated/agent_state.gd")
        self.assertEqual(
            self.client.wait_for_project_autoload(
                "AgentState",
                path="res://scripts/generated/agent_state.gd",
                singleton=True,
                timeout=0.1,
            )["name"],
            "AgentState",
        )
        autoloads = self.client.project_autoloads()
        self.assertEqual(autoloads["count"], 1)
        project_summary = self.client.project_summary(max_results=10, include_input_events=True)
        self.assertTrue(project_summary["ok"])
        self.assertEqual(project_summary["main_scene"]["path"], "res://scenes/generated_by_agent.tscn")
        self.assertEqual(project_summary["counts"]["autoloads"], 1)
        self.assertEqual(project_summary["counts"]["export_presets"], 1)
        self.assertGreaterEqual(project_summary["counts"]["scenes"], 1)
        self.assertGreaterEqual(project_summary["counts"]["scripts"], 1)
        self.assertGreaterEqual(project_summary["counts"]["input_actions"], 1)
        self.assertIn("scene_files", project_summary)
        self.assertIn("script_classes", project_summary)
        self.assertIn("resource_files", project_summary)
        project_doctor = self.client.project_doctor(max_results=10, include_input_events=True, include_protocol_methods=True)
        self.assertTrue(project_doctor["ok"])
        self.assertTrue(project_doctor["ready"])
        self.assertEqual(project_doctor["status"], "ready")
        self.assertIn("project_summary", project_doctor)
        self.assertIn("protocol", project_doctor)
        self.assertIn("project.doctor", {entry["method"] for entry in project_doctor["protocol"]["methods"]})
        doctor_checks = {entry["name"]: entry for entry in project_doctor["checks"]}
        self.assertEqual(doctor_checks["project_summary"]["status"], "pass")
        self.assertIn(doctor_checks["main_scene"]["status"], {"pass", "warn"})
        self.assertGreaterEqual(project_doctor["check_count"], 3)
        self.assertIn("next_steps", project_doctor)
        matched_autoload = expect_project(self.client).to_have_autoload(
            "AgentState",
            path="res://scripts/generated/agent_state.gd",
            singleton=True,
            timeout=0.1,
        )
        self.assertEqual(matched_autoload["name"], "AgentState")
        with self.assertRaisesRegex(AssertionError, "Expected project autoload 'AgentState'.*singleton=False"):
            expect_project(self.client).to_have_autoload(
                "AgentState",
                singleton=False,
                timeout=0.01,
                interval=0.001,
            )
        removed_autoload = self.client.project_remove_autoload("AgentState", save=True)
        self.assertTrue(removed_autoload["removed"])
        self.assertEqual(removed_autoload["autoload_state"]["state"], "missing")
        self.assertEqual(self.client.project_autoloads()["count"], 0)
        self.assertEqual(
            self.client.wait_for_project_autoload("AgentState", state="missing", timeout=0.1)["state"],
            "missing",
        )
        expect_project(self.client).not_to_have_autoload("AgentState", timeout=0.1)
        fire_and_forget_setting = self.client.project_set_setting("application/config/name", "No Wait", wait=False)
        self.assertNotIn("setting", fire_and_forget_setting)

        methods = [method for method, _params in self.server.calls]
        self.assertIn("scene.new", methods)
        self.assertIn("editor.history", methods)
        self.assertIn("editor.undo", methods)
        self.assertIn("editor.redo", methods)
        self.assertIn("node.create", methods)
        self.assertIn("node.create_tree", methods)
        self.assertIn("node.instantiate_scene", methods)
        self.assertIn("node.save_as_scene", methods)
        self.assertIn("node.metadata", methods)
        self.assertIn("node.set_metadata", methods)
        self.assertIn("node.remove_metadata", methods)
        self.assertIn("node.groups", methods)
        self.assertIn("node.add_group", methods)
        self.assertIn("node.remove_group", methods)
        self.assertIn("node.reparent", methods)
        self.assertIn("node.move", methods)
        self.assertIn("node.duplicate", methods)
        self.assertIn("node.attach_script", methods)
        self.assertIn("node.detach_script", methods)
        self.assertIn("node.delete", methods)
        self.assertIn("signal.connections", methods)
        self.assertIn("signal.connect", methods)
        self.assertIn("signal.disconnect", methods)
        self.assertIn("scene.open", methods)
        self.assertIn("scene.save", methods)
        self.assertIn("project.set_setting", methods)
        self.assertIn("project.doctor", methods)
        self.assertIn("project.summary", methods)
        self.assertIn("project.export_presets", methods)
        self.assertIn("project.set_export_preset", methods)
        self.assertIn("project.main_scene", methods)
        self.assertIn("project.set_main_scene", methods)
        self.assertIn("project.add_autoload", methods)
        self.assertIn("project.autoloads", methods)
        self.assertIn("project.remove_autoload", methods)

    def test_editor_helpers_call_rpc(self) -> None:
        selection = self.client.editor_select("#CounterButton")
        self.assertEqual(selection["count"], 1)
        self.assertEqual(self.client.editor_selection()["count"], 1)
        editor_panel = self.client.editor_locator("Panel")
        self.assertTrue(editor_panel.exists())
        self.assertEqual(self.server.calls[-1][0], "node.find")
        self.assertEqual(self.server.calls[-1][1]["root"], "editor")
        editor_panel_by_role = self.client.editor_get_by_role("panel")
        self.assertTrue(editor_panel_by_role.exists())
        self.assertEqual(self.server.calls[-1][1]["selector"], {"role": "panel"})
        self.assertEqual(self.server.calls[-1][1]["root"], "editor")
        inspected = self.client.editor_inspect(selector="#CounterButton", property="text", timeout=0.1)
        self.assertEqual(inspected["property"], "text")
        self.assertEqual(inspected["inspector_state"]["properties"][0]["name"], "text")
        self.assertEqual(inspected["inspector_state"]["properties"][0]["value"], "Clicked 1")
        no_wait_inspect = self.client.editor_inspect(selector="#CounterButton", property="text", wait=False)
        self.assertNotIn("inspector_state", no_wait_inspect)
        inspector = self.client.inspector("#CounterButton")
        description = inspector.describe()
        self.assertEqual(description["count"], 1)
        self.assertEqual(inspector.property("text").value(), "Clicked 1")
        single_update = inspector.property("text").set("Clicked 2", timeout=0.1)
        self.assertEqual(single_update["value"], "Clicked 2")
        self.assertEqual(single_update["property_state"]["value"], "Clicked 2")
        expect_inspector(inspector).to_have_property("text", "Clicked 2", timeout=0.1)
        expect_inspector(inspector.property("text")).to_have_value("Clicked 2", timeout=0.1)
        updated = inspector.set_properties({"text": "Batch Updated", "visible": False})
        self.assertEqual(updated["count"], 2)
        self.assertEqual(updated["values"], {"text": "Batch Updated", "visible": False})
        self.assertEqual(updated["properties_state"], {"text": "Batch Updated", "visible": False})
        self.assertEqual(inspector.values(properties=["text", "visible"]), {"text": "Batch Updated", "visible": False})
        expect_inspector(inspector).to_have_properties({"text": "Batch Updated", "visible": False}, timeout=0.1)
        expect_inspector(inspector).not_to_have_properties({"text": "Clicked 2", "visible": False}, timeout=0.1)
        wrapper_values = self.client.editor_inspector_values("#CounterButton", properties=["text", "visible"])
        self.assertEqual(wrapper_values, {"text": "Batch Updated", "visible": False})
        wrapper_single = self.client.editor_inspector_set_property("text", "Wrapper Single", "#CounterButton")
        self.assertEqual(wrapper_single["property_state"]["value"], "Wrapper Single")
        wrapper_set = self.client.editor_inspector_set_properties({"text": "Wrapper Updated"}, "#CounterButton")
        self.assertEqual(wrapper_set["values"], {"text": "Wrapper Updated"})
        self.assertEqual(wrapper_set["properties_state"], {"text": "Wrapper Updated"})
        no_wait_property = self.client.editor_inspector_set_property(
            "text",
            "No Wait Inspector",
            "#CounterButton",
            wait=False,
        )
        self.assertNotIn("property_state", no_wait_property)
        no_wait_batch = inspector.set_properties({"text": "No Wait Batch"}, wait=False)
        self.assertNotIn("properties_state", no_wait_batch)
        resource_batch = self.client.editor_inspector_set_properties(
            {"resource_name": "ResourceBatch"},
            resource_path="res://data/agent_resource.tres",
            save=True,
        )
        self.assertTrue(resource_batch["saved"])
        self.assertEqual(resource_batch["properties_state"], {"resource_name": "ResourceBatch"})
        self.assertEqual(
            self.client.editor_inspector_values(
                resource_path="res://data/agent_resource.tres",
                properties=["resource_name"],
            ),
            {"resource_name": "ResourceBatch"},
        )
        opened = self.client.editor_open_script("res://scripts/main.gd", line=3, timeout=0.1)
        self.assertEqual(opened["path"], "res://scripts/main.gd")
        self.assertEqual(opened["script_state"]["path"], "res://scripts/main.gd")
        self.assertIn("res://scripts/main.gd", opened["script_editor"]["open_paths"])
        self.assertEqual(opened["script_editor"]["current_path"], "res://scripts/main.gd")
        script_status = self.client.editor_script_status()
        self.assertEqual(script_status["open_count"], 1)
        waited_editor_script = self.client.wait_for_editor_script(
            "res://scripts/main.gd",
            current=True,
            timeout=0.1,
        )
        self.assertEqual(waited_editor_script["current_path"], "res://scripts/main.gd")
        expect_editor(self.client).to_have_open_script("res://scripts/main.gd", timeout=0.1)
        expect_editor(self.client).to_have_current_script("res://scripts/main.gd", timeout=0.1)
        no_wait_opened = self.client.editor_open_script("res://scripts/main.gd", wait=False)
        self.assertNotIn("script_state", no_wait_opened)
        scanned = self.client.editor_scan_filesystem(["res://scripts", "res://scenes"], timeout=0.1)
        self.assertTrue(scanned["requested"])
        self.assertEqual(scanned["filesystem_states"]["res://scripts"]["kind"], "directory")
        self.assertEqual(scanned["filesystem_states"]["res://scenes"]["kind"], "directory")
        single_scan = self.client.editor_scan_filesystem("res://scripts/generated/agent_tool.gd", timeout=0.1)
        self.assertEqual(single_scan["filesystem_state"]["resource_type"], "GDScript")
        no_wait_scan = self.client.editor_scan_filesystem("res://scripts/generated/agent_tool.gd", wait=False)
        self.assertNotIn("filesystem_state", no_wait_scan)
        self.client.fs_write_text(
            "res://scripts/generated/agent_tool.gd",
            "class_name AgentTool\n"
            "extends Node\n"
            "signal tool_ready\n"
            "@export var enabled := true\n\n"
            "func generated_value() -> int:\n"
            "\treturn 42\n",
        )
        script = self.client.editor_script_describe("res://scripts/generated/agent_tool.gd", include_source=True)
        self.assertEqual(script["symbols"]["class_name"], "AgentTool")
        self.assertEqual(script["symbols"]["extends"], "Node")
        self.assertIn("generated_value", script["source"])
        script_file = self.client.script_file_describe("res://scripts/generated/agent_tool.gd", include_source=True)
        self.assertEqual(script_file["class_name"], "AgentTool")
        self.assertEqual(script_file["extends"], "Node")
        self.assertEqual(script_file["function_count"], 1)
        self.assertEqual(script_file["signal_count"], 1)
        self.assertEqual(script_file["variable_count"], 1)
        self.assertIn("generated_value", script_file["source"])
        script_class_list = self.client.script_classes(class_name="AgentTool", base_class="Node", max_results=10)
        self.assertEqual(script_class_list["count"], 1)
        script_class = script_class_list["classes"][0]
        self.assertEqual(script_class["class_name"], "AgentTool")
        self.assertEqual(script_class["path"], "res://scripts/generated/agent_tool.gd")
        self.assertTrue(script_class["is_node"])
        self.assertFalse(script_class["is_resource"])
        self.assertEqual(script_class["signals"][0]["name"], "tool_ready")
        self.assertEqual(script_class["variables"][0]["name"], "enabled")
        listed_script_class = expect_script_class(self.client, "AgentTool").to_be_listed(base_class="Node", timeout=0.1)
        self.assertEqual(listed_script_class["class"], "AgentTool")
        self.assertEqual(expect_script_class(self.client, "AgentTool").to_extend("Node", timeout=0.1)["parent"], "Node")
        self.assertTrue(expect_script_class(self.client, "AgentTool").to_be_node(timeout=0.1)["is_node"])
        self.assertEqual(
            expect_script_class(self.client, "AgentTool").to_have_function("generated_value", timeout=0.1)["name"],
            "generated_value",
        )
        expect_script(self.client, "res://scripts/generated/agent_tool.gd").to_extend("Node", timeout=0.1)
        expect_script(self.client, "res://scripts/generated/agent_tool.gd").to_have_class_name("AgentTool", timeout=0.1)
        expect_script(self.client, "res://scripts/generated/agent_tool.gd").to_define_function("generated_value", timeout=0.1)
        expect_script(self.client, "res://scripts/generated/agent_tool.gd").to_define_signal("tool_ready", timeout=0.1)
        expect_script(self.client, "res://scripts/generated/agent_tool.gd").to_define_variable("enabled", timeout=0.1)
        expect_script(self.client, "res://scripts/generated/agent_tool.gd").to_contain_source("generated_value", timeout=0.1)
        generated_script = self.client.write_script(
            "res://tools/agent_status.gd",
            'extends Label\n\nfunc agent_status() -> String:\n\treturn "ready"\n',
            extends="Label",
            functions=["agent_status"],
            source_contains='return "ready"',
            open_editor=True,
            line=3,
            timeout=0.1,
        )
        self.assertEqual(generated_script["file"]["type"], "file")
        self.assertEqual(generated_script["editor_filesystem"]["resource_type"], "GDScript")
        self.assertEqual(generated_script["script"]["symbols"]["extends"], "Label")
        self.assertEqual(generated_script["script"]["source"].splitlines()[0], "extends Label")
        self.assertEqual(generated_script["opened_script"]["line"], 3)
        self.assertEqual(generated_script["opened_script"]["script_state"]["symbols"]["extends"], "Label")
        self.assertEqual(generated_script["opened_script"]["script_editor"]["current_path"], "res://tools/agent_status.gd")
        waited_script = self.client.wait_for_script(
            "res://tools/agent_status.gd",
            extends="Label",
            functions=["agent_status"],
            source_contains="agent_status",
            timeout=0.1,
        )
        self.assertEqual(waited_script["symbols"]["functions"][0]["name"], "agent_status")
        fire_and_forget_script = self.client.write_script(
            "res://tools/no_wait.gd",
            "extends Node\n",
            wait=False,
        )
        self.assertNotIn("script", fire_and_forget_script)
        entry = self.client.editor_filesystem_describe("res://scripts/generated/agent_tool.gd")
        self.assertEqual(entry["resource_type"], "GDScript")
        indexed = self.client.wait_for_editor_filesystem_entry(
            "res://scripts/generated/agent_tool.gd",
            resource_type="GDScript",
            is_file=True,
            timeout=0.1,
        )
        self.assertEqual(indexed["name"], "agent_tool.gd")
        found = self.client.editor_filesystem_find("res://scripts", extension="gd", name="agent_tool.gd")
        self.assertEqual(found["entries"][0]["path"], "res://scripts/generated/agent_tool.gd")
        waited_find = self.client.wait_for_editor_filesystem_find(
            "res://scripts",
            extension="gd",
            name_contains="agent",
            resource_type="GDScript",
            min_count=1,
            max_count=1,
            timeout=0.1,
        )
        self.assertEqual(waited_find["count"], 1)
        missing_find = self.client.wait_for_editor_filesystem_find(
            "res://scripts",
            name="missing.gd",
            min_count=0,
            max_count=0,
            timeout=0.1,
        )
        self.assertEqual(missing_find["count"], 0)
        expect_filesystem(self.client, "res://scripts/generated/agent_tool.gd").to_be_indexed(
            resource_type="GDScript",
            is_file=True,
            timeout=0.1,
        )
        expect_filesystem(self.client, "res://scripts/generated/agent_tool.gd").to_have_resource_type("GDScript", timeout=0.1)
        expect_filesystem(self.client, "res://scripts").to_have_indexed_count(1, extension="gd", timeout=0.1)
        expect_filesystem(self.client, "res://scripts").to_contain("agent_tool.gd", extension="gd", timeout=0.1)
        expect_filesystem(self.client, "res://scripts").not_to_contain("missing.gd", extension="gd", timeout=0.1)
        with self.assertRaisesRegex(ValueError, "max_count"):
            self.client.wait_for_editor_filesystem_find("res://scripts", min_count=2, max_count=1)
        with self.assertRaisesRegex(AssertionError, "Expected editor filesystem search"):
            self.client.wait_for_editor_filesystem_find(
                "res://scripts",
                name="missing.gd",
                min_count=1,
                timeout=0.01,
                interval=0.001,
            )
        selected = self.client.editor_filesystem_select("res://scripts/generated/agent_tool.gd", inspect=True, timeout=0.1)
        self.assertTrue(selected["selected"])
        self.assertTrue(selected["filesystem_state"]["selected"])
        self.assertTrue(
            self.client.wait_for_editor_filesystem_selection(
                "res://scripts/generated/agent_tool.gd",
                timeout=0.1,
            )["selected"]
        )
        self.assertTrue(
            self.client.wait_for_editor_filesystem_entry(
                "res://scripts/generated/agent_tool.gd",
                selected=True,
                timeout=0.1,
            )["selected"]
        )
        selected_search = self.client.editor_filesystem_find("res://scripts", extension="gd")
        self.assertTrue(
            any(
                entry["path"] == "res://scripts/generated/agent_tool.gd" and entry["selected"]
                for entry in selected_search["entries"]
            )
        )
        no_wait_selection = self.client.editor_filesystem_select(
            "res://scripts/generated/agent_tool.gd",
            wait=False,
        )
        self.assertNotIn("filesystem_state", no_wait_selection)
        self.client.fs_write_text("res://scenes/opened_from_filesystem.tscn", "[gd_scene format=3]\n")
        opened_scene_file = self.client.editor_filesystem_open(
            "res://scenes/opened_from_filesystem.tscn",
            timeout=0.1,
        )
        self.assertEqual(opened_scene_file["action"], "scene")
        self.assertEqual(opened_scene_file["editor_status"]["edited_scene_file_path"], "res://scenes/opened_from_filesystem.tscn")
        self.assertTrue(opened_scene_file["filesystem_state"]["selected"])
        opened_script_file = self.client.editor_filesystem_open(
            "res://scripts/generated/agent_tool.gd",
            line=2,
            timeout=0.1,
        )
        self.assertEqual(opened_script_file["action"], "script")
        self.assertEqual(opened_script_file["script_state"]["path"], "res://scripts/generated/agent_tool.gd")
        self.assertIn("res://scripts/generated/agent_tool.gd", opened_script_file["script_editor"]["open_paths"])
        self.client.resource_save("res://data/opened_resource.tres", properties={"resource_name": "OpenedResource"}, timeout=0.1)
        opened_resource_file = self.client.editor_filesystem_open(
            "res://data/opened_resource.tres",
            timeout=0.1,
        )
        self.assertEqual(opened_resource_file["action"], "resource")
        self.assertTrue(opened_resource_file["inspected"])
        self.assertEqual(opened_resource_file["inspector_state"]["target"]["path"], "res://data/opened_resource.tres")
        no_wait_open_file = self.client.editor_filesystem_open(
            "res://scripts/generated/agent_tool.gd",
            wait=False,
        )
        self.assertNotIn("filesystem_state", no_wait_open_file)

    def test_editor_expectations_poll_status(self) -> None:
        editor = expect_editor(self.client)
        status = self.client.editor_status()
        self.assertTrue(status["editor"])
        self.assertTrue(status["ui"]["has_base_control"])
        ui_status = self.client.editor_ui_status()
        self.assertEqual(ui_status["main_screen_name"], "2D")
        self.assertEqual(ui_status["base_control"]["class"], "Panel")
        self.client.wait_for_editor_ui({"has_base_control": True, "main_screen_name": "2D"}, timeout=0.1)

        editor.to_be_available(timeout=0.1)
        editor.to_have_base_control(timeout=0.1)
        editor.to_have_main_screen(timeout=0.1)
        editor.to_have_main_screen("2D", timeout=0.1)
        editor.to_have_ui({"bottom_panel": {"can_hide": True}}, timeout=0.1)
        editor.to_have_bottom_panel_capability(can_make_visible=True, can_hide=True, timeout=0.1)
        switched = self.client.editor_switch_main_screen("Script", timeout=0.1)
        self.assertEqual(switched["main_screen_name"], "Script")
        self.assertEqual(switched["ui_state"]["main_screen_name"], "Script")
        self.client.wait_for_editor_main_screen("Script", timeout=0.1)
        editor.to_have_main_screen("Script", timeout=0.1)
        raw_switch = self.client.editor_switch_main_screen("2D", wait=False)
        self.assertEqual(raw_switch["main_screen_name"], "2D")
        self.assertNotIn("ui_state", raw_switch)
        hidden_panel = self.client.editor_hide_bottom_panel(timeout=0.1)
        self.assertTrue(hidden_panel["hidden"])
        self.assertTrue(self.server.bottom_panel_hidden)
        self.assertTrue(hidden_panel["ui_state"]["bottom_panel"]["can_hide"])
        raw_hide = self.client.editor_hide_bottom_panel(wait=False)
        self.assertTrue(raw_hide["hidden"])
        self.assertNotIn("ui_state", raw_hide)
        editor.not_to_have_undo(timeout=0.1)
        editor.not_to_have_redo(timeout=0.1)
        editor.to_match_history({"available": True, "can_undo": False, "can_redo": False}, timeout=0.1)
        editor.to_have_open_scene("res://scenes/main.tscn", timeout=0.1)
        editor.to_have_open_scenes(["res://scenes/main.tscn"], exact=True, timeout=0.1)
        editor.to_have_edited_scene("res://scenes/main.tscn", timeout=0.1)
        editor.to_have_edited_scene_name("Main", timeout=0.1)
        editor.to_have_edited_scene_file_path("res://scenes/main.tscn", timeout=0.1)
        editor.not_to_be_playing(timeout=0.1)
        editor.to_match_status({"editor": True, "playing": False}, timeout=0.1)
        play_status = self.client.editor_play("main", timeout=0.1)
        self.assertTrue(play_status["playing"])
        self.assertEqual(play_status["playing_scene"], "res://scenes/main.tscn")
        self.assertEqual(play_status["scene"], "main")
        self.assertEqual(play_status["editor_status"]["playing_scene"], "res://scenes/main.tscn")
        self.client.wait_for_editor_playing("res://scenes/main.tscn", timeout=0.1)
        editor.to_be_playing(timeout=0.1)
        editor.to_be_playing("res://scenes/main.tscn", timeout=0.1)
        editor.to_have_playing_scene("res://scenes/main.tscn", timeout=0.1)
        stop_status = self.client.editor_stop(timeout=0.1)
        self.assertFalse(stop_status["playing"])
        self.assertFalse(stop_status["editor_status"]["playing"])
        self.client.wait_for_editor_stopped(timeout=0.1)
        editor.to_be_stopped(timeout=0.1)

        custom_status = self.client.editor_play("res://scenes/secondary.tscn", timeout=0.1)
        self.assertEqual(custom_status["playing_scene"], "res://scenes/secondary.tscn")
        self.assertEqual(custom_status["editor_status"]["playing_scene"], "res://scenes/secondary.tscn")
        raw_stop = self.client.editor_stop(wait=False)
        self.assertEqual(raw_stop, {"playing": False})
        editor.not_to_be_playing(timeout=0.1)

        selected_counter = self.client.editor_select("#CounterButton")
        self.assertEqual(selected_counter["selection_state"]["count"], 1)
        editor.to_have_selection_count(1, timeout=0.1)
        editor.to_have_selection("#CounterButton", timeout=0.1)
        waited_selection = self.client.wait_for_editor_selection("#CounterButton", exact=True, timeout=0.1)
        self.assertEqual(waited_selection["count"], 1)
        multi_selection = self.client.editor_select(["#CounterButton", "#NextSceneButton"])
        self.assertEqual(multi_selection["selection_state"]["count"], 2)
        self.assertEqual(
            self.client.wait_for_editor_selection(["#CounterButton", "#NextSceneButton"], exact=True, timeout=0.1)[
                "count"
            ],
            2,
        )
        fire_and_forget_selection = self.client.editor_select("#CounterButton", wait=False)
        self.assertNotIn("selection_state", fire_and_forget_selection)
        with self.assertRaisesRegex(AssertionError, "Expected editor selection"):
            self.client.wait_for_editor_selection("#Missing", timeout=0.01, interval=0.001)
        editor.to_have_selected_nodes(["CounterButton"], exact=True, timeout=0.1)

    def test_trace_expectations_poll_events(self) -> None:
        trace = expect_trace(self.client)
        self.client.trace_start(clear=True, max_events=10)
        self.client.locator("#CounterButton").click()

        event = trace.to_have_event("node.click", data={"strategy": "pressed_signal"}, timeout=0.1)
        self.assertEqual(event["data"]["path"], "/root/Main/CounterButton")
        trace.to_have_rpc("node.click", timeout=0.1)
        trace.to_have_event_sequence(["trace.start", "node.click", "rpc"], timeout=0.1)
        self.assertEqual(self.client.trace_count("rpc", data={"method": "node.click"}), 1)
        trace.to_have_event_count(1, "node.click", timeout=0.1)
        trace.to_have_event_count(3, at_least=True, timeout=0.1)
        trace.to_have_rpc_count("node.click", 1, timeout=0.1)
        self.assertTrue(trace.client.trace_events(event_type="rpc"))
        trace.not_to_have_event("node.delete", timeout=0.05)
        trace.not_to_have_rpc("node.delete", timeout=0.05)
        self.client.trace_clear()
        trace.to_be_empty(timeout=0.1)
        self.client.trace_stop()

    def test_log_expectations_poll_local_collector(self) -> None:
        collector = _GodotLogCollector(max_events=10)
        self.client._log_collector = collector
        collector._append_line("Godot Engine v4.6.2.stable\n")
        collector._append_line("USER ERROR: Agent live error\n")
        collector._append_line("   at: push_error (res://scripts/main.gd:4)\n")
        collector._append_line("WARNING: Agent live warning\n")

        self.assertIn("Godot Engine", self.client.log_text())
        error = self.client.wait_for_log("Agent live error", severity="error", timeout=0.1)
        self.assertEqual(error["kind"], "USER ERROR")
        self.assertEqual(error["path"], "res://scripts/main.gd")
        self.assertEqual(error["line"], 4)
        warnings = self.client.log_events(severity="warning")
        self.assertEqual(warnings[0]["message"], "Agent live warning")

        log = expect_log(self.client)
        log.to_have_error("Agent live error", timeout=0.1)
        log.to_have_warning("Agent live warning", timeout=0.1)
        log.not_to_have_message("missing marker", timeout=0.05)
        log.not_to_have_error("missing marker", timeout=0.05)
        log.not_to_have_warning("missing marker", timeout=0.05)
        with self.assertRaisesRegex(AssertionError, "Expected Godot log not to contain event"):
            log.not_to_have_error("Agent live error", timeout=0.01, interval=0.001)
        with self.assertRaisesRegex(AssertionError, "Expected Godot log not to contain event"):
            log.not_to_have_warning("Agent live warning", timeout=0.01, interval=0.001)
        self.assertGreaterEqual(len(self.client.log_events(clear=True)), 4)
        self.assertEqual(self.client.log_events(), [])


class Pathish:
    def __init__(self, path: str):
        self.path = path

    @property
    def stem_title(self) -> str:
        stem = self.path.rsplit("/", 1)[-1].split(".", 1)[0]
        return stem[:1].upper() + stem[1:]


if __name__ == "__main__":
    unittest.main()

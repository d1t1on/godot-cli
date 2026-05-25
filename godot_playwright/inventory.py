from __future__ import annotations

import re
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


RESOURCE_EXTENSIONS = {".tres", ".res", ".gdshader", ".material", ".theme", ".translation"}
ASSET_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".wav",
    ".ogg",
    ".mp3",
    ".ttf",
    ".otf",
}
TEXT_RESOURCE_EXTENSIONS = {".tscn", ".tres", ".gdshader", ".material", ".theme", ".translation"}


class ProjectInventoryError(RuntimeError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(_project_inventory_error_message(report))


def inspect_project(
    project: str | Path,
    *,
    exclude: list[str] | None = None,
    include_settings: bool = True,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    started = time.monotonic()
    exclude_patterns = exclude or []
    diagnostics: list[dict[str, Any]] = []

    project_file = project_path / "project.godot"
    config = _config_summary(project_file, include_settings)
    if not project_file.is_file():
        diagnostics.append(
            {
                "severity": "error",
                "kind": "PROJECT_FILE_MISSING",
                "message": "project.godot was not found",
                "path": "project.godot",
                "global_path": str(project_file),
                "line": None,
            }
        )

    values = _project_setting_values(project_file)
    uid_paths = _uid_path_index(project_path)
    main_scene_path = _setting_value(values, "application", "run/main_scene", "")
    main_scene = (
        _resource_entry(project_path, str(main_scene_path), uid_paths=uid_paths)
        if main_scene_path
        else _empty_resource_entry()
    )
    if main_scene_path == "":
        diagnostics.append(
            {
                "severity": "warning",
                "kind": "MAIN_SCENE_NOT_CONFIGURED",
                "message": "application/run/main_scene is not configured",
                "path": "project.godot",
                "line": None,
            }
        )
    elif not main_scene["exists"]:
        diagnostics.append(
            {
                "severity": "error",
                "kind": "MAIN_SCENE_MISSING",
                "message": f"Configured main scene does not exist: {main_scene_path}",
                "path": str(main_scene_path),
                "global_path": main_scene.get("global_path", ""),
                "line": None,
            }
        )

    autoloads = _autoload_summaries(
        project_path,
        values.get("autoload", {}) if isinstance(values, dict) else {},
        uid_paths=uid_paths,
    )
    for autoload in autoloads:
        if not autoload["exists"]:
            diagnostics.append(
                {
                    "severity": "error",
                    "kind": "AUTOLOAD_MISSING",
                    "message": f"Autoload target does not exist: {autoload['path']}",
                    "path": autoload["path"],
                    "global_path": autoload["global_path"],
                    "autoload": autoload["name"],
                    "line": None,
                }
            )

    export_presets = _export_presets_summary(project_path / "export_presets.cfg", include_settings)
    files = _file_inventory(project_path, exclude_patterns)
    error_count = sum(1 for item in diagnostics if item.get("severity") == "error")
    report = {
        "project": str(project_path),
        "ok": project_path.is_dir() and error_count == 0,
        "exists": project_path.is_dir(),
        "project_file": config,
        "name": _setting_value(values, "application", "config/name", ""),
        "main_scene": main_scene,
        "autoloads": autoloads,
        "autoload_count": len(autoloads),
        "export_presets": export_presets,
        "files": files,
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
        "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
    }
    if check and not report["ok"]:
        raise ProjectInventoryError(report)
    return report


def inspect_export_presets(
    project: str | Path,
    *,
    include_settings: bool = True,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    return _export_presets_summary(project_path / "export_presets.cfg", include_settings)


def _config_summary(path: Path, include_settings: bool) -> dict[str, Any]:
    exists = path.is_file()
    values: dict[str, dict[str, Any]] = {}
    entries: dict[str, dict[str, dict[str, Any]]] = {}
    diagnostics: list[dict[str, Any]] = []
    if exists:
        parsed = _parse_config_text(path.read_text(encoding="utf-8"))
        values = parsed["values"]
        entries = parsed["entries"]
        diagnostics = parsed["diagnostics"]
    summary: dict[str, Any] = {
        "path": _res_path_for_project_file(path),
        "global_path": str(path),
        "exists": exists,
        "section_count": len(values),
        "sections": list(values.keys()),
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
    }
    if include_settings:
        summary["values"] = values
        summary["entries"] = entries
    else:
        summary["values"] = {}
        summary["entries"] = {}
    return summary


def _project_setting_values(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    return _parse_config_text(path.read_text(encoding="utf-8"))["values"]


def _export_presets_summary(path: Path, include_settings: bool) -> dict[str, Any]:
    exists = path.is_file()
    values: dict[str, dict[str, Any]] = {}
    entries: dict[str, dict[str, dict[str, Any]]] = {}
    diagnostics: list[dict[str, Any]] = []
    if exists:
        parsed = _parse_config_text(path.read_text(encoding="utf-8"))
        values = parsed["values"]
        entries = parsed["entries"]
        diagnostics = parsed["diagnostics"]
    presets = []
    for section, section_values in values.items():
        match = re.fullmatch(r"preset\.(\d+)", section)
        if not match:
            continue
        index = int(match.group(1))
        options = values.get(f"preset.{index}.options", {})
        presets.append(
            {
                "index": index,
                "name": section_values.get("name", ""),
                "platform": section_values.get("platform", ""),
                "runnable": section_values.get("runnable", False),
                "export_filter": section_values.get("export_filter", ""),
                "include_filter": section_values.get("include_filter", ""),
                "exclude_filter": section_values.get("exclude_filter", ""),
                "export_path": section_values.get("export_path", ""),
                "options": options,
                "option_count": len(options),
            }
        )
    presets.sort(key=lambda item: int(item.get("index", 0)))
    summary: dict[str, Any] = {
        "path": "res://export_presets.cfg",
        "global_path": str(path),
        "exists": exists,
        "presets": presets,
        "count": len(presets),
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
    }
    if include_settings:
        summary["values"] = values
        summary["entries"] = entries
    return summary


def _parse_config_text(text: str) -> dict[str, Any]:
    section = ""
    values: dict[str, dict[str, Any]] = {section: {}}
    entries: dict[str, dict[str, dict[str, Any]]] = {section: {}}
    diagnostics: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped == "" or stripped.startswith(";"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            values.setdefault(section, {})
            entries.setdefault(section, {})
            continue
        if "=" not in stripped:
            diagnostics.append(
                {
                    "severity": "warning",
                    "kind": "UNPARSED_CONFIG_LINE",
                    "message": "Config line is not a section or key/value assignment",
                    "line": line_number,
                    "text": stripped,
                }
            )
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        value = _parse_config_value(raw_value)
        values.setdefault(section, {})[key] = value
        entries.setdefault(section, {})[key] = {
            "raw": raw_value,
            "value": value,
            "line": line_number,
        }
    if not values.get("", {}):
        values.pop("", None)
        entries.pop("", None)
    return {"values": values, "entries": entries, "diagnostics": diagnostics}


def _parse_config_value(raw: str) -> Any:
    if raw.startswith('"') and raw.endswith('"'):
        return _unescape_config_string(raw[1:-1])
    if raw in {"true", "false"}:
        return raw == "true"
    if raw in {"null", "nil"}:
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?", raw):
        return float(raw)
    call = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\((.*)\)", raw)
    if call:
        return {"$type": call.group(1), "args": _parse_call_args(call.group(2))}
    return {"$raw": raw}


def _parse_call_args(raw_args: str) -> list[Any]:
    args: list[Any] = []
    current = []
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
        if char == "," and not in_string:
            args.append(_parse_config_value("".join(current).strip()))
            current = []
            continue
        current.append(char)
    if current or raw_args.strip():
        args.append(_parse_config_value("".join(current).strip()))
    return args


def _unescape_config_string(value: str) -> str:
    return value.replace(r"\"", '"').replace(r"\\", "\\").replace(r"\n", "\n").replace(r"\t", "\t")


def _setting_value(values: dict[str, dict[str, Any]], section: str, key: str, default: Any) -> Any:
    section_values = values.get(section, {})
    if not isinstance(section_values, dict):
        return default
    return section_values.get(key, default)


def _autoload_summaries(
    project_path: Path,
    values: dict[str, Any],
    *,
    uid_paths: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    autoloads = []
    for name, raw_value in sorted(values.items()):
        raw = str(raw_value)
        singleton = raw.startswith("*")
        path = raw.removeprefix("*")
        entry = _resource_entry(project_path, path, uid_paths=uid_paths)
        entry.update(
            {
                "name": name,
                "setting": f"autoload/{name}",
                "raw": raw,
                "singleton": singleton,
            }
        )
        autoloads.append(entry)
    return autoloads


def _resource_entry(
    project_path: Path,
    path: str,
    *,
    uid_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    raw_path = path
    uid = path if path.startswith("uid://") else ""
    resolved_path = uid_paths.get(path, "") if uid and uid_paths is not None else ""
    path = resolved_path or path
    global_path = _global_path(project_path, path) if not uid or resolved_path else None
    exists = global_path.is_file() if global_path is not None else False
    entry = {
        "path": path,
        "global_path": "" if global_path is None else str(global_path),
        "exists": exists,
        "extension": Path(path).suffix,
    }
    if raw_path != path:
        entry["raw_path"] = raw_path
    if uid:
        entry["uid"] = uid
    return entry


def _empty_resource_entry() -> dict[str, Any]:
    return {"path": "", "global_path": "", "exists": False, "extension": ""}


def _uid_path_index(project_path: Path) -> dict[str, str]:
    uid_paths: dict[str, str] = {}
    if not project_path.is_dir():
        return uid_paths
    for path in sorted(project_path.rglob("*")):
        if not path.is_file() or _is_ignored_path(project_path, path):
            continue
        if path.suffix == ".uid":
            uid = _read_uid_sidecar(path)
            target = path.with_suffix("")
            if uid and target.is_file():
                uid_paths.setdefault(uid, _res_path_for_file(project_path, target))
            continue
        if path.suffix.lower() not in TEXT_RESOURCE_EXTENSIONS:
            continue
        uid = _read_text_resource_uid(path)
        if uid:
            uid_paths.setdefault(uid, _res_path_for_file(project_path, path))
    return uid_paths


def _read_uid_sidecar(path: Path) -> str:
    try:
        uid = path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[0]
    except (IndexError, OSError, UnicodeDecodeError):
        return ""
    return uid if uid.startswith("uid://") else ""


def _read_text_resource_uid(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    except OSError:
        return ""
    match = re.search(r'\buid="(uid://[^"]+)"', text)
    return match.group(1) if match else ""


def _file_inventory(project_path: Path, exclude: list[str]) -> dict[str, Any]:
    scenes = []
    scripts = []
    resources = []
    assets = []
    files = []
    total_bytes = 0
    extension_counts: dict[str, int] = {}
    extension_bytes: dict[str, int] = {}
    directory_counts: dict[str, int] = {}
    directory_bytes: dict[str, int] = {}
    category_counts = {"scenes": 0, "scripts": 0, "resources": 0, "assets": 0, "other": 0}
    category_bytes = {"scenes": 0, "scripts": 0, "resources": 0, "assets": 0, "other": 0}
    max_path_depth = 0
    if not project_path.is_dir():
        scale = _scale_summary(
            files,
            total_bytes=0,
            directory_counts=directory_counts,
            directory_bytes=directory_bytes,
            extension_counts=extension_counts,
            extension_bytes=extension_bytes,
            category_counts=category_counts,
            category_bytes=category_bytes,
            max_path_depth=0,
        )
        return {
            "count": 0,
            "total_bytes": 0,
            "extension_counts": {},
            "extension_bytes": {},
            "directory_counts": {},
            "directory_bytes": {},
            "top_directories": [],
            "scale": scale,
            "largest_files": [],
            "newest_files": [],
            "files": files,
            "scenes": scenes,
            "scene_count": 0,
            "scripts": scripts,
            "script_count": 0,
            "resources": resources,
            "resource_count": 0,
            "assets": assets,
            "asset_count": 0,
        }
    for path in sorted(project_path.rglob("*")):
        if not path.is_file() or _is_ignored_path(project_path, path):
            continue
        relative = path.relative_to(project_path)
        res_path = "res://" + relative.as_posix()
        if _is_excluded(res_path, exclude):
            continue
        stat = path.stat()
        extension = path.suffix.lower()
        directory = _directory_res_path(relative)
        max_path_depth = max(max_path_depth, len(relative.parts))
        entry = {
            "path": res_path,
            "global_path": str(path),
            "extension": extension,
            "bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "directory": directory,
            "depth": len(relative.parts),
        }
        files.append(entry)
        total_bytes += stat.st_size
        extension_key = extension or "<none>"
        extension_counts[extension_key] = extension_counts.get(extension_key, 0) + 1
        extension_bytes[extension_key] = extension_bytes.get(extension_key, 0) + stat.st_size
        directory_counts[directory] = directory_counts.get(directory, 0) + 1
        directory_bytes[directory] = directory_bytes.get(directory, 0) + stat.st_size
        if extension in {".tscn", ".scn"}:
            scenes.append(entry)
            category = "scenes"
        elif extension == ".gd":
            scripts.append(entry)
            category = "scripts"
        elif extension in RESOURCE_EXTENSIONS:
            resources.append(entry)
            category = "resources"
        elif extension in ASSET_EXTENSIONS:
            assets.append(entry)
            category = "assets"
        else:
            category = "other"
        category_counts[category] += 1
        category_bytes[category] += stat.st_size
    scale = _scale_summary(
        files,
        total_bytes=total_bytes,
        directory_counts=directory_counts,
        directory_bytes=directory_bytes,
        extension_counts=extension_counts,
        extension_bytes=extension_bytes,
        category_counts=category_counts,
        category_bytes=category_bytes,
        max_path_depth=max_path_depth,
    )
    return {
        "count": len(files),
        "total_bytes": total_bytes,
        "extension_counts": dict(sorted(extension_counts.items())),
        "extension_bytes": dict(sorted(extension_bytes.items())),
        "directory_counts": dict(sorted(directory_counts.items())),
        "directory_bytes": dict(sorted(directory_bytes.items())),
        "top_directories": scale["top_directories"],
        "scale": scale,
        "largest_files": _trim_file_entries(sorted(files, key=lambda entry: (-int(entry["bytes"]), entry["path"]))),
        "newest_files": _trim_file_entries(sorted(files, key=lambda entry: (-int(entry["mtime_ns"]), entry["path"]))),
        "files": files,
        "scenes": scenes,
        "scene_count": len(scenes),
        "scripts": scripts,
        "script_count": len(scripts),
        "resources": resources,
        "resource_count": len(resources),
        "assets": assets,
        "asset_count": len(assets),
    }


def _directory_res_path(relative: Path) -> str:
    parent = relative.parent.as_posix()
    return "res://" if parent in {"", "."} else f"res://{parent}"


def _scale_summary(
    files: list[dict[str, Any]],
    *,
    total_bytes: int,
    directory_counts: dict[str, int],
    directory_bytes: dict[str, int],
    extension_counts: dict[str, int],
    extension_bytes: dict[str, int],
    category_counts: dict[str, int],
    category_bytes: dict[str, int],
    max_path_depth: int,
) -> dict[str, Any]:
    file_count = len(files)
    largest_file_bytes = max((int(entry.get("bytes", 0)) for entry in files), default=0)
    return {
        "file_count": file_count,
        "directory_count": len(directory_counts),
        "total_bytes": total_bytes,
        "average_file_bytes": round(total_bytes / file_count, 3) if file_count else 0,
        "largest_file_bytes": largest_file_bytes,
        "max_path_depth": max_path_depth,
        "category_counts": dict(category_counts),
        "category_bytes": dict(category_bytes),
        "top_extensions": _top_count_byte_entries(extension_counts, extension_bytes, key_name="extension"),
        "top_directories": _top_count_byte_entries(directory_counts, directory_bytes, key_name="path"),
    }


def _top_count_byte_entries(
    counts: dict[str, int],
    byte_counts: dict[str, int],
    *,
    key_name: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    entries = [
        {key_name: name, "count": count, "bytes": byte_counts.get(name, 0)}
        for name, count in counts.items()
    ]
    entries.sort(key=lambda entry: (-int(entry["bytes"]), -int(entry["count"]), str(entry[key_name])))
    return entries[:limit]


def _trim_file_entries(entries: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    return [
        {
            "path": entry["path"],
            "global_path": entry["global_path"],
            "extension": entry["extension"],
            "bytes": entry["bytes"],
            "mtime_ns": entry["mtime_ns"],
            "directory": entry.get("directory", ""),
            "depth": entry.get("depth", 0),
        }
        for entry in entries[:limit]
    ]


def _global_path(project_path: Path, path: str) -> Path | None:
    if path == "":
        return None
    if path.startswith("res://"):
        return (project_path / path.removeprefix("res://")).resolve()
    raw_path = Path(path)
    if raw_path.is_absolute():
        return raw_path.resolve()
    return (project_path / raw_path).resolve()


def _res_path_for_project_file(path: Path) -> str:
    return "res://" + path.name if path.name != "project.godot" else "res://project.godot"


def _res_path_for_file(project_path: Path, path: Path) -> str:
    return "res://" + path.resolve().relative_to(project_path).as_posix()


def _is_ignored_path(project_path: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(project_path)
    except ValueError:
        relative = path
    return any(part in {".godot", "__pycache__"} for part in relative.parts)


def _is_excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) or fnmatch(path.removeprefix("res://"), pattern) for pattern in patterns)


def _project_inventory_error_message(report: dict[str, Any]) -> str:
    diagnostics = report.get("diagnostics", [])
    if diagnostics:
        details = "\n".join(
            f"{item.get('kind')}: {item.get('message')} {item.get('path', '')}".rstrip()
            for item in diagnostics[:8]
        )
    else:
        details = "unknown error"
    return f"Godot project inventory failed for {report.get('project')!r}\n{details}"

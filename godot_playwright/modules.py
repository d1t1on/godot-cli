from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .install import enable_autoload, package_root, repository_root


_ALLOWED_MANIFEST_FIELDS = {
    "name",
    "version",
    "display_name",
    "description",
    "godot_version",
    "copy",
    "autoloads",
    "demo",
    "validation",
}
_REQUIRED_MANIFEST_FIELDS = {
    "name",
    "version",
    "display_name",
    "description",
    "godot_version",
    "copy",
    "autoloads",
}
_COPY_FIELDS = {"from", "to"}
_AUTOLOAD_FIELDS = {"name", "path"}
_DEMO_FIELDS = {"copy"}


class ModuleError(RuntimeError):
    pass


@dataclass(frozen=True)
class _CopyOperation:
    source: Path
    target: Path
    source_label: str
    target_res: str


def default_module_roots() -> list[Path]:
    return [
        repository_root() / "gameplay_modules",
        package_root() / "bundled_gameplay_modules",
    ]


def module_library_path(module_root: str | Path | None = None) -> Path:
    if module_root is not None:
        return Path(module_root).expanduser().resolve()

    roots = default_module_roots()
    for root in roots:
        if root.exists():
            return root
    return roots[0]


def list_modules(*, module_root: str | Path | None = None) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in _module_roots(module_root):
        if not root.exists():
            continue
        if not root.is_dir():
            raise ModuleError(f"Module root is not a directory: {root}")
        for module_dir in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name):
            manifest_path = module_dir / "module.json"
            if not manifest_path.exists():
                continue
            manifest = _load_module_manifest(manifest_path, module_dir.name)
            if manifest["name"] in seen:
                continue
            seen.add(manifest["name"])
            modules.append(manifest)
    return modules


def load_module_manifest(module_name: str, *, module_root: str | Path | None = None) -> dict[str, Any]:
    manifest_path = _find_module_manifest(module_name, module_root)
    return _load_module_manifest(manifest_path, module_name)


def add_module(
    project_path: str | Path,
    module_name: str,
    *,
    module_root: str | Path | None = None,
    demo: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    project_dir = Path(project_path).expanduser().resolve()
    project_file = project_dir / "project.godot"
    if not project_file.exists():
        raise ModuleError(f"Godot project not found: {project_file}")

    manifest_path = _find_module_manifest(module_name, module_root)
    manifest = _load_module_manifest(manifest_path, module_name)
    module_dir = manifest_path.parent

    copy_entries = list(manifest["copy"])
    if demo:
        copy_entries.extend(manifest.get("demo", {}).get("copy", []))
    copy_operations = _plan_copy_operations(module_dir, project_dir, copy_entries)

    _check_copy_conflicts(copy_operations, project_dir, force=force)
    project_text = project_file.read_text(encoding="utf-8")
    _check_autoload_conflicts(project_text, manifest["autoloads"], force=force)

    for operation in copy_operations:
        _copy_file(operation.source, operation.target, force=force)

    autoload_reports: list[dict[str, str]] = []
    for autoload in manifest["autoloads"]:
        enabled_path = f"*{autoload['path']}"
        project_text = enable_autoload(project_text, autoload["name"], enabled_path)
        autoload_reports.append(
            {
                "name": autoload["name"],
                "path": autoload["path"],
                "enabled_path": enabled_path,
            }
        )
    project_file.write_text(project_text, encoding="utf-8")

    return {
        "ok": True,
        "module": manifest["name"],
        "version": manifest["version"],
        "project": str(project_dir),
        "demo": bool(demo),
        "copied": [
            {"source": operation.source_label, "target": operation.target_res}
            for operation in copy_operations
        ],
        "autoloads": autoload_reports,
        "warnings": [],
        "errors": [],
    }


def _module_roots(module_root: str | Path | None) -> list[Path]:
    if module_root is not None:
        return [module_library_path(module_root)]
    return default_module_roots()


def _find_module_manifest(module_name: str, module_root: str | Path | None) -> Path:
    _validate_module_name(module_name)
    checked: list[Path] = []
    for root in _module_roots(module_root):
        manifest_path = root / module_name / "module.json"
        checked.append(manifest_path)
        if manifest_path.exists():
            return manifest_path
    checked_text = ", ".join(str(path) for path in checked)
    raise ModuleError(f"Module not found: {module_name}. Checked: {checked_text}")


def _load_module_manifest(manifest_path: Path, expected_name: str) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModuleError(f"Invalid module manifest JSON: {manifest_path}: {exc}") from exc
    except OSError as exc:
        raise ModuleError(f"Unable to read module manifest: {manifest_path}: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ModuleError(f"Module manifest must be a JSON object: {manifest_path}")

    unsupported = sorted(set(manifest) - _ALLOWED_MANIFEST_FIELDS)
    if unsupported:
        raise ModuleError(f"Unsupported manifest field: {unsupported[0]}")

    missing = sorted(_REQUIRED_MANIFEST_FIELDS - set(manifest))
    if missing:
        raise ModuleError(f"Missing required manifest field: {missing[0]}")

    for field in ("name", "version", "display_name", "description", "godot_version"):
        _validate_non_empty_string(manifest[field], f"manifest.{field}")

    if manifest["name"] != expected_name:
        raise ModuleError(
            f"Manifest name mismatch: expected {expected_name!r}, found {manifest['name']!r}"
        )

    _validate_copy_entries(manifest["copy"], "manifest.copy")
    _validate_autoloads(manifest["autoloads"])
    if "demo" in manifest:
        _validate_demo(manifest["demo"])
    if "validation" in manifest:
        _validate_validation(manifest["validation"])
    return manifest


def _validate_module_name(module_name: str) -> None:
    _validate_relative_path(module_name, "module name")
    if PurePosixPath(module_name).name != module_name:
        raise ModuleError(f"Module name must not contain path separators: {module_name}")


def _validate_non_empty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ModuleError(f"{field} must be a non-empty string")


def _validate_copy_entries(entries: Any, field: str) -> None:
    if not isinstance(entries, list):
        raise ModuleError(f"{field} must be a list")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ModuleError(f"{field}[{index}] must be an object")
        unsupported = sorted(set(entry) - _COPY_FIELDS)
        if unsupported:
            raise ModuleError(f"Unsupported copy field: {field}[{index}].{unsupported[0]}")
        for key in ("from", "to"):
            if key not in entry:
                raise ModuleError(f"Missing copy field: {field}[{index}].{key}")
            _validate_relative_path(entry[key], f"{field}[{index}].{key}")


def _validate_autoloads(autoloads: Any) -> None:
    if not isinstance(autoloads, list):
        raise ModuleError("manifest.autoloads must be a list")
    for index, autoload in enumerate(autoloads):
        if not isinstance(autoload, dict):
            raise ModuleError(f"manifest.autoloads[{index}] must be an object")
        unsupported = sorted(set(autoload) - _AUTOLOAD_FIELDS)
        if unsupported:
            raise ModuleError(f"Unsupported autoload field: manifest.autoloads[{index}].{unsupported[0]}")
        if "name" not in autoload:
            raise ModuleError(f"Missing autoload field: manifest.autoloads[{index}].name")
        if "path" not in autoload:
            raise ModuleError(f"Missing autoload field: manifest.autoloads[{index}].path")
        _validate_non_empty_string(autoload["name"], f"manifest.autoloads[{index}].name")
        _validate_autoload_path(autoload["path"], f"manifest.autoloads[{index}].path")


def _validate_demo(demo: Any) -> None:
    if not isinstance(demo, dict):
        raise ModuleError("manifest.demo must be an object")
    unsupported = sorted(set(demo) - _DEMO_FIELDS)
    if unsupported:
        raise ModuleError(f"Unsupported demo manifest field: {unsupported[0]}")
    if "copy" in demo:
        _validate_copy_entries(demo["copy"], "manifest.demo.copy")


def _validate_validation(validation: Any) -> None:
    if not isinstance(validation, dict):
        raise ModuleError("manifest.validation must be an object")
    commands = validation.get("commands")
    if commands is None:
        return
    if not isinstance(commands, list) or not all(isinstance(command, str) for command in commands):
        raise ModuleError("manifest.validation.commands must be a list of strings")


def _validate_autoload_path(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ModuleError(f"{field} must be an unstarred res:// path")
    if value.startswith("*res://"):
        raise ModuleError(f"{field} must be an unstarred res:// path")
    if not value.startswith("res://"):
        raise ModuleError(f"{field} must be an unstarred res:// path")
    _validate_relative_path(value[len("res://") :], field)


def _validate_relative_path(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ModuleError(f"{field} must be a relative path")
    if value.startswith("res://") or value.startswith("*res://"):
        raise ModuleError(f"{field} must be a relative path")
    if "\\" in value:
        raise ModuleError(f"{field} must use forward slashes: {value}")

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise ModuleError(f"{field} must be a relative path: {value}")
    if any(part == ".." for part in posix_path.parts):
        raise ModuleError(f"{field} must not contain '..': {value}")


def _plan_copy_operations(
    module_dir: Path,
    project_dir: Path,
    copy_entries: list[dict[str, str]],
) -> list[_CopyOperation]:
    operations: list[_CopyOperation] = []
    for entry in copy_entries:
        source = module_dir / entry["from"]
        target_root = project_dir / entry["to"]
        if not source.exists():
            raise ModuleError(f"Module source not found: {source}")

        if source.is_dir():
            for source_file in sorted(path for path in source.rglob("*") if path.is_file()):
                relative = source_file.relative_to(source)
                source_label = _join_posix(entry["from"], relative.as_posix())
                target_relative = _join_posix(entry["to"], relative.as_posix())
                operations.append(
                    _CopyOperation(
                        source=source_file,
                        target=target_root / relative,
                        source_label=source_label,
                        target_res=_to_res_path(target_relative),
                    )
                )
        elif source.is_file():
            operations.append(
                _CopyOperation(
                    source=source,
                    target=target_root,
                    source_label=entry["from"],
                    target_res=_to_res_path(entry["to"]),
                )
            )
        else:
            raise ModuleError(f"Module source is not a file or directory: {source}")
    return operations


def _check_copy_conflicts(
    operations: list[_CopyOperation],
    project_dir: Path,
    *,
    force: bool,
) -> None:
    for operation in operations:
        parent_conflict = _first_non_directory_parent(operation.target, project_dir)
        if parent_conflict is not None:
            raise ModuleError(f"Target already exists and is not a directory: {parent_conflict}")
        if operation.target.exists() and not force:
            raise ModuleError(f"Target already exists: {operation.target}")


def _first_non_directory_parent(target: Path, project_dir: Path) -> Path | None:
    parent = target.parent
    while parent != project_dir:
        if parent.exists():
            return None if parent.is_dir() else parent
        parent = parent.parent
    return None


def _check_autoload_conflicts(
    project_text: str,
    autoloads: list[dict[str, str]],
    *,
    force: bool,
) -> None:
    if force:
        return
    for autoload in autoloads:
        if _has_autoload(project_text, autoload["name"]):
            raise ModuleError(f"Autoload already exists: {autoload['name']}")


def _has_autoload(project_text: str, name: str) -> bool:
    section = _find_section(project_text, "autoload")
    if section is None:
        return False
    start, end = section
    body = project_text[start:end]
    return bool(re.search(rf"(?m)^\s*{re.escape(name)}\s*=", body))


def _find_section(text: str, name: str) -> tuple[int, int] | None:
    header = re.search(rf"(?m)^\[{re.escape(name)}\]\s*$", text)
    if header is None:
        return None
    body_start = header.end()
    next_header = re.search(r"(?m)^\[[^\]]+\]\s*$", text[body_start:])
    body_end = len(text) if next_header is None else body_start + next_header.start()
    return body_start, body_end


def _copy_file(source: Path, target: Path, *, force: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.is_dir():
        if not force:
            raise ModuleError(f"Target already exists: {target}")
        shutil.rmtree(target)
    shutil.copy2(source, target)


def _join_posix(base: str, child: str) -> str:
    return (PurePosixPath(base) / PurePosixPath(child)).as_posix()


def _to_res_path(relative_path: str) -> str:
    return f"res://{PurePosixPath(relative_path).as_posix()}"
